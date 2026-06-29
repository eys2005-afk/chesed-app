"""
סבב חסד — גרעין תורני עמיחי רמלה
Flask Backend + Google Sheets sync
"""

import os, json, time, ssl, threading
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

# מיפוי רחובות → שכונות ברמלה
STREET_TO_HOOD = {
    # הרדוף
    'הרדוף':            'הרדוף',
    "אצ\"ל":            'הרדוף',
    'אצל':               'הרדוף',
    # עמישב (= אג"ש / ביל"ו / הגטו)
    'מסדה':              'עמישב',
    'יוספטל':            'שכונות',
    'שלמה בן יוסף':     'עמישב',
    'בן יוסף':           'עמישב',
    'אליהו הנביא':       'עמישב',
    'שמואל הנביא':       'עמישב',
    'משה שמש':           'עמישב',
    'הרב הרצוג':         'עמישב',
    'הרצוג':             'עמישב',
    'אהרון בן יוסף':     'עמישב',
    'שכונת עמישב':       'עמישב',
    # קרית האמונים
    'יוסי בנאי':         'קרית האמונים',
    # נאות שמיר
    'יהודה עמיחי':       'נאות שמיר',
    'נאות שמיר':         'נאות שמיר',
    # רמבלס
    'יגאל ידין':         'רמבלס',
    # שכונות — כל השאר
    'עמיחי':             'שכונות',
    'בר אילן':           'שכונות',
    'בר-אילן':           'שכונות',
    'ויצמן':             'שכונות',
    'הרצל':              'שכונות',
    'בן צבי':            'שכונות',
    'גורדון':            'שכונות',
    'בורוכוב':           'שכונות',
    'הרב קוק':           'שכונות',
    'הרב מימון':         'שכונות',
    'הרב פינס':          'שכונות',
    'שבזי':              'שכונות',
    'שרת':               'שכונות',
    'יבנה':              'שכונות',
    'צה"ל':              'שכונות',
    'צהל':               'שכונות',
    'נתן אלבז':          'שכונות',
    'המגדל הלבן':        'שכונות',
    'ישראל פרנקל':       'שכונות',
    'סשה ארגוב':         'שכונות',
    'איפרגן':            'שכונות',
    'אברהם הלל':         'שכונות',
    'מנחם דניאל':        'שכונות',
    'ביאליק':            'עמישב',
    'וילנא':             'שכונות',
    'וילנה':             'שכונות',
    'יחזקאל וכיל':       'שכונות',
    'מאיר בינט':         'שכונות',
    'משה לוי':           'שכונות',
    'יגאל אלון':         'שכונות',
    'דני מס':            'שכונות',
    'ויתקין':            'שכונות',
    'בן גוריון':         'שכונות',
}

def detect_hood(addr):
    if not addr:
        return 'שכונות'
    for street, hood in STREET_TO_HOOD.items():
        if street in addr:
            return hood
    return 'שכונות'

# ══════════════════════════════════════════
# GOOGLE SHEETS (optional — set env vars to enable)
# ══════════════════════════════════════════
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
        if 'נשים' not in titles:
            sh.add_worksheet(title='נשים', rows=500, cols=10)
        if 'לידות' not in titles:
            sh.add_worksheet(title='לידות', rows=500, cols=10)
        if 'גיבוי' not in titles:
            sh.add_worksheet(title='גיבוי', rows=10, cols=2)
        return gc, sh
    except Exception as e:
        print(f"Sheets error: {e}")
        return None, None

def sync_to_sheets_bg(women_data):
    threading.Thread(target=sync_to_sheets, args=(list(women_data),), daemon=True).start()

def sync_to_sheets(women_data):
    """Write women list to Google Sheets (Women tab)."""
    _, sh = get_sheets_client()
    if not sh:
        return
    try:
        ws = sh.worksheet('נשים')
        ws.clear()
        ws.append_row(['ID','שם','טלפון','שכונה','כתובת','סטטוס','לא זמינה עד'])
        for w in women_data:
            until = ''
            if w.get('unavailUntil'):
                until = datetime.fromtimestamp(w['unavailUntil']/1000).strftime('%d/%m/%Y %H:%M')
            ws.append_row([w['id'], w['name'], w['phone'], w['hood'],
                           w.get('addr',''), w['status'], until])
    except Exception as e:
        print(f"Sheets sync error: {e}")

def save_app_data_bg():
    threading.Thread(target=_save_app_data, daemon=True).start()

def _save_app_data():
    """Persist births + women statuses to גיבוי sheet so data survives redeploys."""
    _, sh = get_sheets_client()
    if not sh:
        return
    try:
        ws = sh.worksheet('גיבוי')
        ws.clear()
        # row 1: births JSON
        ws.append_row(['births', json.dumps(_births, ensure_ascii=False)])
        # row 2: status overrides {id: {status, unavailUntil}}
        statuses = {str(w['id']): {'status': w['status'], 'unavailUntil': w.get('unavailUntil')}
                    for w in _women if w['status'] != 'available' or w.get('unavailUntil')}
        ws.append_row(['statuses', json.dumps(statuses, ensure_ascii=False)])
    except Exception as e:
        print(f"גיבוי save error: {e}")

def load_app_data():
    """Load persisted births + status overrides on startup."""
    global _births, _women
    _, sh = get_sheets_client()
    if not sh:
        return
    try:
        ws = sh.worksheet('גיבוי')
        rows = ws.get_all_values()
        data = {r[0]: r[1] for r in rows if len(r) >= 2}
        if 'births' in data and data['births']:
            _births = json.loads(data['births'])
        if 'statuses' in data and data['statuses']:
            statuses = json.loads(data['statuses'])
            for w in _women:
                s = statuses.get(str(w['id']))
                if s:
                    w['status'] = s['status']
                    w['unavailUntil'] = s.get('unavailUntil')
        print(f"גיבוי loaded: {len(_births)} births, {len([w for w in _women if w['status']!='available'])} non-available women")
    except Exception as e:
        print(f"גיבוי load error: {e}")

def load_cooking_history():
    """Load last cooking date per family from תאריך בישול אחרון tab.
    Returns dict: family_name -> last_cooked (DD/MM/YYYY string)."""
    _, sh = get_sheets_client()
    if not sh:
        return {}
    try:
        ws = sh.worksheet('תאריך בישול אחרון')
        rows = ws.get_all_values()
        result = {}
        for row in rows[1:]:
            name = row[0].strip() if len(row) > 0 else ''
            date = row[1].strip() if len(row) > 1 else ''
            if name and date:
                result[name] = date
        return result
    except Exception as e:
        print(f"Cooking history load error: {e}")
        return {}

def enrich_phones_from_contact_tab(women_list):
    """One-time: fill missing phones from דף קשר גרעין tab by name matching."""
    _, sh = get_sheets_client()
    if not sh:
        return
    try:
        ws = sh.worksheet('דף קשר גרעין')
        rows = ws.get_all_values()
        # col 0 = name (family + husband + וwife), col 3 (D) = נייד אשה
        contact_map = []
        for row in rows[1:]:
            full_name = row[0].strip() if len(row) > 0 else ''
            phone     = row[3].strip() if len(row) > 3 else ''
            if full_name and phone:
                words = set(full_name.split())
                # strip ו prefix (e.g. ואביה → אביה) so names match
                words_clean = {w[1:] if w.startswith('ו') and len(w) > 1 else w for w in words}
                contact_map.append((words | words_clean, phone))

        filled = 0
        for w in women_list:
            if w['phone']:
                continue
            w_words = set(w['name'].split())
            for contact_words, phone in contact_map:
                # match if at least 2 words overlap (handles different name orders)
                if len(w_words & contact_words) >= 2:
                    w['phone'] = phone
                    filled += 1
                    break
            else:
                # fallback: match if any single word overlaps (for short names)
                if len(w_words) == 1:
                    for contact_words, phone in contact_map:
                        if w_words & contact_words:
                            w['phone'] = phone
                            filled += 1
                            break
        print(f"Phone enrichment: filled {filled} missing phones from דף קשר גרעין")
    except Exception as e:
        print(f"Phone enrichment error: {e}")

def load_from_sheets():
    """Load women list from רשימת משפחות הגרעין + cooking history."""
    _, sh = get_sheets_client()
    if not sh:
        return None
    try:
        ws = sh.worksheet('רשימת משפחות הגרעין')
        rows = ws.get_all_values()
        if not rows:
            return None

        result = []
        wid = 1
        for row in rows[1:]:
            last_cooked = row[0].strip()  if len(row) > 0 else ''
            name  = row[1].strip()        if len(row) > 1 else ''
            phone = row[4].strip()        if len(row) > 4 else ''
            hood  = row[5].strip()        if len(row) > 5 else ''
            addr  = row[6].strip()        if len(row) > 6 else ''
            delete= row[8].strip()        if len(row) > 8 else ''
            if not name or delete.startswith('מחק'):
                continue
            if not hood:
                hood = detect_hood(addr)
            # 01/01/2000 is the sheet's sentinel for "never cooked" → treat as highest priority
            if last_cooked == '01/01/2000':
                last_cooked = ''
            result.append({
                'id':           wid,
                'name':         name,
                'phone':        phone,
                'hood':         hood,
                'addr':         addr,
                'status':       'available',
                'unavailUntil': None,
                'lastCooked':   last_cooked,
            })
            wid += 1
        return result
    except Exception as e:
        print(f"Sheets load error: {e}")
        return None

# ══════════════════════════════════════════
# IN-MEMORY DATA (fallback when no Sheets)
# ══════════════════════════════════════════
_women = [
    {'id':1,'name':'רבקה לוי',   'phone':'050-1234567','hood':'עמישב',     'addr':'הרצל 12',    'status':'available','unavailUntil':None},
    {'id':2,'name':'מרים אברהם', 'phone':'052-9876543','hood':'שכונות',    'addr':'בן גוריון 3','status':'available','unavailUntil':None},
    {'id':3,'name':'דינה שפירא', 'phone':'054-1112233','hood':'נאות שמיר', 'addr':'הנביאים 7',  'status':'available','unavailUntil':None},
    {'id':4,'name':'לאה גולדברג','phone':'053-4445566','hood':'רמבלס',     'addr':'הפלמח 2',    'status':'available','unavailUntil':None},
    {'id':5,'name':'חנה רוזן',   'phone':'050-7778899','hood':'הרדוף',     'addr':'הדקל 9',     'status':'available','unavailUntil':None},
    {'id':6,'name':'שרה כהן',    'phone':'052-3334455','hood':'עמישב',     'addr':'ויצמן 4',    'status':'available','unavailUntil':None},
    {'id':7,'name':'נעמי ברק',   'phone':'057-1122334','hood':'שכונות',    'addr':'הנשיא 11',   'status':'available','unavailUntil':None},
    {'id':8,'name':'רחל פרץ',    'phone':'054-6667788','hood':'נאות שמיר', 'addr':'הגפן 5',     'status':'available','unavailUntil':None},
    {'id':9,'name':'יעל מזרחי',  'phone':'050-9998877','hood':'רמבלס',     'addr':'הזית 8',     'status':'available','unavailUntil':None},
    {'id':10,'name':'תמר שלום',  'phone':'052-1113322','hood':'הרדוף',     'addr':'הברוש 3',    'status':'available','unavailUntil':None},
]

_births = []

# Load real women data from Sheets on startup
_loaded = load_from_sheets()
if _loaded:
    _women = _loaded
    enrich_phones_from_contact_tab(_women)

# Restore births + status overrides from previous session
load_app_data()

def check_unavail_expiry(women):
    now_ms = time.time() * 1000
    for w in women:
        if w['status'] == 'unavail' and w.get('unavailUntil') and now_ms > w['unavailUntil']:
            w['status'] = 'available'
            w['unavailUntil'] = None
    return women

# ══════════════════════════════════════════
# ROUTES — STATIC
# ══════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ══════════════════════════════════════════
# ROUTES — WOMEN
# ══════════════════════════════════════════
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
        return jsonify({'error': 'חסרים שדות חובה'}), 400
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
    sync_to_sheets_bg(_women)
    return jsonify(woman), 201

@app.route('/api/women/<int:wid>', methods=['PATCH'])
def update_woman(wid):
    global _women
    woman = next((w for w in _women if w['id'] == wid), None)
    if not woman:
        return jsonify({'error': 'לא נמצאה'}), 404
    data = request.json
    allowed = ['name','phone','hood','addr','status','unavailUntil']
    for key in allowed:
        if key in data:
            woman[key] = data[key]
    sync_to_sheets_bg(_women)
    save_app_data_bg()
    return jsonify(woman)

@app.route('/api/women/<int:wid>/cant', methods=['POST'])
def mark_cant(wid):
    """Mark woman as unavailable for 7 days."""
    global _women
    woman = next((w for w in _women if w['id'] == wid), None)
    if not woman:
        return jsonify({'error': 'לא נמצאה'}), 404
    woman['status'] = 'unavail'
    woman['unavailUntil'] = (time.time() + 7 * 24 * 3600) * 1000
    sync_to_sheets_bg(_women)
    save_app_data_bg()
    return jsonify(woman)

# ══════════════════════════════════════════
# ROUTES — BIRTHS
# ══════════════════════════════════════════
@app.route('/api/births', methods=['GET'])
def get_births():
    return jsonify(_births)

@app.route('/api/births', methods=['POST'])
def add_birth():
    global _women, _births
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'חסר שם יולדת'}), 400
    if not data.get('teamIds') or len(data['teamIds']) < 1:
        return jsonify({'error': 'נא לבחור לפחות אישה אחת'}), 400

    # mark mother as birth
    mother = next((w for w in _women if w['name'] == data['name']), None)
    if mother:
        mother['status'] = 'birth'

    # mark team members as cooking so they won't appear in future suggestions
    for w in _women:
        if w['id'] in data['teamIds']:
            w['status'] = 'cooking'

    team_members = [
        {'id': w['id'], 'name': w['name'], 'phone': w.get('phone',''), 'hood': w.get('hood',''), 'addr': w.get('addr','')}
        for w in _women if w['id'] in data['teamIds']
    ]
    birth = {
        'id':      int(time.time() * 1000),
        'name':    data['name'],
        'hood':    data.get('hood',''),
        'date':    data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'teamIds': data['teamIds'],
        'team':    team_members,
        'addr':        data.get('addr', next((w.get('addr','') for w in _women if w['name']==data['name']), '')),
        'motherPhone': next((w.get('phone','') for w in _women if w['name']==data['name']), ''),
        'created': datetime.now().isoformat(),
    }
    _births.insert(0, birth)
    sync_to_sheets_bg(_women)
    save_app_data_bg()
    return jsonify(birth), 201

@app.route('/api/births/<int:bid>', methods=['DELETE'])
def delete_birth(bid):
    global _births, _women
    birth = next((b for b in _births if b['id'] == bid), None)
    if birth:
        # restore team members to available
        for w in _women:
            if w['id'] in birth.get('teamIds', []) and w['status'] == 'cooking':
                w['status'] = 'available'
        # restore mother
        mother = next((w for w in _women if w['name'] == birth['name']), None)
        if mother and mother['status'] == 'birth':
            mother['status'] = 'available'
    _births = [b for b in _births if b['id'] != bid]
    save_app_data_bg()
    return jsonify({'ok': True})

@app.route('/api/births/<int:bid>/replace', methods=['POST'])
def replace_team_member(bid):
    """Replace a team member who can't make it."""
    global _women, _births
    birth = next((b for b in _births if b['id'] == bid), None)
    if not birth:
        return jsonify({'error': 'לידה לא נמצאה'}), 404

    data = request.json
    old_id = data.get('oldId')
    days = int(data.get('days', 7))
    if not old_id:
        return jsonify({'error': 'חסר oldId'}), 400

    # mark old member cant
    old_w = next((w for w in _women if w['id'] == old_id), None)
    if old_w:
        old_w['status'] = 'unavail'
        old_w['unavailUntil'] = (time.time() + days * 24 * 3600) * 1000

    # find replacement — available, not in team
    replacement = next(
        (w for w in _women
         if w['status'] == 'available' and w['id'] not in birth['teamIds']),
        None
    )
    if replacement:
        replacement['status'] = 'cooking'
        birth['teamIds'] = [replacement['id'] if i == old_id else i
                            for i in birth['teamIds']]
        birth['team'] = [
            {'id': w['id'], 'name': w['name'], 'phone': w.get('phone',''), 'hood': w.get('hood',''), 'addr': w.get('addr','')}
            for w in _women if w['id'] in birth['teamIds']
        ]

    sync_to_sheets_bg(_women)
    save_app_data_bg()
    return jsonify({'birth': birth, 'replacement': replacement})

# ══════════════════════════════════════════
# ROUTES — SUGGEST TEAM
# ══════════════════════════════════════════
@app.route('/api/suggest', methods=['GET'])
def suggest_team():
    """Return 5 available women sorted by oldest last-cooked date."""
    global _women
    _women = check_unavail_expiry(_women)
    exclude_ids = request.args.getlist('exclude', type=int)
    hood_filter = request.args.get('hood', '')

    def sort_key(w):
        d = w.get('lastCooked', '')
        if not d:
            return '01/01/2000'  # never cooked → highest priority
        # convert DD/MM/YYYY to YYYY/MM/DD for sorting
        try:
            parts = d.split('/')
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        except:
            return '01/01/2000'

    available = [w for w in _women
                 if w['status'] == 'available'
                 and w['id'] not in exclude_ids]

    # prefer same neighborhood if specified
    if hood_filter:
        same_hood = [w for w in available if w.get('hood') == hood_filter]
        other = [w for w in available if w.get('hood') != hood_filter]
        available = sorted(same_hood, key=sort_key) + sorted(other, key=sort_key)
    else:
        available = sorted(available, key=sort_key)

    limit = request.args.get('limit', 5, type=int)
    return jsonify(available[:limit])

# ══════════════════════════════════════════
# ROUTES — SYNC
# ══════════════════════════════════════════
@app.route('/api/sync', methods=['POST'])
def sync_from_sheets():
    """Reload women from Google Sheets."""
    global _women
    data = load_from_sheets()
    if data is not None:
        _women = data
        return jsonify({'ok': True, 'count': len(_women)})
    return jsonify({'ok': False, 'message': 'Google Sheets לא מוגדר'}), 200

@app.route('/api/debug-phones', methods=['GET'])
def debug_phones():
    _, sh = get_sheets_client()
    if not sh:
        return jsonify({'error': 'no sheets'})
    try:
        tabs = [w.title for w in sh.worksheets()]
        contact_tab = next((w for w in sh.worksheets() if 'קשר' in w.title), None)
        if not contact_tab:
            return jsonify({'tabs': tabs, 'error': 'no contact tab found'})
        rows = contact_tab.get_all_values()
        missing_phones = [w['name'] for w in _women if not w['phone']]
        with_phones = [{'name': w['name'], 'phone': w['phone']} for w in _women if w['phone']][:5]
        return jsonify({
            'tab_name': contact_tab.title,
            'header': rows[0] if rows else [],
            'sample_rows': rows[1:4],
            'total_contact_rows': len(rows) - 1,
            'missing_phones_count': len(missing_phones),
            'missing_sample': missing_phones[:10],
            'with_phones_sample': with_phones,
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/health', methods=['GET'])
def health():
    sa_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '')
    return jsonify({
        'status': 'ok',
        'women': len(_women),
        'births': len(_births),
        'sheets_enabled': SHEETS_ENABLED,
        'sa_json_len': len(sa_json),
        'sa_json_start': sa_json[:10] if sa_json else '',
        'time': datetime.now().isoformat()
    })

# ══════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG','0')=='1')
