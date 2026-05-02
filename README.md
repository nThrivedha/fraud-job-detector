# 🛡️ FraudSentinel AI — Job Scam Detector

An AI-powered web application that detects fraudulent job postings in real time using three machine learning models trained on the EMSCAD dataset.

🔗 **Live Demo:** https://fraud-job-detector-xqf3.onrender.com/

---

## What It Does

Users paste any job title and description. The system analyzes it using three ML classifiers simultaneously and returns a verdict — **Genuine** or **Fraudulent** — with a confidence score and full model breakdown.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10, Flask |
| Database | SQLite3 (jobs.db) |
| ML Models | Scikit-Learn, Joblib |
| NLP | TF-IDF Vectorization |
| Frontend | HTML5, CSS3, JavaScript |

---

## ML Models Used

| Model | Accuracy | F1-Score | AUC-ROC |
|---|---|---|---|
| Support Vector Machine (SVM) | 98.41% | 0.83 | 0.98 |
| Random Forest | 98.38% | 0.80 | 0.98 |
| Naive Bayes (ComplementNB) | 82.33% | 0.33 | 0.94 |

The model with the highest confidence score is selected as the final verdict.

---

## Dataset

- **EMSCAD** (Employment Scam Aegean Dataset) — Kaggle
- 17,880 real-world job postings (2012–2014)
- 95% genuine, 5% fraudulent
- SMOTE applied to handle class imbalance

---

## How to Run Locally

```bash
git clone https://github.com/nThrivedha/fraud-job-detector.git
cd fraud-job-detector
pip install -r requirements.txt
python app.py
 **Open in your browser:**
   Go to `http://127.0.0.1:5000/`

---

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
