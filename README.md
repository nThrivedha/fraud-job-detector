# 🚨 FraudSentinel AI - Job Scam Detector

FraudSentinel AI is a machine-learning web application built with Python and Flask. It analyzes job posting titles and descriptions in real time to classify them as either **Genuine** or **Fraudulent**, protecting job seekers from scams.

## ✨ Features
- **3-Model Cross Validation**: Uses Support Vector Machine (SVM), Random Forest, and Complement Naive Bayes with consensus-based scoring.
- **Real-Time Risk Scoring**: Parallel side-by-side layout showing confidence scores, model breakdown, and AI reasoning.
- **History Tracking**: Card-based scan history with search, filtering, sorting, and CSV export.
- **User Authentication**: Secure login/register with hashed passwords (Werkzeug).
- **Admin Dashboard**: Protected admin panel with charts showing scans by model and severity breakdown.
- **Flagged Jobs Management**: Automated fraud flagging with keyword matching from a configurable rules database.
- **Risk Levels**: Three-tier classification — Fraudulent (red), Uncertain (yellow), Genuine (green).

## 🛠️ Tech Stack
- **Backend:** Python 3.10, Flask, SQLite3, Werkzeug
- **Machine Learning:** Scikit-Learn, Pandas, Joblib, imbalanced-learn (TF-IDF Vectorization + SMOTE)
- **Frontend:** HTML5, Vanilla CSS3, JavaScript, Chart.js
- **Database:** SQLite3 with 5 tables (users, job_posts, flagged_jobs, fraud_rules, admin_logs)

## 🚀 How to Run Locally

1. **Clone the repository** (or download the ZIP and extract it):
   ```bash
   git clone https://github.com/yourusername/fraud-detector.git
   cd fraud-detector
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Train the models (if missing):**
   *Note: This might take a few minutes as it vectorizes the dataset and trains all 3 models.*
   ```bash
   python train_model.py
   ```

4. **Run the Flask server:**
   ```bash
   python app.py
   ```

5. **Open in your browser:**
   Go to `http://127.0.0.1:5000/`

## 🔐 Default Admin Credentials
- **Email:** `admin@fraudsentinel.com`
- **Password:** `admin123`

## 📁 Project Structure
```text
fraud-detector/
│
├── app.py                   # Main Flask backend (routes, ML inference, auth)
├── train_model.py           # Model training script (SVM, RF, NB + SMOTE)
├── requirements.txt         # Python dependencies
├── fake_job_postings.csv    # Dataset for training
├── jobs.db                  # SQLite database (auto-created)
│
├── static/
│   ├── css/style.css        # Global UI styling
│   └── js/main.js           # Frontend logic & API calls
│
└── templates/
    ├── home.html            # Landing page with hero & model cards
    ├── index.html           # Job analyzer (side-by-side layout)
    ├── history.html         # Scan history with cards, search & export
    ├── auth.html            # Login / Register page
    ├── flagged.html         # Flagged jobs management (admin)
    ├── admin_jobs.html      # All scans table (admin)
    ├── admin_stats.html     # Dashboard with charts (admin)
    └── base.html            # Legacy base template
```

## 📜 License
This project is open-source and available under the MIT License.
