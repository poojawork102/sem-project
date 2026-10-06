"""Single submission pipeline: rules score + ML scores -> allow / captcha / block, then persist."""
import json
import secrets
import threading
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .detector import analyse_submission, choose_action
from .ml_agent import assess as assess_ai
from .models import Action, ActivityLog, Application
from .schemas import MAX_PAYLOAD_BYTES, DecisionOut, SubmissionIn
from .xgboost_agent import predict as xgb_predict

_submission_lock = threading.Lock()
CAPTCHA_NOTICE = "Simulated: no CAPTCHA challenge is enforced yet; this decision is recorded for admin review only."


def process_submission(data: SubmissionIn, db: Session, at: datetime | None = None) -> tuple[DecisionOut, Application]:
    """The single submission pipeline: portal, partner API, seed script and CSV import all use it.

    `at` lets the seed/import scripts replay historical timestamps; live requests leave it None."""
    now = at or datetime.utcnow()
    payload_bytes = len(json.dumps(data.payload).encode("utf-8"))
    if payload_bytes > MAX_PAYLOAD_BYTES:
        # Unbounded extra fields would let one request bloat the DB and every ML feature query.
        raise HTTPException(status_code=413, detail=f"Submission too large (limit {MAX_PAYLOAD_BYTES} bytes).")
    program = str(data.payload.get("program", ""))
    # ML scores are supplementary and do not affect the limits, so they run outside the lock.
    ai_score, agent_status = assess_ai(db, data.full_name, str(data.email), data.ip_address, payload_bytes, at)
    xgb_pred, xgb_conf = xgb_predict(db, data.full_name, str(data.email), data.ip_address, payload_bytes, program, at)
    reference_code = f"CAP-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"
    # Race fix: analyse_submission COUNTS earlier rows and we then INSERT this one. Without
    # a lock, N concurrent requests could all count "0 so far" and all pass the limit.
    # Holding the lock over count + insert + commit makes that sequence atomic per process.
    # Limitation: it does not protect multiple uvicorn workers/containers; for that,
    # use a DB-level lock (e.g. Postgres advisory lock) or a shared counter such as Redis.
    with _submission_lock:
        score, reasons = analyse_submission(db, data.full_name, data.email, data.ip_address, at)
        action = choose_action(score)
        application = Application(full_name=data.full_name, email=str(data.email), ip_address=data.ip_address, status=action, reference_code=reference_code, phone=str(data.payload.get("phone", "")), program=program, payload=json.dumps(data.payload), submitted_at=now)
        db.add(application)
        db.flush()
        log = ActivityLog(application_id=application.id, full_name=data.full_name, email=str(data.email), ip_address=data.ip_address, risk_score=score, ai_anomaly_score=ai_score, ai_status=agent_status, suggested_action=action, final_action=action, reasons=reasons, xgb_prediction=xgb_pred, xgb_confidence=xgb_conf, created_at=now)
        db.add(log)
        db.commit()
    db.refresh(log)
    # No CAPTCHA widget is wired in yet, so "captcha" is a recorded decision only.
    # Say so explicitly instead of implying the applicant was actually challenged.
    is_captcha = action == Action.CAPTCHA.value
    decision = DecisionOut(activity_id=log.id, risk_score=score, ai_anomaly_score=ai_score, ai_status=agent_status, action=action, reasons=reasons, created_at=log.created_at, captcha_simulated=is_captcha, notice=CAPTCHA_NOTICE if is_captcha else None)
    return decision, application
