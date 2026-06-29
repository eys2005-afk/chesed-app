from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')

DATA_FILE = 'data.json'
NEIGHBORHOODS = ['עמישב', 'שכונות', 'נאות שמיר', 'רמבלס', 'הרדוף']

DEFAULT_DATA = {
    "women": [
        {"id": 1, "name": "שרה כהן", "phone": "050-1234567", "neighborhood": "עמישב", "available": True, "times_served": 3, "unavailable_until": None},
        {"id": 2, "name": "רחל לוי", "phone": "052-2345678", "neighborhood": "שכונות", "available": True, "times_served": 2, "unavailable_until": None},
        {"id": 3, "name": "מרים ישראל", "phone": "054-3456789", "neighborhood": "נאות שמיר", "available": True, "times_served": 5, "unavailable_until": None},
        {"id": 4, "name": "דינה אברהם", "phone": "058-4567890", "neighborhood": "רמבלס", "available": True, "times_served": 1, "unavailable_until": None},
        {"id": 5, "name": "לאה גולן", "phone": "050-5678901", "neighborhood": "הרדוף", "available": True, "times_served": 4, "unavailable_until": None},
        {"id": 6, "name": "תמר בן-דוד", "phone": "052-6789012", "neighborhood": "עמישב", "available": True, "times_served": 2, "unavailable_until": None},
        {"id": 7, "name": "נעמי שפירא", "phone": "054-7890123", "neighborhood": "שכונות", "available": True, "times_served": 3, "unavailable_until": None},
        {"id": 8, "name": "אסתר מלכה", "phone": "058-8901234", "neighborhood": "נאות שמיר", "available": True, "times_served": 0, "unavailable_until": None},
        {"id": 9, "name": "חנה פרידמן", "phone": "050-9012345", "neighborhood": "רמבלס", "available": True, "times_served": 6, "unavailable_until": None},
        {"id": 10, "name": "יעל רוזן", "phone": "052-0123456", "neighborhood": "הרדוף", "available": True, "times_served": 1, "unavailable_until": None}
    ],
    "active_birth": None,
    "current_team": []
}


def load_data():
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def refresh_availability(data):
    now = datetime.now()
    changed = False
    for w in data['women']:
        if w.get('unavailable_until'):
            until = datetime.fromisoformat(w['unavailable_until'])
            if until <= now:
                w['available'] = True
                w['unavailable_until'] = None
                changed = True
    if changed:
        save_data(data)
    return data


def get_sheets_service():
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not creds_json:
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds_info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=creds)
    except Exception:
        return None


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/women', methods=['GET'])
def get_women():
    data = load_data()
    data = refresh_availability(data)
    return jsonify(data['women'])


@app.route('/api/women', methods=['POST'])
def add_woman():
    data = load_data()
    req = request.json
    new_id = max((w['id'] for w in data['women']), default=0) + 1
    woman = {
        'id': new_id,
        'name': req['name'],
        'phone': req.get('phone', ''),
        'neighborhood': req.get('neighborhood', NEIGHBORHOODS[0]),
        'available': True,
        'times_served': 0,
        'unavailable_until': None
    }
    data['women'].append(woman)
    save_data(data)
    return jsonify({'success': True, 'woman': woman})


@app.route('/api/women/<int:woman_id>', methods=['DELETE'])
def delete_woman(woman_id):
    data = load_data()
    data['women'] = [w for w in data['women'] if w['id'] != woman_id]
    save_data(data)
    return jsonify({'success': True})


@app.route('/api/birth', methods=['GET'])
def get_birth():
    data = load_data()
    return jsonify({
        'active_birth': data.get('active_birth'),
        'team': data.get('current_team', [])
    })


@app.route('/api/birth', methods=['POST'])
def start_birth():
    data = load_data()
    data = refresh_availability(data)
    req = request.json
    team_ids = req.get('team', [])

    data['active_birth'] = {
        'id': datetime.now().isoformat(),
        'mother_name': req.get('mother_name', 'לידה חדשה'),
        'date': datetime.now().isoformat()
    }
    data['current_team'] = team_ids

    for w in data['women']:
        if w['id'] in team_ids:
            w['times_served'] = w.get('times_served', 0) + 1

    save_data(data)
    return jsonify({'success': True, 'birth': data['active_birth'], 'team': data['current_team']})


@app.route('/api/cannot', methods=['POST'])
def cannot_serve():
    data = load_data()
    data = refresh_availability(data)
    req = request.json
    woman_id = req.get('woman_id')

    for w in data['women']:
        if w['id'] == woman_id:
            w['available'] = False
            w['unavailable_until'] = (datetime.now() + timedelta(weeks=1)).isoformat()
            w['times_served'] = max(0, w.get('times_served', 0) - 1)
            break

    available = [
        w for w in data['women']
        if w['available'] and w['id'] not in data['current_team']
    ]
    available.sort(key=lambda w: w.get('times_served', 0))

    if available:
        replacement = available[0]
        data['current_team'] = [
            replacement['id'] if x == woman_id else x
            for x in data['current_team']
        ]
        for w in data['women']:
            if w['id'] == replacement['id']:
                w['times_served'] = w.get('times_served', 0) + 1
                break
        save_data(data)
        return jsonify({'success': True, 'replacement': replacement, 'team': data['current_team']})

    save_data(data)
    return jsonify({'success': False, 'message': 'לא נמצאה מחליפה זמינה'})


@app.route('/api/complete', methods=['POST'])
def complete_birth():
    data = load_data()
    data['active_birth'] = None
    data['current_team'] = []
    save_data(data)
    return jsonify({'success': True})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    data = load_data()
    data = refresh_availability(data)
    women = data['women']

    available = [w for w in women if w['available']]
    unavailable = [w for w in women if not w['available']]
    total_served = sum(w.get('times_served', 0) for w in women)
    top_servers = sorted(women, key=lambda w: w.get('times_served', 0), reverse=True)[:5]

    by_neighborhood = {}
    for n in NEIGHBORHOODS:
        wn = [w for w in women if w['neighborhood'] == n]
        by_neighborhood[n] = {
            'total': len(wn),
            'available': len([w for w in wn if w['available']]),
            'times_served': sum(w.get('times_served', 0) for w in wn)
        }

    return jsonify({
        'total_women': len(women),
        'available': len(available),
        'unavailable': len(unavailable),
        'total_served': total_served,
        'top_servers': top_servers,
        'by_neighborhood': by_neighborhood,
        'unavailable_list': unavailable
    })


if __name__ == '__main__':
    app.run(debug=True)
