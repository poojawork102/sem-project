"""XGBoost supervised classifier for admission fraud detection.

Complements the unsupervised Isolation Forest by learning from labeled data
(allow / captcha / block) to predict the appropriate action for new submissions.
"""
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session
from xgboost import XGBClassifier

from .detector import similarity
from .models import Application

MODEL_PATH = Path("data/xgboost_model.joblib")
MIN_TRAINING_SAMPLES = 30
LABEL_MAP = {"allow": 0, "captcha": 1, "block": 2}
LABEL_NAMES = {v: k for k, v in LABEL_MAP.items()}
FEATURE_NAMES = (
    "ip_submissions_last_minute",
    "same_email_seen",
    "submissions_last_five_minutes",
    "payload_size_bytes",
    "name_similarity_max",
    "ip_submissions_last_hour",
    "program_frequency",
    "hour_of_day",
)


def _features_for(
    db: Session,
    full_name: str,
    email: str,
    ip_address: str,
    payload_size: int,
    program: str,
    at: datetime | None = None,
) -> list[float]:
    """Extract an 8-dimensional feature vector for a single submission."""
    at = at or datetime.utcnow()
    one_min = at - timedelta(minutes=1)
    five_min = at - timedelta(minutes=5)
    one_hour = at - timedelta(hours=1)

    ip_1m = (
        db.query(func.count(Application.id))
        .filter(Application.ip_address == ip_address, Application.submitted_at >= one_min, Application.submitted_at < at)
        .scalar()
        or 0
    )
    ip_1h = (
        db.query(func.count(Application.id))
        .filter(Application.ip_address == ip_address, Application.submitted_at >= one_hour, Application.submitted_at < at)
        .scalar()
        or 0
    )
    traffic_5m = (
        db.query(func.count(Application.id))
        .filter(Application.submitted_at >= five_min, Application.submitted_at < at)
        .scalar()
        or 0
    )
    email_seen = 1.0 if db.query(Application.id).filter(Application.email == email, Application.submitted_at < at).first() else 0.0

    # Name similarity against recent applications (sample up to 200 for speed)
    recent = db.query(Application.full_name).order_by(Application.submitted_at.desc()).limit(200).all()
    name_sim_max = max((similarity(full_name, r[0]) for r in recent), default=0.0)

    # Program popularity (normalized count in whole DB)
    total_apps = db.query(func.count(Application.id)).scalar() or 1
    prog_count = db.query(func.count(Application.id)).filter(Application.program == program).scalar() or 0
    prog_freq = prog_count / total_apps

    hour = float(at.hour)

    return [
        float(ip_1m),
        email_seen,
        float(traffic_5m),
        float(payload_size),
        name_sim_max,
        float(ip_1h),
        prog_freq,
        hour,
    ]


def train(db: Session) -> dict:
    """Train an XGBoost classifier on all labeled applications."""
    samples = db.query(Application).filter(Application.status.in_(["allow", "captcha", "block"])).order_by(Application.submitted_at).all()

    if len(samples) < MIN_TRAINING_SAMPLES:
        return {
            "trained": False,
            "samples": len(samples),
            "minimum_samples": MIN_TRAINING_SAMPLES,
            "message": f"Need at least {MIN_TRAINING_SAMPLES} labeled applications. Currently have {len(samples)}.",
        }

    X = []
    y = []
    for app in samples:
        features = _features_for(
            db,
            app.full_name,
            app.email,
            app.ip_address,
            len(app.payload.encode("utf-8")) if app.payload else 0,
            app.program or "",
            app.submitted_at,
        )
        X.append(features)
        y.append(LABEL_MAP.get(app.status, 0))

    X = np.array(X)
    y = np.array(y)

    # Check we have at least 2 classes
    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        return {
            "trained": False,
            "samples": len(samples),
            "message": "Need at least 2 different status classes to train. Add some suspicious/blocked data.",
        }

    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=42,
        verbosity=0,
    )
    model.fit(X, y)

    # Evaluate on training data (for status display)
    preds = model.predict(X)
    accuracy = float(np.mean(preds == y))

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "samples": len(samples),
            "accuracy": accuracy,
            "class_distribution": {LABEL_NAMES[c]: int(np.sum(y == c)) for c in unique_classes},
            "feature_names": FEATURE_NAMES,
        },
        MODEL_PATH,
    )

    return {
        "trained": True,
        "samples": len(samples),
        "accuracy": round(accuracy * 100, 1),
        "class_distribution": {LABEL_NAMES[c]: int(np.sum(y == c)) for c in unique_classes},
        "message": f"XGBoost trained on {len(samples)} samples with {accuracy * 100:.1f}% training accuracy.",
    }


def predict(
    db: Session,
    full_name: str,
    email: str,
    ip_address: str,
    payload_size: int,
    program: str,
    at: datetime | None = None,
) -> tuple[str | None, float | None]:
    """Predict the action class and confidence for a new submission.

    Returns (predicted_action, confidence) or (None, None) if not trained.
    """
    if not MODEL_PATH.exists():
        return None, None

    artifact = joblib.load(MODEL_PATH)
    model = artifact["model"]
    features = np.array([_features_for(db, full_name, email, ip_address, payload_size, program, at)])
    proba = model.predict_proba(features)[0]
    pred_class = int(np.argmax(proba))
    confidence = float(proba[pred_class])

    return LABEL_NAMES.get(pred_class, "allow"), round(confidence * 100, 1)


def status() -> dict:
    """Return the current model status for the admin dashboard."""
    if not MODEL_PATH.exists():
        return {"trained": False, "minimum_samples": MIN_TRAINING_SAMPLES}

    artifact = joblib.load(MODEL_PATH)
    return {
        "trained": True,
        "samples": artifact["samples"],
        "accuracy": artifact.get("accuracy", 0),
        "class_distribution": artifact.get("class_distribution", {}),
        "features": artifact.get("feature_names", FEATURE_NAMES),
    }
