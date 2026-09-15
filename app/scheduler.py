"""Scheduled jobs. Run one scheduler instance only (one API replica or a dedicated worker)."""
from apscheduler.schedulers.background import BackgroundScheduler
from .database import SessionLocal
from .models import Application
from .reports import daily_csv, weekly_trend_png

scheduler = BackgroundScheduler(timezone="UTC")


def generate_reports() -> None:
    with SessionLocal() as db:
        daily_csv(db)
        weekly_trend_png(db)


def remove_confirmed_spam() -> None:
    """Nightly cleanup cannot delete a genuine record because confirmation is explicit."""
    with SessionLocal() as db:
        for item in db.query(Application).filter(Application.confirmed_spam.is_(True)).all():
            db.delete(item)
        db.commit()


def start_scheduler() -> None:
    scheduler.add_job(generate_reports, "cron", hour=0, minute=0, id="daily-reports", replace_existing=True)
    scheduler.add_job(remove_confirmed_spam, "cron", hour=1, minute=0, id="nightly-confirmed-spam-cleanup", replace_existing=True)
    scheduler.start()
