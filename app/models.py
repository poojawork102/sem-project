from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Application(Base):
    """Linked portal application. Only ALLOWED applications are final admissions records."""
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    reference_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), default="")
    program: Mapped[str] = mapped_column(String(120), default="")
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    status: Mapped[str] = mapped_column(String(24), default="allowed")
    payload: Mapped[str] = mapped_column(Text, default="{}")
    confirmed_spam: Mapped[bool] = mapped_column(Boolean, default=False)


class ActivityLog(Base):
    """Independent immutable-style audit log required by SRS section 6."""
    __tablename__ = "flagged_activity_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    ai_anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(32), default="not_trained")
    suggested_action: Mapped[str] = mapped_column(String(24))
    final_action: Mapped[str] = mapped_column(String(24))
    reasons: Mapped[dict] = mapped_column(JSON)
    admin_override_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
