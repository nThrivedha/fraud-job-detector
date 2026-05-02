import os, sys, sqlite3, joblib, re, csv, io
from functools import wraps
sys.stdout.reconfigure(encoding='utf-8')
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# ── Auth decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

DB_PATH         = 'jobs.db'
SVM_PATH        = 'svm.pkl'
RF_PATH         = 'rf.pkl'
NB_PATH         = 'nb.pkl'
VECTORIZER_PATH = 'vectorizer.pkl'

# ════════════════════════════════
# DATABASE INIT — ALL 5 TABLES
# ════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT    NOT NULL UNIQUE,
        email      TEXT    NOT NULL UNIQUE,
        password   TEXT    NOT NULL,
        role       TEXT    DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS job_posts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL,
        title            TEXT    NOT NULL,
        description      TEXT    NOT NULL,
        prediction_label TEXT    NOT NULL,
        probability      REAL    NOT NULL,
        model_used       TEXT    DEFAULT 'Unknown',
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS flagged_jobs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id     INTEGER NOT NULL,
        flagged_by INTEGER NOT NULL,
        reason     TEXT,
        severity   TEXT    DEFAULT 'medium',
        status     TEXT    DEFAULT 'pending',
        flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id)     REFERENCES job_posts(id),
        FOREIGN KEY (flagged_by) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS fraud_rules (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword     TEXT    NOT NULL UNIQUE,
        severity    TEXT    DEFAULT 'medium',
        description TEXT,
        is_active   INTEGER DEFAULT 1,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id    INTEGER NOT NULL,
        action      TEXT    NOT NULL,
        target_type TEXT,
        target_id   INTEGER,
        timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (admin_id) REFERENCES users(id)
    )''')

    # Seed default fraud keywords
    keywords = [
        ('earn daily',     'high',   'Promise of daily earnings'),
        ('no experience',  'high',   'No experience required scam'),
        ('work from home', 'medium', 'Generic WFH bait'),
        ('guaranteed pay', 'high',   'Guaranteed payment fraud'),
        ('urgent hiring',  'low',    'Urgency pressure tactic'),
        ('send money',     'high',   'Advance fee fraud'),
        ('part time easy', 'medium', 'Too-easy job posting'),
    ]
    for kw in keywords:
        c.execute('''INSERT OR IGNORE INTO fraud_rules
                     (keyword, severity, description) VALUES (?,?,?)''', kw)

    # Seed default admin user (hashed password)
    admin_hash = generate_password_hash('admin123')
    c.execute('''INSERT OR IGNORE INTO users
                 (username, email, password, role)
                 VALUES ('admin','admin@fraudsentinel.com',?,'admin')''', (admin_hash,))

    conn.commit()
    conn.close()

# ════════════════════════════════
# TEXT CLEANING
# ════════════════════════════════
def clean_text(text):
    text = text.lower()
    # Remove URLs and Emails but keep numbers and symbols for semantic analysis
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    # Keep alphanumeric and common currency/percentage symbols
    text = re.sub(r'[^a-z0-9\s\$%€£]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def analyze_semantic_patterns(title, description):
    """
    Analyzes the job posting for deeper semantic fraud indicators.
    Returns a list of flags and an overall risk score adjustment.
    """
    flags = []
    risk_score = 0
    
    title = title.lower()
    desc = description.lower()
    
    # 1. Title vs Responsibility Consistency
    high_level_titles = ['specialist', 'manager', 'director', 'engineer', 'analyst', 'consultant', 'lead']
    low_level_tasks = ['data entry', 'micro-platform', 'account validation', 'posting ads', 'receiving packages', 'transaction monitoring']
    
    has_high_title = any(t in title for t in high_level_titles)
    has_low_tasks = any(task in desc for task in low_level_tasks)
    
    if has_high_title and has_low_tasks:
        flags.append({
            'type': 'Consistency Risk',
            'indicator': 'High-level title paired with low-complexity task patterns.',
            'severity': 'medium'
        })
        risk_score += 15

    # 2. Vague Task Descriptions
    vague_phrases = ['digital workflow patterns', 'system integrity observations', 'operational footprint', 'partner coordination', 'internal ecosystem']
    vague_matches = [p for p in vague_phrases if p in desc]
    if len(vague_matches) >= 2:
        flags.append({
            'type': 'Vague Description',
            'indicator': 'Uses overly generalized corporate jargon to mask actual job functions.',
            'severity': 'low'
        })
        risk_score += 10

    # 3. Missing/Unverifiable Identity
    generic_company = ['global digital solutions', 'rapidly growing company', 'leading international firm']
    if not any(marker in desc for marker in ['inc.', 'ltd', 'corp', 'limited']) and any(g in desc for g in generic_company):
        flags.append({
            'type': 'Identity Risk',
            'indicator': 'Lack of specific company identity signals or verifiable corporate markers.',
            'severity': 'medium'
        })
        risk_score += 15

    # 4. Payment Anomalies
    if 'crypto' in desc or 'bitcoin' in desc or 'usdt' in desc:
        flags.append({
            'type': 'Payment Risk',
            'indicator': 'Cryptocurrency mentioned as a payment or onboarding method.',
            'severity': 'high'
        })
        risk_score += 30
    
    if 'performance' in desc and ('weekly' in desc or 'daily' in desc) and '$' in desc:
        if 'salary' not in desc and 'base pay' not in desc:
            flags.append({
                'type': 'Payment Risk',
                'indicator': 'Performance-only pay structure with high frequency payouts.',
                'severity': 'medium'
            })
            risk_score += 15

    # 5. Onboarding Risks
    onboarding_hooks = ['verification step', 'activation process', 'unlock access', 'dashboard activation', 'security deposit', 'verification fee']
    matched_hooks = [h for h in onboarding_hooks if h in desc]
    if matched_hooks:
        flags.append({
            'type': 'Onboarding Risk',
            'indicator': f"Suspicious onboarding condition detected: '{matched_hooks[0]}'.",
            'severity': 'high'
        })
        risk_score += 40

    return flags, risk_score

# ════════════════════════════════
# LOAD MODELS
# ════════════════════════════════
def load_models():
    if not all(os.path.exists(p) for p in
               [SVM_PATH, RF_PATH, NB_PATH, VECTORIZER_PATH]):
        raise FileNotFoundError("Model files missing. Run train_model.py first.")
    models = {
        "SVM":           joblib.load(SVM_PATH),
        "Random Forest": joblib.load(RF_PATH),
        "Naive Bayes":   joblib.load(NB_PATH)
    }
    vectorizer = joblib.load(VECTORIZER_PATH)
    return models, vectorizer

init_db()
try:
    models, vectorizer = load_models()
    print("[OK] All models loaded.")
except Exception as e:
    print(f"[ERROR] {e}")
    models, vectorizer = None, None

# ════════════════════════════════
# ROUTES
# ════════════════════════════════

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/analyze')
def analyze():
    return render_template('index.html')

@app.route('/history')
def history_page():
    return render_template('history.html')

@app.route('/flagged-ui')
def flagged_ui():
    return render_template('flagged.html')

@app.route('/auth')
def auth_page():
    return render_template('auth.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ── REGISTER ──
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip()
    password = data.get('password', '').strip()
    if not username or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hashed = generate_password_hash(password)
        c.execute('''INSERT INTO users (username, email, password)
                     VALUES (?, ?, ?)''', (username, email, hashed))
        conn.commit()
        conn.close()
        return jsonify({'message': f'User {username} registered successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 409

# ── LOGIN ──
@app.route('/login', methods=['POST'])
def login():
    data     = request.json
    email    = data.get('email', '').strip()
    password = data.get('password', '').strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, username, role, password FROM users
                 WHERE email=?''', (email,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[3], password):
        session['user_id']  = user[0]
        session['username'] = user[1]
        session['role']     = user[2]
        return jsonify({'message': 'Login successful',
                        'username': user[1], 'role': user[2]})
    return jsonify({'error': 'Invalid credentials'}), 401


# ── PREDICT ──
@app.route('/predict', methods=['POST'])
def predict():
    global models, vectorizer
    if models is None:
        try:
            models, vectorizer = load_models()
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    data = request.json
    if not data:
        return jsonify({'error': 'No data received'}), 400

    title       = data.get('title', '').strip()
    description = data.get('description', '').strip()
    # Use user_id=1 (guest/admin) if no session
    user_id     = session.get('user_id', 1)

    if not description:
        return jsonify({'error': 'Description is required'}), 400

    # Clean + vectorize
    text = clean_text(title + " " + description)
    vec  = vectorizer.transform([text])

    model_results = {}

    # SVM
    svm_pred = models["SVM"].predict(vec)[0]
    try:
        svm_conf = max(models["SVM"].predict_proba(vec)[0])
    except AttributeError:
        svm_conf = 0.90
    model_results["SVM"] = {
        "prediction": int(svm_pred),
        "label":      "Fraudulent" if svm_pred == 1 else "Genuine",
        "confidence": round(float(svm_conf) * 100, 2)
    }

    # Random Forest
    rf_pred  = models["Random Forest"].predict(vec)[0]
    rf_proba = models["Random Forest"].predict_proba(vec)[0]
    rf_fraud_prob = rf_proba[1] if len(rf_proba) > 1 else rf_proba[0]
    model_results["Random Forest"] = {
        "prediction": int(rf_pred),
        "label":      "Fraudulent" if rf_pred == 1 else "Genuine",
        "confidence": round(float(max(rf_proba)) * 100, 2)
    }

    # Naive Bayes
    nb_pred  = models["Naive Bayes"].predict(vec)[0]
    nb_proba = models["Naive Bayes"].predict_proba(vec)[0]
    model_results["Naive Bayes"] = {
        "prediction": int(nb_pred),
        "label":      "Fraudulent" if nb_pred == 1 else "Genuine",
        "confidence": round(float(max(nb_proba)) * 100, 2)
    }

    # ── SEMANTIC ANALYSIS ──
    semantic_flags, semantic_risk = analyze_semantic_patterns(title, description)
    
    # Best model = highest confidence
    best_model = max(model_results,
                     key=lambda x: model_results[x]["confidence"])
    best         = model_results[best_model]
    
    # Final verdict calculation: Model confidence + Semantic risk
    final_score = best["confidence"] + (semantic_risk if best["prediction"] == 1 else -semantic_risk)
    # Ensure score stays in 0-100
    final_score = max(0, min(100, round(final_score, 2)))
    
    # Rule: If multiple high-risk semantic flags exist, classify as Fraudulent regardless of ML
    is_fraudulent = best["prediction"] == 1 or semantic_risk >= 30
    label         = "Fraudulent" if is_fraudulent else "Genuine"

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # INSERT into job_posts
    c.execute('''INSERT INTO job_posts
                 (user_id, title, description, prediction_label,
                  probability, model_used)
                 VALUES (?, ?, ?, ?, ?, ?)''',
               (user_id, title, description, label,
                final_score / 100, best_model))
    job_id = c.lastrowid

    # If fraudulent → auto INSERT into flagged_jobs
    reasons_list = []

    if is_fraudulent:
        # 1. Add Semantic Flags first (Deeper reasoning)
        for flag in semantic_flags:
            reasons_list.append(f"[{flag['type']}] {flag['indicator']}")
        
        # 2. Add Model reasoning
        if best["prediction"] == 1:
            reasons_list.append(f"Model consensus ({best_model}) indicates fraudulent patterns with {best['confidence']}% confidence.")
        else:
            reasons_list.append("ML models suggested Genuine, but high-risk semantic patterns triggered a Fraudulent verdict.")

        c.execute('''INSERT INTO flagged_jobs
                     (job_id, flagged_by, reason, severity, status)
                     VALUES (?, ?, ?, ?, 'pending')''',
                  (job_id, user_id, " | ".join(reasons_list[:2]), 
                   'high' if final_score > 85 else 'medium'))
    else:
        reasons_list.append("No suspicious semantic patterns or payment anomalies detected.")
        reasons_list.append("ML models consensus indicates typical corporate language.")

    conn.commit()
    inserted_id = job_id
    conn.close()

    return jsonify({
        'id':               inserted_id,
        'title':            title,
        'is_fraudulent':    is_fraudulent,
        'prediction':       label,
        'confidence':       final_score,
        'model_used':       best_model,
        'probability_fraud': round(rf_fraud_prob * 100, 2),
        'semantic_flags':   semantic_flags,
        'message':          '⚠️ Likely Fraudulent Job'
                            if is_fraudulent else '✅ Looks Genuine',
        'reasons':          reasons_list,
        'all_models':       model_results
    })

# ── HISTORY (per user) ──
@app.route('/api/history', methods=['GET'])
def api_history():
    user_id = session.get('user_id', 1)
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''SELECT j.id, j.title, j.description, j.prediction_label,
                        j.probability, j.model_used, j.created_at,
                        u.username
                 FROM job_posts j
                 JOIN users u ON j.user_id = u.id
                 WHERE j.user_id = ?
                 ORDER BY j.id DESC''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'id':               r[0],
        'title':            r[1],
        'description':      r[2],
        'prediction_label': r[3],
        'probability':      r[4],
        'model_used':       r[5],
        'created_at':       r[6],
        'submitted_by':     r[7]
    } for r in rows])

@app.route('/api/history/<int:scan_id>', methods=['DELETE'])
def delete_history(scan_id):
    user_id = session.get('user_id', 1)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM flagged_jobs WHERE job_id = ? AND flagged_by = ?', (scan_id, user_id))
    c.execute('DELETE FROM job_posts WHERE id = ? AND user_id = ?', (scan_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Scan deleted'})

@app.route('/api/history/export', methods=['GET'])
def export_history():
    user_id = session.get('user_id', 1)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT j.title, j.description, j.prediction_label,
                        j.probability, j.model_used, j.created_at
                 FROM job_posts j WHERE j.user_id = ?
                 ORDER BY j.id DESC''', (user_id,))
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Description', 'Prediction', 'Confidence', 'Model Used', 'Scanned At'])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], f"{r[3]*100:.1f}%", r[4], r[5]])
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=fraudsentinel_history.csv'}
    )

# ── ADMIN: ALL JOBS ──
@app.route('/admin/jobs', methods=['GET'])
def all_jobs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT j.id, j.title, j.prediction_label, j.probability,
               j.model_used, j.created_at, u.username
        FROM job_posts j
        JOIN users u ON j.user_id = u.id
        ORDER BY j.id DESC
    ''')

    rows = c.fetchall()
    conn.close()

    return jsonify([{
        'id': r[0],
        'title': r[1],
        'prediction': r[2],
        'confidence': round(r[3]*100, 2),
        'model': r[4],
        'time': r[5],
        'user': r[6]
    } for r in rows])    

# ── FLAGGED JOBS ──
@app.route('/flagged', methods=['GET'])
def flagged():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''SELECT f.id, j.title, j.probability,
                        f.reason, f.severity, f.status, f.flagged_at
                 FROM flagged_jobs f
                 JOIN job_posts j ON f.job_id = j.id
                 ORDER BY f.flagged_at DESC''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'flag_id':    r[0],
        'title':      r[1],
        'confidence': round(r[2] * 100, 2),
        'reason':     r[3],
        'severity':   r[4],
        'status':     r[5],
        'flagged_at': r[6]
    } for r in rows])

# ── UPDATE FLAG STATUS (Admin) ──
@app.route('/flagged/<int:flag_id>', methods=['PUT'])
@admin_required
def update_flag(flag_id):
    data       = request.json
    new_status = data.get('status', 'reviewed')
    admin_id   = session.get('user_id', 1)
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''UPDATE flagged_jobs SET status=?
                 WHERE id=?''', (new_status, flag_id))
    # Log admin action
    c.execute('''INSERT INTO admin_logs
                 (admin_id, action, target_type, target_id)
                 VALUES (?, ?, 'flagged_job', ?)''',
              (admin_id, f'Status updated to {new_status}', flag_id))
    conn.commit()
    conn.close()
    return jsonify({'message': f'Flag {flag_id} updated to {new_status}'})

@app.route('/flagged/<int:flag_id>/status', methods=['PUT'])
@admin_required
def update_flag_status(flag_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['approved', 'rejected', 'reviewed']:
        return jsonify({'error': 'Invalid status'}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        UPDATE flagged_jobs
        SET status = ?
        WHERE id = ?
    """, (new_status, flag_id))

    conn.commit()
    conn.close()

    return jsonify({'message': f'Flag {flag_id} updated to {new_status}'})
@app.route('/admin/jobs-ui')
def admin_jobs_ui():
    return render_template('admin_jobs.html')

@app.route('/admin/stats-ui')
def admin_stats_ui():
    return render_template('admin_stats.html')  



# ── FRAUD RULES ──
@app.route('/rules', methods=['GET'])
def get_rules():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''SELECT id, keyword, severity, description, is_active
                 FROM fraud_rules ORDER BY severity DESC''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'id':          r[0],
        'keyword':     r[1],
        'severity':    r[2],
        'description': r[3],
        'is_active':   bool(r[4])
    } for r in rows])

@app.route('/rules', methods=['POST'])
def add_rule():
    data     = request.json
    keyword  = data.get('keyword', '').strip().lower()
    severity = data.get('severity', 'medium')
    desc     = data.get('description', '')
    admin_id = session.get('user_id', 1)
    if not keyword:
        return jsonify({'error': 'Keyword required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    try:
        c.execute('''INSERT INTO fraud_rules
                     (keyword, severity, description)
                     VALUES (?, ?, ?)''', (keyword, severity, desc))
        rule_id = c.lastrowid
        c.execute('''INSERT INTO admin_logs
                     (admin_id, action, target_type, target_id)
                     VALUES (?, 'Added fraud rule', 'fraud_rules', ?)''',
                  (admin_id, rule_id))
        conn.commit()
        conn.close()
        return jsonify({'message': f'Rule "{keyword}" added'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Keyword already exists'}), 409

# ── ADMIN LOGS ──
@app.route('/admin/logs', methods=['GET'])
def admin_logs():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''SELECT l.id, u.username, l.action,
                        l.target_type, l.target_id, l.timestamp
                 FROM admin_logs l
                 JOIN users u ON l.admin_id = u.id
                 ORDER BY l.timestamp DESC LIMIT 20''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'log_id':      r[0],
        'admin':       r[1],
        'action':      r[2],
        'target_type': r[3],
        'target_id':   r[4],
        'timestamp':   r[5]
    } for r in rows])

# ── ADMIN STATS ──
@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("SELECT COUNT(*) FROM job_posts")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM flagged_jobs")
    flagged = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]

    c.execute('''SELECT model_used, COUNT(*) as cnt
                 FROM job_posts GROUP BY model_used''')
    by_model = {r[0]: r[1] for r in c.fetchall()}

    c.execute('''SELECT severity, COUNT(*) as cnt
                 FROM flagged_jobs GROUP BY severity''')
    by_severity = {r[0]: r[1] for r in c.fetchall()}

    conn.close()
    return jsonify({
        'total_scans':   total,
        'flagged_jobs':  flagged,
        'total_users':   users,
        'by_model':      by_model,
        'by_severity':   by_severity
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)