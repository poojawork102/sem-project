import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import func
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .config import settings, validate_secrets
from .ratelimit import RateLimiter
from .database import ensure_schema, get_db
from .submission import process_submission
from .models import Action, ActivityLog, Application
from .reports import daily_csv, summary, weekly_trend_png
from .scheduler import scheduler, start_scheduler
from .ml_agent import status as ai_status, train as train_ai
from .xgboost_agent import status as xgb_status, train as xgb_train
from .chatbot import chat_with_gemini
from .schemas import ApplicationStatusIn, ChatMessageIn, DecisionOut, LoginIn, OverrideIn, PortalApplicationIn, PortalDecisionOut, SubmissionIn
from .security import create_access_token, require_admin, require_submissions_api_key

app = FastAPI(title="AdmitShield Agent API", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Failed logins only: 5 wrong attempts per client IP in 5 minutes -> HTTP 429.
login_limiter = RateLimiter(max_events=5, window_seconds=300)
# Every status lookup counts: 10 per client IP per minute -> HTTP 429 (slows guessing of reference codes).
status_limiter = RateLimiter(max_events=10, window_seconds=60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def mask_name(full_name: str) -> str:
    """'Priya Patil' -> 'Priya P.' so a guessed reference code does not reveal the full name."""
    parts = full_name.split()
    return " ".join([parts[0]] + [f"{p[0]}." for p in parts[1:]]) if parts else ""


@app.on_event("startup")
def start() -> None:
    validate_secrets()
    Path("data").mkdir(exist_ok=True)
    ensure_schema()
    start_scheduler()


@app.on_event("shutdown")
def stop() -> None:
    if scheduler.running:
        scheduler.shutdown()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def admission_portal():
    return FileResponse("app/static/portal.html")


@app.get("/admin", include_in_schema=False)
def dashboard():
    return FileResponse("app/static/index.html")


@app.post("/auth/login")
def login(data: LoginIn, request: Request):
    ip = client_ip(request)
    if login_limiter.is_blocked(ip):
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again in a few minutes.")
    # compare_digest takes constant time, so response timing does not leak how much matched.
    # Both fields are always compared (no short-circuit) and encoded so non-ASCII input is safe.
    user_ok = secrets.compare_digest(data.username.encode(), settings.admin_username.encode())
    pass_ok = secrets.compare_digest(data.password.encode(), settings.admin_password.encode())
    if not (user_ok and pass_ok):
        login_limiter.record(ip)
        raise HTTPException(status_code=401, detail="Incorrect admin credentials")
    login_limiter.reset(ip)
    return {"access_token": create_access_token(data.username), "token_type": "bearer"}


@app.post("/v1/submissions", response_model=DecisionOut)
def assess_submission(data: SubmissionIn, _key: str = Depends(require_submissions_api_key), db: Session = Depends(get_db)):
    """Integration endpoint for a partner's existing admission portal over TLS in
    production. Requires an X-API-Key header because, unlike /v1/portal/applications,
    the caller (not this server) is trusted to report the real applicant IP."""
    decision, _application = process_submission(data, db)
    return decision


@app.post("/v1/portal/applications", response_model=PortalDecisionOut)
def submit_portal_application(data: PortalApplicationIn, request: Request, db: Session = Depends(get_db)):
    payload = data.model_dump(exclude={"full_name", "email"})
    decision, application = process_submission(SubmissionIn(full_name=data.full_name, email=data.email, ip_address=client_ip(request), payload=payload), db)
    # The applicant only learns the outcome. The score and reasons stay admin-only,
    # otherwise an attacker could read the thresholds back and tune around them.
    return PortalDecisionOut(action=decision.action, created_at=decision.created_at, captcha_simulated=decision.captcha_simulated, notice=decision.notice, reference_code=application.reference_code or "")


@app.post("/v1/portal/application-status")
def portal_application_status(data: ApplicationStatusIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if status_limiter.is_blocked(ip):
        raise HTTPException(status_code=429, detail="Too many status lookups. Please wait a minute and try again.")
    status_limiter.record(ip)
    application = db.query(Application).filter(Application.reference_code == data.reference_code.strip().upper(), func.lower(Application.email) == str(data.email).lower()).first()
    if not application:
        raise HTTPException(status_code=404, detail="No application matches that reference and email.")
    labels = {Action.ALLOW.value: "Application received", Action.CAPTCHA.value: "Verification required", Action.BLOCK.value: "Application held for review"}
    # Data minimisation: the 6-hex ref code is a weak secret, so return only what the status
    # page needs. Phone, DOB, statement and the email are never sent back; the name is masked.
    return {
        "reference_code": application.reference_code,
        "program": application.program,
        "submitted_at": application.submitted_at,
        "status": labels.get(application.status, application.status),
        "raw_status": application.status,
        "full_name": mask_name(application.full_name),
    }


@app.get("/v1/admin/applications")
def list_applications(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    apps = db.query(Application).order_by(Application.submitted_at.desc()).all()
    logs = {log.application_id: log for log in db.query(ActivityLog).all() if log.application_id}
    result = []
    for app_item in apps:
        log = logs.get(app_item.id)
        payload_data = {}
        try:
            payload_data = json.loads(app_item.payload) if app_item.payload else {}
        except Exception:
            payload_data = {}
        result.append({
            "id": app_item.id,
            "full_name": app_item.full_name,
            "email": app_item.email,
            "reference_code": app_item.reference_code,
            "phone": app_item.phone,
            "program": app_item.program,
            "ip_address": app_item.ip_address,
            "submitted_at": app_item.submitted_at.isoformat() if app_item.submitted_at else None,
            "status": app_item.status,
            "confirmed_spam": app_item.confirmed_spam,
            "payload": payload_data,
            "activity_id": log.id if log else None,
            "risk_score": log.risk_score if log else 0.0,
            "ai_anomaly_score": log.ai_anomaly_score if log else None,
            "ai_status": log.ai_status if log else "not_trained",
            "reasons": log.reasons if log else [],
            "admin_override_by": log.admin_override_by if log else None,
            "admin_note": log.admin_note if log else None,
            "xgb_prediction": log.xgb_prediction if log else None,
            "xgb_confidence": log.xgb_confidence if log else None,
        })
    return result


@app.put("/v1/admin/applications/{app_id}/spam")
def toggle_spam(app_id: int, confirmed: bool = True, _admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    app_item = db.get(Application, app_id)
    if not app_item:
        raise HTTPException(status_code=404, detail="Application not found")
    app_item.confirmed_spam = confirmed
    db.commit()
    return {"id": app_item.id, "confirmed_spam": app_item.confirmed_spam}


@app.get("/v1/admin/activity")
def activity(limit: int = 100, _admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(min(limit, 500)).all()


@app.put("/v1/admin/activity/{activity_id}/override")
def override(activity_id: int, data: OverrideIn, admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    record = db.get(ActivityLog, activity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Activity record not found")
    record.final_action, record.admin_override_by, record.admin_note = data.action, admin, data.note
    application = db.get(Application, record.application_id) if record.application_id else None
    if application:
        application.status = data.action
    db.commit()
    return {"id": record.id, "final_action": record.final_action, "overridden_by": admin}


@app.get("/v1/admin/reports/summary")
def report_summary(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return summary(db)


@app.get("/v1/admin/ai/status")
def agent_status(_admin: str = Depends(require_admin)):
    return ai_status()


@app.post("/v1/admin/ai/train")
def train_agent(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return train_ai(db)


@app.get("/v1/admin/ai/xgboost/status")
def xgboost_status(_admin: str = Depends(require_admin)):
    return xgb_status()


@app.post("/v1/admin/ai/xgboost/train")
def train_xgboost(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return xgb_train(db)


@app.post("/v1/admin/chat")
def admin_chat(data: ChatMessageIn, _admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return chat_with_gemini(data.message, data.history, db)


@app.post("/v1/admin/reports/daily.csv")
def export_daily_report(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return FileResponse(daily_csv(db), media_type="text/csv", filename="daily-attack-summary.csv")


@app.post("/v1/admin/reports/weekly-trend.png")
def export_weekly_trend(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    return FileResponse(weekly_trend_png(db), media_type="image/png", filename="weekly-attack-trend.png")


@app.post("/v1/admin/cleanup")
def cleanup_confirmed_spam(_admin: str = Depends(require_admin), db: Session = Depends(get_db)):
    # Safety requirement: only previously admin-confirmed spam is deleted.
    candidates = db.query(Application).filter(Application.confirmed_spam.is_(True)).all()
    count = len(candidates)
    for item in candidates:
        db.delete(item)
    db.commit()
    return {"deleted_confirmed_spam_records": count, "message": "Audit entries were retained."}
