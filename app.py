from flask import Flask, render_template, request, redirect
import heapq
import qrcode
import uuid
import os
from flask_mysqldb import MySQL
from twilio.rest import Client
from dotenv import load_dotenv
load_dotenv()
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_WA_FROM = os.getenv("TWILIO_WA_FROM")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
BASE_URL = os.getenv("BASE_URL")

app = Flask(__name__)

app.config['MYSQL_HOST']     = 'localhost'
app.config['MYSQL_USER']     = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB']       = 'smartmedic'
mysql = MySQL(app)


# Priority Queue
queue = []
DOCTORS = ["Dr. Sharma", "Dr. Mehta", "Dr. Patel"]
queues  = {doctor: [] for doctor in DOCTORS}


def load_doctor_queues():
    global queues
    queues = {doctor: [] for doctor in DOCTORS}
    try:
        with app.app_context():
            cur = mysql.connection.cursor()
            cur.execute("""SELECT priority, name, age, symptoms, arrival_time,
                                  token_id, prediction, doctor
                           FROM patients
                           WHERE status = 'waiting'
                           ORDER BY priority ASC, created_at ASC""")
            rows = cur.fetchall()
            cur.close()
            for row in rows:
                doctor = row[7]
                if doctor in queues:
                    heapq.heappush(queues[doctor],
                                   (row[0], row[1], row[2], row[3],
                                    row[4], row[5], row[6]))
            print(f"✅ Queues loaded — {sum(len(q) for q in queues.values())} patients")
    except Exception as e:
        print(f"Queue load error: {e}")

#watsapp message 
def send_whatsapp(to_number, patient_name, token_id, priority_label, wait_mins, prediction=""):
    try:
        if not to_number or len(to_number) < 10:
            print("No valid phone number")
            return

        if not to_number.startswith('+'):
            to_number = '+91' + to_number.strip()

        client = Client(TWILIO_SID, TWILIO_TOKEN)

        # Prediction se recommended tests nikalo
        tests_line = ""
        if prediction and "Recommended Tests:" in prediction:
            tests = prediction.split("Recommended Tests:")[-1].strip()
            tests_line = f"🔬 *Recommended Tests:*\n{tests}\n_(Please arrange these before your turn)_\n\n"

        message = (
            f"🏥 *Smart Medic – Registration Confirmed!*\n\n"
            f"👤 *Patient:* {patient_name}\n"
            f"🎫 *Token:* {token_id}\n"
            f"🚨 *Priority:* {priority_label}\n"
            f"⏱ *Est. Wait:* ~{wait_mins} mins\n\n"
            f"{tests_line}"
            f"📸 *Please take a screenshot of your QR code "
            f"from the registration screen and show it to the doctor.*\n\n"
            f"_Please be ready when your token is called._\n"
            f"_Smart Medic – Emergency Queue Manager_"
        )

        client.messages.create(
            body=message,
            from_=TWILIO_WA_FROM,
            to=f"whatsapp:{to_number}"
        )
        print(f"✅ WhatsApp sent to {to_number}")

    except Exception as e:
        print(f"WhatsApp Error: {e}")

# ─────────────────────────────────────────────
#  AI DISEASE PREDICTION (Groq - Free)
# ─────────────────────────────────────────────
from groq import Groq


def get_disease_prediction(symptoms, age):
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""You are a medical triage assistant.
Patient age: {age}
Symptoms: {symptoms}

Reply in EXACTLY this format, nothing else, no extra text:
Possible Conditions: [2-3 conditions separated by comma]
Recommended Tests: [3-4 tests separated by comma]"""
            }],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Prediction error: {e}")
        return "Prediction unavailable"


# for generating tokens 

def generate_qr_token(patient_name, token_id, age="", symptoms="", priority_label="", doctor=""):
    data = f"{BASE_URL}/patient/{token_id}"
    img = qrcode.make(data)
    folder = os.path.join('static', 'qrcodes')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{token_id}.png")
    img.save(path)
    return path

# ─────────────────────────────────────────────
#  SYMPTOM KEYWORD BANKS  (base priority)
# ─────────────────────────────────────────────
PRIORITY_0_KEYWORDS = [
    "heart attack", "cardiac arrest", "not breathing", "no breath",
    "stopped breathing", "unconscious", "unresponsive", "severe bleeding",
    "uncontrolled bleeding", "anaphylaxis", "anaphylactic", "major accident",
    "polytrauma", "eclampsia", "aortic dissection", "septic shock",
]


PRIORITY_1_KEYWORDS = [
    # Cardiac
    "heart attack", "cardiac arrest", "chest pain", "chest tightness",
    "heart failure", "myocardial", "palpitation severe",
    # Neurological
    "stroke", "unconscious", "unresponsive", "seizure", "convulsion",
    "status epilepticus", "coma",
    # Respiratory
    "not breathing", "stopped breathing", "respiratory failure",
    "cant breathe", "can't breathe", "no breath", "airway blocked",
    "tension pneumothorax",
    # Circulation / Bleeding
    "severe bleeding", "uncontrolled bleeding", "massive hemorrhage",
    "aortic dissection", "septic shock", "anaphylaxis", "anaphylactic",
    # Trauma
    "polytrauma", "major accident", "head trauma", "spinal injury",
    "severe burn",
    # Other critical
    "overdose", "poisoning", "eclampsia", "diabetic coma", "dka severe",
]

PRIORITY_2_KEYWORDS = [
    # Cardiac / Vascular
    "chest discomfort", "chest pressure", "hypertensive crisis",
    "high blood pressure severe", "pulmonary embolism", "blood clot",
    "ectopic pregnancy", "aortic",
    # Neurological
    "severe headache", "sudden headache", "head injury", "loss of consciousness",
    "confusion", "altered mental", "meningitis",
    # Respiratory
    "difficulty breathing", "breathing difficulty", "shortness of breath",
    "asthma attack", "wheezing severe", "low oxygen", "pneumonia severe",
    # Infection / Fever
    "high fever", "fever with confusion", "fever with rash",
    "sepsis", "meningococcal",
    # Abdominal
    "severe abdominal pain", "appendicitis", "bowel obstruction",
    "gastrointestinal bleed", "gi bleed", "vomiting blood",
    "abdominal rigidity",
    # Trauma / Injury
    "open fracture", "compound fracture", "dislocation", "spinal",
    "eye injury", "chemical burn eye", "moderate burn",
    # Other serious
    "kidney failure", "renal failure", "liver failure", "jaundice severe",
    "kidney stone severe", "ectopic",
    # Mental health emergencies
    "suicidal", "self harm", "overdose medication",
]

PRIORITY_3_KEYWORDS = [
    # Mild infections
    "fever", "mild fever", "cold", "flu", "cough", "sore throat",
    "ear infection", "ear pain", "throat infection", "tonsillitis",
    "conjunctivitis", "eye infection", "pink eye",
    # Minor injuries
    "minor cut", "laceration", "sprain", "minor fracture",
    "bruise", "contusion", "minor burn",
    # GI
    "nausea", "vomiting", "diarrhea", "constipation",
    "stomach ache", "mild abdominal pain", "indigestion", "acidity",
    # Musculoskeletal
    "back pain", "muscle pain", "joint pain", "neck pain", "headache",
    "migraine", "body ache",
    # Skin
    "rash", "skin irritation", "itching", "allergy mild", "urticaria",
    # Urological
    "uti", "urinary infection", "burning urination", "frequent urination",
    # Dental
    "dental pain", "toothache",
    # Respiratory mild
    "mild asthma", "mild breathing", "runny nose", "congestion",
    # Other
    "anxiety mild", "dizziness mild", "weakness mild",
]


# ─────────────────────────────────────────────
#  AGE RISK ESCALATION RULES
# ─────────────────────────────────────────────
#
#  Infants (0–2 yrs) : immune system immature → escalate P3 → P2
#  Children (3–12)   : generally resilient, no change
#  Elderly (60–74)   : higher comorbidity risk → P3 → P2
#  Very elderly (75+): high fragility → P3 → P2, and P2 → P1
#
def apply_age_escalation(base_priority: int, age: int) -> int:
    """
    Escalates priority based on patient age risk factors.
    Never de-escalates (age cannot make a critical case less urgent).
    """
    if age < 0 or age > 130:
        return base_priority  # invalid age, no change

    # Infants (0–2): fragile, immune immature
    if age <= 2:
        if base_priority == 3:
            return 2  # any "normal" case → serious for infants

    # Elderly (60–74): higher comorbidity, slower recovery
    elif 60 <= age <= 74:
        if base_priority == 3:
            return 2  # normal → serious

    # Very elderly (75+): high fragility, multiple organ vulnerability
    elif age >= 75:
        if base_priority == 3:
            return 2   # normal → serious
        if base_priority == 2:
            return 1   # serious → critical

    return base_priority


# ─────────────────────────────────────────────
#  KEYWORD MATCHING HELPER
# ─────────────────────────────────────────────

def match_keywords(text: str, keyword_list: list) -> bool:
    """Returns True if any keyword from the list is found in text."""
    for keyword in keyword_list:
        if keyword in text:
            return True
    return False


# ─────────────────────────────────────────────
#  MAIN PRIORITY DETECTION FUNCTION
# ─────────────────────────────────────────────

def detect_priority(symptoms: str, age: int) -> dict:
    """
    Detects patient priority based on symptoms and age.

    Args:
        symptoms (str): Free-text symptom description from receptionist
        age      (int): Patient age in years

    Returns:
        dict: {
            "priority"       : int  (1=Critical, 2=Serious, 3=Normal),
            "label"          : str  ("Critical" / "Serious" / "Normal"),
            "age_escalated"  : bool (True if age caused escalation),
            "reason"         : str  (short explanation)
        }
    """
    symptoms_lower = symptoms.lower().strip()

    # ── Step 1: Determine base priority from symptoms ──

    if match_keywords(symptoms_lower, PRIORITY_0_KEYWORDS):
       base_priority = 0      # extreme emergency → top of queue instantly
    elif match_keywords(symptoms_lower, PRIORITY_1_KEYWORDS):
        base_priority = 1
    elif match_keywords(symptoms_lower, PRIORITY_2_KEYWORDS):
        base_priority = 2
    else:
        base_priority = 3  # default to normal if no keywords match

    # ── Step 2: Apply age-based escalation ──
    final_priority = apply_age_escalation(base_priority, age)
    age_escalated  = final_priority != base_priority

    # ── Step 3: Build response ──
    labels = {0: "Emergency", 1: "Critical", 2: "Serious", 3: "Normal"}

    if age_escalated:
        reason = (
            f"Symptoms suggest priority {base_priority} ({labels[base_priority]}), "
            f"but escalated to {final_priority} ({labels[final_priority]}) "
            f"due to patient age ({age} yrs)."
        )
    else:
        reason = f"Assigned priority {final_priority} ({labels[final_priority]}) based on symptoms."

    return {
        "priority"     : final_priority,
        "label"        : labels[final_priority],
        "age_escalated": age_escalated,
        "reason"       : reason,
    }


# ─────────────────────────────────────────────
#  PRIORITY QUEUE INTEGRATION HELPER
# ─────────────────────────────────────────────

def get_queue_weight(priority: int, arrival_order: int) -> float:
    """
    Returns a sortable weight for the priority queue.
    Lower weight = treated first.

    Uses arrival_order as a tiebreaker so patients with the
    same priority are seen in FIFO order.

    Args:
        priority      (int): 1, 2, or 3
        arrival_order (int): incremental counter (1, 2, 3, ...)
    """
    return priority * 10000 + arrival_order


# Home page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_patient', methods=['POST'])
def add_patient():
    name     = request.form['name']
    age      = int(request.form['age'])
    symptoms = request.form['symptoms']
    phone    = request.form.get('phone', '')
    time_val = request.form['time']
    doctor   = request.form.get('doctor', DOCTORS[0])
    
    # Doctor None na ho
    if not doctor or doctor not in DOCTORS:
        doctor = DOCTORS[0]

    # Duplicate check — same name + same symptoms already waiting
    cur_check = mysql.connection.cursor()
    cur_check.execute("""SELECT token_id, priority FROM patients 
                         WHERE name = %s 
                         AND symptoms = %s
                         AND status = 'waiting'
                         LIMIT 1""", (name, symptoms))
    existing = cur_check.fetchone()
    cur_check.close()

    if existing is not None:
        labels = {0: "Emergency", 1: "Critical", 2: "Serious", 3: "Normal"}
        if phone:
            wait_mins = len(queues[doctor]) * 10
            send_whatsapp(phone, name, existing[0],
                          labels[existing[1]], wait_mins, "")
        return render_template('token.html',
                               name=name,
                               token=existing[0],
                               priority=labels[existing[1]],
                               qr_image=f"qrcodes/{existing[0]}.png")

    # Naya patient
    result     = detect_priority(symptoms, age)
    priority   = result['priority']
    token_id   = "SM-" + str(uuid.uuid4())[:4].upper()
    prediction = get_disease_prediction(symptoms, age)

    generate_qr_token(name, token_id, age, symptoms, result['label'], doctor)

    cur = mysql.connection.cursor()
    cur.execute("""INSERT INTO patients 
                   (name, age, symptoms, priority, token_id, phone, 
                    arrival_time, prediction, doctor)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, age, symptoms, priority, token_id, phone,
                 time_val, prediction, doctor))
    mysql.connection.commit()
    cur.close()

    heapq.heappush(queues[doctor],
                   (priority, name, age, symptoms, time_val, token_id, prediction))

    wait_mins = len(queues[doctor]) * 10
    if phone:
        send_whatsapp(phone, name, token_id, result['label'], wait_mins, prediction)

    return render_template('token.html',
                           name=name,
                           token=token_id,
                           priority=result['label'],
                           qr_image=f"qrcodes/{token_id}.png")

# Dashboard
@app.route('/dashboard')
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("""SELECT priority, name, age, symptoms, arrival_time, token_id, prediction 
                   FROM patients 
                   WHERE status = 'waiting' 
                   ORDER BY priority ASC, created_at ASC""")
    patients     = cur.fetchall()
    cur.close()
    waiting_time = len(patients) * 10
    return render_template('dashboard.html', patients=patients, wait=waiting_time)


# Serve next patient
@app.route('/serve')
def serve():
    cur = mysql.connection.cursor()
    cur.execute("""SELECT id, name, age, symptoms, priority, token_id, doctor
                   FROM patients 
                   WHERE status = 'waiting' 
                   ORDER BY priority ASC, created_at ASC 
                   LIMIT 1""")
    patient = cur.fetchone()

    if patient:
        doctor = patient[6] if patient[6] else 'Dr. Sharma'
        cur.execute("""INSERT INTO served_log 
                       (name, age, symptoms, priority, token_id, doctor)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (patient[1], patient[2], patient[3], 
                     patient[4], patient[5], doctor))
        cur.execute("UPDATE patients SET status = 'served' WHERE id = %s", 
                    (patient[0],))
        mysql.connection.commit()

    cur.close()
    return redirect('/dashboard')

@app.route('/doctor_dashboard')
def doctor_dashboard():
    doctor       = request.args.get('doctor', DOCTORS[0])
    waiting_time = len(queues[doctor]) * 10
    patients     = sorted(queues[doctor])
    return render_template('doctor_dashboard.html', patients=patients,
                           wait=waiting_time, doctors=DOCTORS, current=doctor)

@app.route('/doctor_serve')
def doctor_serve():
    doctor = request.args.get('doctor', DOCTORS[0])
    if queues[doctor]:
        heapq.heappop(queues[doctor])
    return redirect(f'/doctor_dashboard?doctor={doctor}')



@app.route('/emergency', methods=['POST'])
def emergency():
    name     = request.form['emergency_name']
    age      = int(request.form.get('emergency_age', 30))
    symptoms = request.form.get('emergency_symptoms', 'Emergency - immediate attention')
    token_id = "SOS-" + str(uuid.uuid4())[:4].upper()
    # priority 0 puts them above ALL other patients
    heapq.heappush(queue, (0, name, age, symptoms, "EMERGENCY", '', token_id))
    return redirect('/dashboard')

@app.route('/analytics')
def analytics():
    cur = mysql.connection.cursor()

    cur.execute("""SELECT COUNT(*) FROM served_log 
                   WHERE DATE(served_at) = CURDATE()""")
    total_today = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM served_log")
    total_all = cur.fetchone()[0]

    cur.execute("""SELECT COUNT(*) FROM served_log 
                   WHERE priority = 0 AND DATE(served_at) = CURDATE()""")
    emergency = cur.fetchone()[0]

    cur.execute("""SELECT COUNT(*) FROM served_log 
                   WHERE priority = 1 AND DATE(served_at) = CURDATE()""")
    critical = cur.fetchone()[0]

    cur.execute("""SELECT COUNT(*) FROM served_log 
                   WHERE priority = 2 AND DATE(served_at) = CURDATE()""")
    serious = cur.fetchone()[0]

    cur.execute("""SELECT COUNT(*) FROM served_log 
                   WHERE priority = 3 AND DATE(served_at) = CURDATE()""")
    normal = cur.fetchone()[0]

    cur.execute("""SELECT COUNT(*) FROM patients 
                   WHERE status = 'waiting'""")
    waiting = cur.fetchone()[0]

    cur.execute("""SELECT HOUR(served_at) as hour, COUNT(*) as count 
                   FROM served_log 
                   WHERE DATE(served_at) = CURDATE()
                   GROUP BY HOUR(served_at) 
                   ORDER BY count DESC 
                   LIMIT 1""")
    busiest = cur.fetchone()
    busiest_hour = f"{busiest[0]}:00" if busiest else "No data yet"

    cur.execute("""SELECT name, age, symptoms, priority, token_id, served_at 
                   FROM served_log 
                   ORDER BY served_at DESC 
                   LIMIT 10""")
    recent = cur.fetchall()

    cur.close()

    return render_template('analytics.html',
                           total_today=total_today,
                           total_all=total_all,
                           emergency=emergency,
                           critical=critical,
                           serious=serious,
                           normal=normal,
                           waiting=waiting,
                           busiest_hour=busiest_hour,
                           recent=recent)

@app.route('/patient/<token_id>')
def patient_detail(token_id):
    cur = mysql.connection.cursor()

    # Current patient
    cur.execute("""SELECT name, age, symptoms, priority, token_id,
                          arrival_time, doctor, prediction, phone
                   FROM patients WHERE token_id = %s""", (token_id,))
    p = cur.fetchone()

    if not p:
        return "<h2>Token not found</h2>", 404

    # Purani history — same name + phone, alag token
    cur.execute("""SELECT token_id, symptoms, priority, arrival_time, 
                          status, prediction
                   FROM patients
                   WHERE name = %s AND phone = %s
                   AND token_id != %s
                   ORDER BY created_at DESC
                   LIMIT 5""", (p[0], p[8], token_id))
    history = cur.fetchall()
    cur.close()

    labels = {0: "Emergency", 1: "Critical", 2: "Serious", 3: "Normal"}
    colors = {0: "#c0392b", 1: "#e63946", 2: "#f4a261", 3: "#2dc653"}
    priority_num = p[3]

    return render_template('patient_detail.html',
        name=p[0], age=p[1], symptoms=p[2],
        priority_label=labels[priority_num],
        priority_color=colors[priority_num],
        token=p[4], arrival=p[5],
        doctor=p[6] if p[6] else 'Not assigned',
        prediction=p[7] if p[7] else 'Not available',
        history=history,
        labels=labels
    )

@app.route('/doctor_performance')
def doctor_performance():
    selected = request.args.get('selected', None)  # ← YE ADD KARO
    cur = mysql.connection.cursor()

    cur.execute("""SELECT doctor, COUNT(*) as total
                   FROM served_log
                   WHERE DATE(served_at) = CURDATE()
                   AND doctor IS NOT NULL
                   GROUP BY doctor""")
    today_rows = cur.fetchall()
    today_stats = {row[0]: row[1] for row in today_rows}

    cur.execute("""SELECT doctor, COUNT(*) as total
                   FROM served_log
                   WHERE doctor IS NOT NULL
                   GROUP BY doctor""")
    all_rows = cur.fetchall()
    alltime_stats = {row[0]: row[1] for row in all_rows}

    cur.execute("""SELECT doctor, priority, COUNT(*) as count
                   FROM served_log
                   WHERE DATE(served_at) = CURDATE()
                   AND doctor IS NOT NULL
                   GROUP BY doctor, priority
                   ORDER BY doctor, priority""")
    priority_rows = cur.fetchall()

    priority_by_doctor = {}
    for row in priority_rows:
        doc = row[0]
        if doc not in priority_by_doctor:
            priority_by_doctor[doc] = {}
        priority_by_doctor[doc][row[1]] = row[2]

    cur.execute("""SELECT doctor, name, priority, token_id, served_at
                   FROM served_log
                   WHERE doctor IS NOT NULL
                   ORDER BY served_at DESC
                   LIMIT 30""")
    recent = cur.fetchall()

    cur.close()

    return render_template('doctor_performance.html',
                           today_stats=today_stats,
                           alltime_stats=alltime_stats,
                           priority_by_doctor=priority_by_doctor,
                           recent=recent,
                           doctors=DOCTORS,
                           selected=selected) 

def get_patient_history(phone):
    """Phone number se patient ki previous visits fetch karo"""
    if not phone:
        return []
    try:
        cur = mysql.connection.cursor()
        cur.execute("""SELECT name, age, symptoms, priority, 
                              token_id, arrival_time, prediction, created_at
                       FROM patients 
                       WHERE phone = %s 
                       AND status = 'served'
                       ORDER BY created_at DESC 
                       LIMIT 5""", (phone,))
        history = cur.fetchall()
        cur.close()
        return history
    except:
        return []

if __name__ == '__main__':
    with app.app_context():
        load_doctor_queues()
    app.run(debug=True, use_reloader=False)