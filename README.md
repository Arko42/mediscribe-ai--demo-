# 🏥 MediScribe AI — Clinical Documentation System

AI-powered clinical documentation. Turns patient conversations into structured SOAP notes and prescriptions in seconds.

---

## 🚀 Quick Start

### 1. Install Python (3.9+)
Download from https://python.org

### 2. Install Flask
```bash
pip install flask
```
Or:
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
```
http://127.0.0.1:5000
```

---

## 🔑 Demo Credentials

| Role   | Email              | Password   |
|--------|--------------------|------------|
| Doctor | doctor@demo.com    | doctor123  |
| Admin  | admin@demo.com     | admin123   |

---

## 📂 Project Structure

```
mediscribe/
├── app.py                  # Flask backend + AI engine + all API routes
├── requirements.txt
├── mediscribe.db           # SQLite database (auto-created on first run)
├── static/
│   └── style.css           # All styles
└── templates/
    ├── _sidebar.html       # Shared sidebar component
    ├── login.html
    ├── signup.html
    ├── dashboard.html
    ├── consultation.html   # Main feature: AI note generation
    └── history.html        # Patient records with modal view
```

---

## 🎯 Features

### ✅ Authentication
- Login / Signup with Doctor & Admin roles
- SHA-256 password hashing
- Flask session management

### ✅ Dashboard
- Live stats (patients, records, today's count)
- Recent consultations table
- Quick action tiles

### ✅ Consultation Module
- Simulated recording with auto-typing demo
- 4 demo patient scenarios (cycle with ⚡ button)
- Editable SOAP notes (Subjective / Objective / Assessment / Plan)
- Automatic prescription extraction
- Print notes to browser

### ✅ AI Engine (Rule-based NLP)
- Maps 20+ symptoms to SOAP sections
- Extracts temperature & BP from text
- Generates contextual prescriptions
- No API key required — works offline

### ✅ Database (SQLite)
- `users` — authentication
- `patients` — patient registry
- `records` — consultation history with SOAP + Rx

### ✅ History
- Searchable patient list
- Click-to-open modal with full SOAP + prescription
- Raw consultation text viewer

---

## 🧪 Demo Flow

1. Go to http://127.0.0.1:5000
2. Login with `doctor@demo.com` / `doctor123`
3. Click **New Consultation**
4. Click **⚡ Auto-fill Demo** to load a sample case
5. Click **🧠 Generate AI Notes**
6. Review SOAP notes and prescription
7. Click **💾 Save Record**
8. Go to **Patient History** to view saved records

---

## ⚙️ Optional: OpenAI Integration

In `app.py`, replace the `rule_based_nlp()` call in `/api/generate_notes` with:

```python
import openai
openai.api_key = "YOUR_KEY"

def openai_soap(text):
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "user",
            "content": f"""Convert this consultation to SOAP format as JSON:
            {{subjective, objective, assessment, plan}}
            
            Consultation: {text}"""
        }]
    )
    return json.loads(resp.choices[0].message.content)
```

---

## 🎨 Design

- **Font**: DM Sans + DM Serif Display (Google Fonts)
- **Theme**: Medical blue (#1a6bcc) + teal accent (#00c2a8)
- **Layout**: Fixed sidebar + responsive main content
- **UI**: Cards, badges, modals, toast notifications, loading overlays

---

Built with Flask + SQLite + Vanilla JS. No build tools required.
