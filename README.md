# 🏥 Smart Medic – AI-Powered Hospital Emergency Queue Management System

An intelligent hospital triage system that automatically prioritizes patients based on symptom severity and age risk factors, powered by Meta's LLaMA 3.3-70B AI model.

## 📌 Problem Statement

In hospital emergency wards, patients are often treated on a first-come, first-served basis — which can be life-threatening. A critical patient arriving after a normal patient may wait too long for treatment. Smart Medic solves this by automatically triaging patients using AI and a priority queue data structure.

✨ Features

- 🤖 **AI-Powered Triage** — LLaMA 3.3-70B (via Groq API) suggests possible conditions and recommended tests
- ⚡ **Automatic Priority Assignment** — 4 levels: Emergency (P0), Critical (P1), Serious (P2), Normal (P3)
- 👴 **Age-Based Risk Escalation** — Infants (0–2) and elderly (60+) automatically get higher priority
- 👨‍⚕️ **Per-Doctor Queue Management** — Separate priority queues for each doctor
- 🎫 **QR Token System** — Each patient gets a unique QR code linking to their full details
- 📱 **Real WhatsApp Notifications** — Patient receives token, wait time & recommended tests via WhatsApp (Twilio)
- 🔄 **Patient History Tracking** — Returning patients' previous visits shown to doctor
- 📊 **Live Analytics Dashboard** — Daily stats, priority breakdown, busiest hour
- 🏆 **Doctor Performance Dashboard** — Per-doctor served count and priority breakdown
- 💾 **MySQL Persistence** — Data survives server restarts
- 🌐 **Cloudflare Tunnel** — QR scan works on any phone without same WiFi

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| Backend | Python, Flask |
| Database | MySQL, flask-mysqldb |
| AI / LLM | Groq API, LLaMA 3.3-70B |
| Data Structure | heapq (Min-Heap Priority Queue) |
| Notifications | Twilio (WhatsApp API) |
| QR Code | qrcode library |
| Voice | pyttsx3 |
| Tunnel | Cloudflare Tunnel |
| Frontend | HTML, CSS (DM Sans, Google Fonts) |
| Security | python-dotenv |

📁 Project Structure

smart-medic/
│
├── app.py                  # Main Flask application
├── .env                    # Environment variables (not uploaded)
├── .gitignore
├── cloudflared.exe         # Cloudflare tunnel binary
│
├── templates/
│   ├── index.html          # Patient registration form
│   ├── token.html          # Token display after registration
│   ├── dashboard.html      # Main queue dashboard
│   ├── Doctor_dashboard.html  # Doctor-wise queue
│   ├── analytics.html      # Hospital analytics
│   ├── doctor_performance.html  # Doctor performance
│   └── patient_detail.html # QR scan page (mobile)
│
└── static/
    ├── style.css           # Base stylesheet
    └── qrcodes/            # Generated QR codes
```
 ⚙️ Installation & Setup

 1. Clone the repository
```bash
git clone https://github.com/iamarchita/Smart_medic.git
cd smart_medic
```

2. Install dependencies
```bash
pip install flask flask-mysqldb groq qrcode twilio pyttsx3 python-dotenv
```

3. Setup MySQL Database
```sql
CREATE DATABASE smartmedic;
USE smartmedic;

CREATE TABLE patients (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100),
    age          INT,
    symptoms     TEXT,
    priority     INT,
    token_id     VARCHAR(20),
    phone        VARCHAR(20),
    arrival_time VARCHAR(10),
    prediction   TEXT,
    doctor       VARCHAR(100),
    status       VARCHAR(20) DEFAULT 'waiting',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE served_log (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100),
    age            INT,
    symptoms       TEXT,
    priority       INT,
    token_id       VARCHAR(20),
    doctor         VARCHAR(100),
    serve_duration INT DEFAULT 10,
    served_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

4. Create `.env` file
```
GROQ_API_KEY=your_groq_api_key
MYSQL_PASSWORD=your_mysql_password
```
5. Update `app.py`
```python
BASE_URL = "http://127.0.0.1:5000"  # Replace with Cloudflare tunnel URL for QR
TWILIO_SID   = "your_twilio_sid"
TWILIO_TOKEN = "your_twilio_auth_token"
TWILIO_WA_FROM = "whatsapp:+14155238886"
```

6. Run the application
```bash
python app.py
```

Visit: `http://127.0.0.1:5000`

---

🌐 QR Code on Any Phone (Cloudflare Tunnel)

```bash
# Download cloudflared and run
.\cloudflared.exe tunnel --url http://localhost:5000
```

Update `BASE_URL` in `app.py` with the generated tunnel URL.

---

🚨 Priority System

| Level | Label | Examples |
|---|---|---|
| P0 | 🆘 Emergency | Cardiac arrest, not breathing |
| P1 | 🔴 Critical | Chest pain, stroke, seizure |
| P2 | 🟠 Serious | Difficulty breathing, high fever |
| P3 | 🟢 Normal | Fever, cough, minor injury |

**Age Escalation:**
- Infants (0–2 yrs): P3 → P2
- Elderly (60–74 yrs): P3 → P2
- Very Elderly (75+ yrs): P3 → P2, P2 → P1

---

📱 WhatsApp Notification Setup (Twilio)

1. Create free account at [twilio.com](https://twilio.com)
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Patient sends `join <code>` to Twilio sandbox number
4. Add Twilio credentials to `app.py`

---

🚀 Future Scope

- 📱 Patient mobile app with real-time queue tracking
- 🧠 Custom ML model trained on real hospital triage datasets
- 🏥 Multi-hospital network with load balancing
- 📊 Predictive analytics for staff scheduling
- 🔗 EHR (Electronic Health Record) integration

---
