import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .config import settings
from .database import ensure_schema, get_db
from .detector import analyse_submission, choose_action
from .models import ActivityLog, Application
from .reports import daily_csv, summary, weekly_trend_png
from .scheduler import scheduler, start_scheduler
from .ml_agent import assess as assess_ai, status as ai_status, train as train_ai
from .schemas import ApplicationStatusIn, DecisionOut, LoginIn, OverrideIn, PortalApplicationIn, PortalDecisionOut, SubmissionIn
from .security import create_access_token, require_admin

app = FastAPI(title="DSADPS Agent API", version="1.0.0")


@app.on_event("startup")
def start() -> None:
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
def login(data: LoginIn):
    if data.username != settings.admin_username or data.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Incorrect admin credentials")
    return {"access_token": create_access_token(data.username), "token_type": "bearer"}


def process_submission(data: SubmissionIn, db: Session) -> DecisionOut:
    """Shared security gate used by the portal and a future external portal integration."""
    score, reasons = analyse_submission(db, data.full_name, data.email, data.ip_address)
    ai_score, agent_status = assess_ai(db, data.full_name, str(data.email), data.ip_address, len(json.dumps(data.payload).encode("utf-8")))
    action = choose_action(score)
    reference_code = f"CAP-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
    application = Application(full_name=data.full_name, email=str(data.email), ip_address=data.ip_address, status=action, reference_code=reference_code, phone=str(data.payload.get("phone", "")), program=str(data.payload.get("program", "")), payload=json.dumps(data.payload))
    db.add(application)
    db.flush()
    log = ActivityLog(application_id=application.id, full_name=data.full_name, email=str(data.email), ip_address=data.ip_address, risk_score=score, ai_anomaly_score=ai_score, ai_status=agent_status, suggested_action=action, final_action=action, reasons=reasons)
    db.add(log)
    db.commit()
    db.refresh(log)
    return DecisionOut(activity_id=log.id, risk_score=score, ai_anomaly_score=ai_score, ai_status=agent_status, action=action, reasons=reasons, created_at=log.created_at)


@app.post("/v1/submissions", response_model=DecisionOut)
def assess_submission(data: SubmissionIn, db: Session = Depends(get_db)):
    """Integration endpoint for an existing admission portal over TLS in production."""
    return process_submission(data, db)


@app.post("/v1/portal/applications", response_model=PortalDecisionOut)
def submit_portal_application(data: PortalApplicationIn, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    payload = data.model_dump(exclude={"full_name", "email"})
    result = process_submission(SubmissionIn(full_name=data.full_name, email=data.email, ip_address=client_ip, payload=payload), db)
    application = db.get(Application, db.get(ActivityLog, result.activity_id).application_id)
    return PortalDecisionOut(**result.model_dump(), reference_code=application.reference_code or "")


@app.post("/v1/portal/application-status")
def portal_application_status(data: ApplicationStatusIn, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.reference_code == data.reference_code.upper(), Application.email == str(data.email)).first()
    if not application:
        raise HTTPException(status_code=404, detail="No application matches that reference and email.")
    labels = {"allow": "Application received", "captcha": "Verification required", "block": "Application held for review"}
    return {"reference_code": application.reference_code, "program": application.program, "submitted_at": application.submitted_at, "status": labels.get(application.status, application.status)}


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
