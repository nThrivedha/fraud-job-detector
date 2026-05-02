import pandas as pd
import re
import joblib
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import ComplementNB
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from imblearn.over_sampling import SMOTE

# Load dataset
df = pd.read_csv('fake_job_postings.csv')

# Preprocess
text_cols = ['title', 'company_profile', 'description', 'requirements', 'benefits']
df[text_cols] = df[text_cols].fillna('')

df['job_content'] = df[text_cols].agg(' '.join, axis=1)

def clean_text(text):
    text = text.lower()
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

df['job_content'] = df['job_content'].apply(clean_text)

X = df['job_content']
y = df['fraudulent']

# TF-IDF
vectorizer = TfidfVectorizer(max_features=5000, stop_words='english', ngram_range=(1,2))
X_tfidf = vectorizer.fit_transform(X)

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X_tfidf, y, test_size=0.2, random_state=42, stratify=y
)

# SMOTE
sm = SMOTE(random_state=42)
X_train_res, y_train_res = sm.fit_resample(X_train, y_train)

# Train models
svm = LinearSVC()
svm.fit(X_train_res, y_train_res)

rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
rf.fit(X_train_res, y_train_res)

nb = ComplementNB()
nb.fit(X_train_res, y_train_res)

# Save
joblib.dump(svm, "svm.pkl")
joblib.dump(rf, "rf.pkl")
joblib.dump(nb, "nb.pkl")
joblib.dump(vectorizer, "vectorizer.pkl")

print("✅ All models saved!")
