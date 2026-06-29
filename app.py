"""
׳¡׳‘׳‘ ׳—׳¡׳“ ג€” ׳’׳¨׳¢׳™׳ ׳×׳•׳¨׳ ׳™ ׳¢׳׳™׳—׳™ ׳¨׳׳׳”
Flask Backend + Google Sheets sync
"""

import os, json, time, ssl
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import urllib3
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context

# BlueCoat SSL bypass for all outgoing requests
import requests as _requests
_orig_req = _requests.Session.request
def _patched_req(self, *a, **kw):
    kw.setdefault('verify', False)
    return _orig_req(self, *a, **kw)
_requests.Session.request = _patched_req

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# GOOGLE SHEETS (optional ג€” set env vars to enable)
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
SHEETS_ENABLED = bool(os.getenv('GOOGLE_SHEET_ID'))

def get_sheets_client():
    """Returns gspread client if configured."""
    if not SHEETS_ENABLED:
        return None, None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_json = json.loads(os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '{}'))
        scopes = ['https://spreadsheets.google.com/feeds',
                  'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(os.getenv('GOOGLE_SHEET_ID'))
        # create worksheets if missing
        titles = [w.title for w in sh.worksheets()]
        if '׳ ׳©׳™׳' not in titles:
            sh.add_worksheet(title='׳ ׳©׳™׳', rows=500, cols=10)
        if '׳׳™׳“׳•׳×' not in titles:
            sh.add_worksheet(title='׳׳™׳“׳•׳×', rows=500, cols=10)
        return gc, sh
    except Exception as e:
        print(f"Sheets error: {e}")
        return None, None

def sync_to_sheets(women_data):
    """Write women list to Google Sheets (Women tab)."""
    _, sh = get_sheets_client()
    if not sh:
        return
    try:
        ws = sh.worksheet('׳ ׳©׳™׳')
        ws.clear()
        ws.append_row(['ID','׳©׳','׳˜׳׳₪׳•׳','׳©׳›׳•׳ ׳”','׳›׳×׳•׳‘׳×','׳¡׳˜׳˜׳•׳¡','׳׳ ׳–׳׳™׳ ׳” ׳¢׳“'])
        for w in women_data:
            until = ''
            if w.get('unavailUntil'):
                until = datetime.fromtimestamp(w['unavailUntil']/1000).strftime('%d/%m/%Y %H:%M')
            ws.append_row([w['id'], w['name'], w['phone'], w['hood'],
                           w.get('addr',''), w['status'], until])
    except Exception as e:
        print(f"Sheets sync error: {e}")

def load_from_sheets():
    """Load women list from Google Sheets."""
    _, sh = get_sheets_client()
    if not sh:
        return None
    try:
        ws = sh.worksheet('׳ ׳©׳™׳')
        rows = ws.get_all_records()
        result = []
        for r in rows:
            result.append({
                'id':          r.get('ID'),
                'name':        r.get('׳©׳',''),
                'phone':       r.get('׳˜׳׳₪׳•׳',''),
                'hood':        r.get('׳©׳›׳•׳ ׳”',''),
                'addr':        r.get('׳›׳×׳•׳‘׳×',''),
                'status':      r.get('׳¡׳˜׳˜׳•׳¡','available'),
                'unavailUntil': None,
            })
        return result
    except Exception as e:
        print(f"Sheets load error: {e}")
        return None

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# IN-MEMORY DATA (fallback when no Sheets)
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
_women = [
    {'id':1,'name':'׳¨׳‘׳§׳” ׳׳•׳™',   'phone':'050-1234567','hood':'׳¢׳׳™׳©׳‘',     'addr':'׳”׳¨׳¦׳ 12',    'status':'available','unavailUntil':None},
    {'id':2,'name':'׳׳¨׳™׳ ׳׳‘׳¨׳”׳', 'phone':'052-9876543','hood':'׳©׳›׳•׳ ׳•׳×',    'addr':'׳‘׳ ׳’׳•׳¨׳™׳•׳ 3','status':'available','unavailUntil':None},
    {'id':3,'name':'׳“׳™׳ ׳” ׳©׳₪׳™׳¨׳', 'phone':'054-1112233','hood':'׳ ׳׳•׳× ׳©׳׳™׳¨', 'addr':'׳”׳ ׳‘׳™׳׳™׳ 7',  'status':'available','unavailUntil':None},
    {'id':4,'name':'׳׳׳” ׳’׳•׳׳“׳‘׳¨׳’','phone':'053-4445566','hood':'׳¨׳׳‘׳׳¡',     'addr':'׳”׳₪׳׳׳— 2',    'status':'available','unavailUntil':None},
    {'id':5,'name':'׳—׳ ׳” ׳¨׳•׳–׳',   'phone':'050-7778899','hood':'׳”׳¨׳“׳•׳£',     'addr':'׳”׳“׳§׳ 9',     'status':'available','unavailUntil':None},
    {'id':6,'name':'׳©׳¨׳” ׳›׳”׳',    'phone':'052-3334455','hood':'׳¢׳׳™׳©׳‘',     'addr':'׳•׳™׳¦׳׳ 4',    'status':'available','unavailUntil':None},
    {'id':7,'name':'׳ ׳¢׳׳™ ׳‘׳¨׳§',   'phone':'057-1122334','hood':'׳©׳›׳•׳ ׳•׳×',    'addr':'׳”׳ ׳©׳™׳ 11',   'status':'available','unavailUntil':None},
    {'id':8,'name':'׳¨׳—׳ ׳₪׳¨׳¥',    'phone':'054-6667788','hood':'׳ ׳׳•׳× ׳©׳׳™׳¨', 'addr':'׳”׳’׳₪׳ 5',     'status':'available','unavailUntil':None},
    {'id':9,'name':'׳™׳¢׳ ׳׳–׳¨׳—׳™',  'phone':'050-9998877','hood':'׳¨׳׳‘׳׳¡',     'addr':'׳”׳–׳™׳× 8',     'status':'available','unavailUntil':None},
    {'id':10,'name':'׳×׳׳¨ ׳©׳׳•׳',  'phone':'052-1113322','hood':'׳”׳¨׳“׳•׳£',     'addr':'׳”׳‘׳¨׳•׳© 3',    'status':'available','unavailUntil':None},
]

_births = []

def check_unavail_expiry(women):
    now_ms = time.time() * 1000
    for w in women:
        if w['status'] == 'unavail' and w.get('unavailUntil') and now_ms > w['unavailUntil']:
            w['status'] = 'available'
            w['unavailUntil'] = None
    return women

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# ROUTES ג€” STATIC
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
@app.route('/')
def index():
    return send_from_directory('static', 'index.html', mimetype='text/html; charset=utf-8')

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# ROUTES ג€” WOMEN
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
@app.route('/api/women', methods=['GET'])
def get_women():
    global _women
    _women = check_unavail_expiry(_women)
    return jsonify(_women)

@app.route('/api/women', methods=['POST'])
def add_woman():
    global _women
    data = request.json
    if not data.get('name') or not data.get('phone') or not data.get('hood'):
        return jsonify({'error': '׳—׳¡׳¨׳™׳ ׳©׳“׳•׳× ׳—׳•׳‘׳”'}), 400
    new_id = max((w['id'] for w in _women), default=0) + 1
    woman = {
        'id':          new_id,
        'name':        data['name'].strip(),
        'phone':       data['phone'].strip(),
        'hood':        data['hood'],
        'addr':        data.get('addr','').strip(),
        'status':      'available',
        'unavailUntil': None,
    }
    _women.append(woman)
    sync_to_sheets(_women)
    return jsonify(woman), 201

@app.route('/api/women/<int:wid>', methods=['PATCH'])
def update_woman(wid):
    global _women
    woman = next((w for w in _women if w['id'] == wid), None)
    if not woman:
        return jsonify({'error': '׳׳ ׳ ׳׳¦׳׳”'}), 404
    data = request.json
    allowed = ['name','phone','hood','addr','status','unavailUntil']
    for key in allowed:
        if key in data:
            woman[key] = data[key]
    sync_to_sheets(_women)
    return jsonify(woman)

@app.route('/api/women/<int:wid>/cant', methods=['POST'])
def mark_cant(wid):
    """Mark woman as unavailable for 7 days."""
    global _women
    woman = next((w for w in _women if w['id'] == wid), None)
    if not woman:
        return jsonify({'error': '׳׳ ׳ ׳׳¦׳׳”'}), 404
    woman['status'] = 'unavail'
    woman['unavailUntil'] = (time.time() + 7 * 24 * 3600) * 1000
    sync_to_sheets(_women)
    return jsonify(woman)

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# ROUTES ג€” BIRTHS
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
@app.route('/api/births', methods=['GET'])
def get_births():
    return jsonify(_births)

@app.route('/api/births', methods=['POST'])
def add_birth():
    global _women, _births
    data = request.json
    if not data.get('name'):
        return jsonify({'error': '׳—׳¡׳¨ ׳©׳ ׳™׳•׳׳“׳×'}), 400
    if not data.get('teamIds') or len(data['teamIds']) < 1:
        return jsonify({'error': '׳ ׳ ׳׳‘׳—׳•׳¨ ׳׳₪׳—׳•׳× ׳׳™׳©׳” ׳׳—׳×'}), 400

    # mark mother as birth
    mother = next((w for w in _women if w['name'] == data['name']), None)
    if mother:
        mother['status'] = 'birth'

    birth = {
        'id':      int(time.time() * 1000),
        'name':    data['name'],
        'hood':    data.get('hood',''),
        'date':    data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'teamIds': data['teamIds'],
        'created': datetime.now().isoformat(),
    }
    _births.insert(0, birth)
    sync_to_sheets(_women)
    return jsonify(birth), 201

@app.route('/api/births/<int:bid>/replace', methods=['POST'])
def replace_team_member(bid):
    """Replace a team member who can't make it."""
    global _women, _births
    birth = next((b for b in _births if b['id'] == bid), None)
    if not birth:
        return jsonify({'error': '׳׳™׳“׳” ׳׳ ׳ ׳׳¦׳׳”'}), 404

    data = request.json
    old_id = data.get('oldId')
    if not old_id:
        return jsonify({'error': '׳—׳¡׳¨ oldId'}), 400

    # mark old member cant
    old_w = next((w for w in _women if w['id'] == old_id), None)
    if old_w:
        old_w['status'] = 'unavail'
        old_w['unavailUntil'] = (time.time() + 7 * 24 * 3600) * 1000

    # find replacement ג€” available, not in team
    replacement = next(
        (w for w in _women
         if w['status'] == 'available' and w['id'] not in birth['teamIds']),
        None
    )
    if replacement:
        birth['teamIds'] = [replacement['id'] if i == old_id else i
                            for i in birth['teamIds']]

    sync_to_sheets(_women)
    return jsonify({'birth': birth, 'replacement': replacement})

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# ROUTES ג€” SYNC
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
@app.route('/api/sync', methods=['POST'])
def sync_from_sheets():
    """Reload women from Google Sheets."""
    global _women
    data = load_from_sheets()
    if data is not None:
        _women = data
        return jsonify({'ok': True, 'count': len(_women)})
    return jsonify({'ok': False, 'message': 'Google Sheets ׳׳ ׳׳•׳’׳“׳¨'}), 200

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'women': len(_women),
        'births': len(_births),
        'sheets_enabled': SHEETS_ENABLED,
        'time': datetime.now().isoformat()
    })

# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG','0')=='1')
