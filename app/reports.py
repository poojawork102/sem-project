import csv
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import ActivityLog


REPORT_DIR = Path("reports")


def daily_csv(db: Session, day: datetime | None = None) -> Path:
    day = day or datetime.utcnow()
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    records = db.query(ActivityLog).filter(ActivityLog.created_at >= start, ActivityLog.created_at < end).all()
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"attack-summary-{start.date()}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["activity_id", "timestamp", "risk_score", "suggested_action", "final_action", "ip_address", "reasons"])
        writer.writerows([[x.id, x.created_at.isoformat(), x.risk_score, x.suggested_action, x.final_action, x.ip_address, " | ".join(x.reasons)] for x in records])
    return path


def summary(db: Session) -> dict:
    since = datetime.utcnow() - timedelta(days=7)
    records = db.query(ActivityLog).filter(ActivityLog.created_at >= since).all()
    return {"from": since.isoformat(), "total_flagged_or_logged": len(records), "by_action": {a: sum(x.final_action == a for x in records) for a in ("allow", "captcha", "block")}}


def weekly_trend_png(db: Session) -> Path:
    """A reproducible weekly graph for REQ-11, based solely on audit-log timestamps."""
    today = datetime.utcnow().date()
    days = [today - timedelta(days=n) for n in reversed(range(7))]
    records = db.query(ActivityLog).filter(ActivityLog.created_at >= datetime.combine(days[0], datetime.min.time())).all()
    counts = [sum(x.created_at.date() == day for x in records) for day in days]
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"weekly-trend-{today}.png"
    fig, axis = plt.subplots(figsize=(8, 4))
    axis.plot([str(day) for day in days], counts, marker="o", color="#1d4ed8")
    axis.set(title="DSADPS weekly flagged activity", xlabel="Date", ylabel="Submissions")
    axis.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
