"""Isolation Forest anomaly agent. It supplements - never hides - the SRS rule score."""
from datetime import datetime, timedelta
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import Application

MODEL_PATH = Path("data/isolation_forest.joblib")
MIN_TRAINING_SAMPLES = 20
FEATURE_NAMES = ("ip_submissions_last_minute", "same_email_seen", "submissions_last_five_minutes", "payload_size_bytes")


def features_for(db: Session, full_name: str, email: str, ip_address: str, payload_size: int, at: datetime | None = None) -> list[float]:
    at = at or datetime.utcnow()
    one_minute_ago, five_minutes_ago = at - timedelta(minutes=1), at - timedelta(minutes=5)
    ip_count = db.query(func.count(Application.id)).filter(Application.ip_address == ip_address, Application.submitted_at >= one_minute_ago, Application.submitted_at < at).scalar() or 0
    traffic_count = db.query(func.count(Application.id)).filter(Application.submitted_at >= five_minutes_ago, Application.submitted_at < at).scalar() or 0
    email_seen = db.query(Application.id).filter(Application.email == email, Application.submitted_at < at).first() is not None
    return [float(ip_count), float(email_seen), float(traffic_count), float(payload_size)]


def train(db: Session) -> dict:
    # Only applications finally allowed by an admin/agent become the normal baseline.
    samples = db.query(Application).filter(Application.status == "allow").order_by(Application.submitted_at).all()
    if len(samples) < MIN_TRAINING_SAMPLES:
        return {"trained": False, "samples": len(samples), "minimum_samples": MIN_TRAINING_SAMPLES, "message": "Generate or collect more approved normal applications before training."}
    matrix = []
    for item in samples:
        matrix.append(features_for(db, item.full_name, item.email, item.ip_address, len(item.payload.encode("utf-8")), item.submitted_at))
    model = Pipeline([("scale", StandardScaler()), ("isolation_forest", IsolationForest(contamination=0.05, random_state=42))])
    model.fit(matrix)
    raw_scores = model.decision_function(matrix)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "min_raw": float(np.min(raw_scores)), "max_raw": float(np.max(raw_scores)), "samples": len(samples)}, MODEL_PATH)
    return {"trained": True, "samples": len(samples), "message": "Isolation Forest trained from approved normal submissions."}


def assess(db: Session, full_name: str, email: str, ip_address: str, payload_size: int, at: datetime | None = None) -> tuple[float | None, str]:
    if not MODEL_PATH.exists():
        return None, "not_trained"
    artifact = joblib.load(MODEL_PATH)
    raw = float(artifact["model"].decision_function([features_for(db, full_name, email, ip_address, payload_size, at)])[0])
    spread = max(artifact["max_raw"] - artifact["min_raw"], 0.001)
    # Lower Isolation Forest decision values are more unusual; 0=normal, 100=very anomalous.
    score = round(max(0.0, min(100.0, (artifact["max_raw"] - raw) / spread * 100)), 2)
    return score, "anomaly" if raw < 0 else "normal"


def status() -> dict:
    if not MODEL_PATH.exists():
        return {"trained": False, "minimum_samples": MIN_TRAINING_SAMPLES}
    artifact = joblib.load(MODEL_PATH)
    return {"trained": True, "samples": artifact["samples"], "features": FEATURE_NAMES}
