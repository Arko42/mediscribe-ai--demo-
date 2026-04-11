from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import hashlib
import os
import json
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mediscribe_secret_key_2024'

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value) if value else {}
    except Exception:
        return {}
DB_PATH = 'mediscribe.db'

# ─── Database Setup ────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'doctor',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            contact TEXT,
            doctor_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT,
            doctor_id INTEGER,
            raw_text TEXT,
            soap_notes TEXT,
            prescription TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed demo users
    pw_doctor = hashlib.sha256('doctor123'.encode()).hexdigest()
    pw_admin  = hashlib.sha256('admin123'.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                  ('Dr. Sarah Johnson', 'doctor@demo.com', pw_doctor, 'doctor'))
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                  ('Admin User', 'admin@demo.com', pw_admin, 'admin'))
    except sqlite3.IntegrityError:
        pass

    # Seed demo patients
    c.execute("SELECT COUNT(*) FROM patients")
    if c.fetchone()[0] == 0:
        demo_patients = [
            ('Rahul Sharma', 34, 'Male', '+91-9876543210', 1),
            ('Priya Patel',  28, 'Female', '+91-9123456789', 1),
            ('Amit Kumar',   45, 'Male', '+91-9012345678', 1),
        ]
        c.executemany("INSERT INTO patients (name, age, gender, contact, doctor_id) VALUES (?,?,?,?,?)", demo_patients)

    # Seed demo records
    c.execute("SELECT COUNT(*) FROM records")
    if c.fetchone()[0] == 0:
        soap = json.dumps({
            'subjective': 'Patient reports fever for 3 days, dry cough, mild headache and body aches.',
            'objective':  'Temperature: 38.5°C. Throat mildly inflamed. No lymphadenopathy.',
            'assessment': 'Viral upper respiratory tract infection suspected.',
            'plan':       'Paracetamol 500mg TDS for 5 days. Rest and hydration. Review in 3 days if no improvement.'
        })
        rx = json.dumps([
            {'name': 'Paracetamol', 'dosage': '500mg', 'frequency': 'TDS', 'duration': '5 days'},
            {'name': 'Cetirizine',  'dosage': '10mg',  'frequency': 'OD',  'duration': '3 days'},
        ])
        c.execute("""INSERT INTO records (patient_id, patient_name, doctor_id, raw_text, soap_notes, prescription, date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (1, 'Rahul Sharma', 1,
                   'Patient has fever since 3 days, dry cough and headache. Temperature 38.5 degrees.',
                   soap, rx, '2024-12-10 10:30:00'))

    conn.commit()
    conn.close()

# ─── AI / NLP Engine ───────────────────────────────────────────────────────────

SYMPTOM_MAP = {
    'fever':       ('subjective', 'assessment'),
    'temperature': ('objective',  None),
    'cough':       ('subjective', None),
    'headache':    ('subjective', 'assessment'),
    'cold':        ('subjective', None),
    'runny nose':  ('subjective', None),
    'sore throat': ('subjective', 'objective'),
    'throat':      ('subjective', 'objective'),
    'pain':        ('subjective', 'assessment'),
    'vomiting':    ('subjective', 'assessment'),
    'nausea':      ('subjective', None),
    'diarrhea':    ('subjective', 'assessment'),
    'dizziness':   ('subjective', 'assessment'),
    'fatigue':     ('subjective', None),
    'weakness':    ('subjective', None),
    'chills':      ('subjective', None),
    'body ache':   ('subjective', None),
    'chest pain':  ('subjective', 'assessment'),
    'breathless':  ('subjective', 'assessment'),
    'rash':        ('subjective', 'objective'),
    'swelling':    ('subjective', 'objective'),
    'bp':          ('objective',  'assessment'),
    'blood pressure': ('objective', 'assessment'),
    'sugar':       ('objective',  'assessment'),
    'diabetes':    ('subjective', 'assessment'),
    'hypertension': ('subjective', 'assessment'),
}

MEDICINE_MAP = {
    'fever':        [{'name': 'Paracetamol',   'dosage': '500mg', 'frequency': 'TDS', 'duration': '5 days'}],
    'cough':        [{'name': 'Dextromethorphan', 'dosage': '15mg', 'frequency': 'BD', 'duration': '5 days'}],
    'cold':         [{'name': 'Cetirizine',    'dosage': '10mg',  'frequency': 'OD',  'duration': '3 days'}],
    'throat':       [{'name': 'Strepsils',     'dosage': '1 lozenge', 'frequency': 'Q4H', 'duration': '4 days'}],
    'pain':         [{'name': 'Ibuprofen',     'dosage': '400mg', 'frequency': 'TDS', 'duration': '3 days'}],
    'vomiting':     [{'name': 'Ondansetron',   'dosage': '4mg',   'frequency': 'BD',  'duration': '3 days'}],
    'diarrhea':     [{'name': 'ORS',           'dosage': '200ml', 'frequency': 'After each stool', 'duration': 'Until resolved'}],
    'acid':         [{'name': 'Pantoprazole',  'dosage': '40mg',  'frequency': 'OD',  'duration': '7 days'}],
    'acidity':      [{'name': 'Pantoprazole',  'dosage': '40mg',  'frequency': 'OD',  'duration': '7 days'}],
    'bp':           [{'name': 'Amlodipine',    'dosage': '5mg',   'frequency': 'OD',  'duration': '30 days'}],
    'hypertension': [{'name': 'Amlodipine',    'dosage': '5mg',   'frequency': 'OD',  'duration': '30 days'}],
    'diabetes':     [{'name': 'Metformin',     'dosage': '500mg', 'frequency': 'BD',  'duration': '30 days'}],
    'rash':         [{'name': 'Hydrocortisone cream', 'dosage': 'Apply thin layer', 'frequency': 'BD', 'duration': '7 days'}],
    'infection':    [{'name': 'Amoxicillin',   'dosage': '500mg', 'frequency': 'TDS', 'duration': '7 days'}],
}

ASSESSMENT_MAP = {
    ('fever', 'cough'):         'Viral upper respiratory tract infection suspected.',
    ('fever', 'headache'):      'Possible viral fever / dengue — monitor platelet count.',
    ('chest pain', 'breathless'): 'Cardiac or pulmonary etiology — further investigation advised.',
    ('vomiting', 'diarrhea'):   'Acute gastroenteritis suspected.',
    ('pain',):                  'Musculoskeletal pain. Rule out systemic causes.',
    ('rash',):                  'Dermatitis / allergic reaction — assess trigger.',
    ('bp',):                    'Hypertension monitoring required.',
    ('diabetes',):              'Diabetes management — monitor HbA1c.',
}

def rule_based_nlp(text):
    text_lower = text.lower()
    found_symptoms = [kw for kw in SYMPTOM_MAP if kw in text_lower]

    # Build SOAP sections
    subj_items = list({kw for kw in found_symptoms if SYMPTOM_MAP[kw][0] == 'subjective'})
    obj_items  = list({kw for kw in found_symptoms if SYMPTOM_MAP[kw][0] == 'objective'})

    # Extract numbers as objective vitals
    temp_match = re.search(r'(\d{2,3}(?:\.\d)?)\s*(?:degrees?|°|celsius|fahrenheit|temp)', text_lower)
    bp_match   = re.search(r'(\d{2,3}/\d{2,3})\s*(?:mm ?hg|bp)', text_lower)
    duration_match = re.search(r'(\d+)\s*(day|days|week|weeks|hour|hours)', text_lower)

    # Build subjective
    if subj_items:
        subjective = 'Patient reports ' + ', '.join(subj_items) + '.'
        if duration_match:
            subjective += f' Duration: {duration_match.group(1)} {duration_match.group(2)}.'
    else:
        subjective = 'Patient reports general discomfort. (Details unclear — please elaborate.)'

    # Build objective
    obj_parts = []
    if temp_match:
        obj_parts.append(f'Temperature: {temp_match.group(1)}°C')
    if bp_match:
        obj_parts.append(f'Blood Pressure: {bp_match.group(1)} mmHg')
    if obj_items:
        obj_parts.append('Clinical signs: ' + ', '.join(obj_items))
    objective = '. '.join(obj_parts) + '.' if obj_parts else 'Vitals not provided. Clinical examination pending.'

    # Build assessment
    assessment = 'General illness — further evaluation needed.'
    for key_combo, verdict in ASSESSMENT_MAP.items():
        if all(k in found_symptoms for k in key_combo):
            assessment = verdict
            break

    # Build plan & prescriptions
    meds_added = set()
    prescriptions = []
    plan_parts = []
    for symptom in found_symptoms:
        if symptom in MEDICINE_MAP:
            for med in MEDICINE_MAP[symptom]:
                if med['name'] not in meds_added:
                    meds_added.add(med['name'])
                    prescriptions.append(med)
                    plan_parts.append(f"{med['name']} {med['dosage']} {med['frequency']} × {med['duration']}")

    # Always add rest/hydration
    plan_parts.append('Adequate rest and hydration.')
    plan_parts.append('Follow-up in 3–5 days if no improvement.')

    plan = ' '.join(plan_parts) if plan_parts else 'Symptomatic treatment. Review in 3 days.'

    soap = {
        'subjective': subjective,
        'objective':  objective,
        'assessment': assessment,
        'plan':       plan,
    }
    return soap, prescriptions

# ─── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
    conn.close()
    if user:
        session['user_id']   = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        return jsonify({'success': True, 'name': user['name'], 'role': user['role']})
    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    data = request.get_json()
    name     = data.get('name', '').strip()
    email    = data.get('email', '').strip().lower()
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    role     = data.get('role', 'doctor')
    if not name or not email:
        return jsonify({'success': False, 'message': 'Name and email required'}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                     (name, email, password, role))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── Page Routes ───────────────────────────────────────────────────────────────

def require_login(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

@app.route('/dashboard')
@require_login
def dashboard():
    conn = get_db()
    records = conn.execute("""
        SELECT r.id, r.patient_name, r.date, r.soap_notes
        FROM records r WHERE r.doctor_id=?
        ORDER BY r.date DESC LIMIT 5
    """, (session['user_id'],)).fetchall()
    patients = conn.execute("SELECT COUNT(*) as c FROM patients WHERE doctor_id=?",
                            (session['user_id'],)).fetchone()
    total_records = conn.execute("SELECT COUNT(*) as c FROM records WHERE doctor_id=?",
                                 (session['user_id'],)).fetchone()
    conn.close()
    return render_template('dashboard.html',
                           user_name=session['user_name'],
                           user_role=session['user_role'],
                           records=records,
                           patient_count=patients['c'],
                           record_count=total_records['c'])

@app.route('/consultation')
@require_login
def consultation():
    conn = get_db()
    patients = conn.execute("SELECT * FROM patients WHERE doctor_id=? ORDER BY name",
                            (session['user_id'],)).fetchall()
    conn.close()
    return render_template('consultation.html',
                           user_name=session['user_name'],
                           patients=patients)

@app.route('/history')
@require_login
def history():
    conn = get_db()
    records = conn.execute("""
        SELECT r.id, r.patient_name, r.date, r.soap_notes, r.prescription
        FROM records r WHERE r.doctor_id=?
        ORDER BY r.date DESC
    """, (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html',
                           user_name=session['user_name'],
                           records=records)

# ─── API Routes ────────────────────────────────────────────────────────────────

@app.route('/api/generate_notes', methods=['POST'])
@require_login
def generate_notes():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'No text provided'}), 400
    soap, prescriptions = rule_based_nlp(text)
    return jsonify({'success': True, 'soap': soap, 'prescriptions': prescriptions})

@app.route('/api/save_record', methods=['POST'])
@require_login
def save_record():
    data = request.get_json()
    patient_name = data.get('patient_name', 'Unknown Patient')
    raw_text     = data.get('raw_text', '')
    soap         = data.get('soap', {})
    prescriptions = data.get('prescriptions', [])

    # Find or create patient
    conn = get_db()
    patient = conn.execute("SELECT id FROM patients WHERE name=? AND doctor_id=?",
                           (patient_name, session['user_id'])).fetchone()
    if not patient:
        conn.execute("INSERT INTO patients (name, doctor_id) VALUES (?, ?)",
                     (patient_name, session['user_id']))
        conn.commit()
        patient = conn.execute("SELECT id FROM patients WHERE name=? AND doctor_id=?",
                               (patient_name, session['user_id'])).fetchone()

    conn.execute("""INSERT INTO records (patient_id, patient_name, doctor_id, raw_text, soap_notes, prescription, date)
                    VALUES (?,?,?,?,?,?,?)""",
                 (patient['id'], patient_name, session['user_id'],
                  raw_text, json.dumps(soap), json.dumps(prescriptions),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Record saved successfully!'})

@app.route('/api/record/<int:record_id>')
@require_login
def get_record(record_id):
    conn = get_db()
    record = conn.execute("SELECT * FROM records WHERE id=? AND doctor_id=?",
                          (record_id, session['user_id'])).fetchone()
    conn.close()
    if not record:
        return jsonify({'success': False, 'message': 'Record not found'}), 404
    return jsonify({
        'success': True,
        'record': {
            'id':           record['id'],
            'patient_name': record['patient_name'],
            'date':         record['date'],
            'raw_text':     record['raw_text'],
            'soap':         json.loads(record['soap_notes'] or '{}'),
            'prescriptions': json.loads(record['prescription'] or '[]'),
        }
    })

@app.route('/api/patients')
@require_login
def get_patients():
    conn = get_db()
    patients = conn.execute("SELECT * FROM patients WHERE doctor_id=?",
                            (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(p) for p in patients])

@app.route('/api/stats')
@require_login
def get_stats():
    conn = get_db()
    patient_count = conn.execute("SELECT COUNT(*) FROM patients WHERE doctor_id=?",
                                 (session['user_id'],)).fetchone()[0]
    record_count  = conn.execute("SELECT COUNT(*) FROM records WHERE doctor_id=?",
                                 (session['user_id'],)).fetchone()[0]
    today_count   = conn.execute(
        "SELECT COUNT(*) FROM records WHERE doctor_id=? AND date LIKE ?",
        (session['user_id'], datetime.now().strftime('%Y-%m-%d') + '%')).fetchone()[0]
    conn.close()
    return jsonify({'patients': patient_count, 'records': record_count, 'today': today_count})

if __name__ == '__main__':
    init_db()
    print("\n" + "="*55)
    print("  🏥  MediScribe AI — Clinical Documentation System")
    print("="*55)
    print("  URL   : http://127.0.0.1:5000")
    print("  Demo Doctor : doctor@demo.com / doctor123")
    print("  Demo Admin  : admin@demo.com  / admin123")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)
