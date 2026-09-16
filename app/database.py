from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Small safe migration for the student-project SQLite database."""
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("flagged_activity_log")}
    with engine.begin() as connection:
        if "ai_anomaly_score" not in columns:
            connection.execute(text("ALTER TABLE flagged_activity_log ADD COLUMN ai_anomaly_score FLOAT"))
        if "ai_status" not in columns:
            connection.execute(text("ALTER TABLE flagged_activity_log ADD COLUMN ai_status VARCHAR(32) DEFAULT 'not_trained'"))
