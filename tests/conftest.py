"""Shared test setup: every test gets its own throwaway SQLite DB, so tests never touch
data/dsadps.db, and the ML model files / rate limiters never leak between tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import main, ml_agent, xgboost_agent
from app.config import settings
from app.database import Base, get_db

ADMIN_USER, ADMIN_PASS = "admin", "test-admin-password"


@pytest.fixture(autouse=True)
def isolated_app(tmp_path, monkeypatch):
    # In-memory DB shared by all connections (StaticPool) so threads see the same data.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(ml_agent, "MODEL_PATH", tmp_path / "isolation_forest.joblib")
    monkeypatch.setattr(xgboost_agent, "MODEL_PATH", tmp_path / "xgboost_model.joblib")
    monkeypatch.setattr(settings, "admin_username", ADMIN_USER)
    monkeypatch.setattr(settings, "admin_password", ADMIN_PASS)
    main.login_limiter.clear()
    main.status_limiter.clear()
    yield factory
    main.app.dependency_overrides.clear()


@pytest.fixture()
def db_factory(isolated_app):
    return isolated_app


@pytest.fixture()
def api():
    return TestClient(main.app)


@pytest.fixture()
def admin_headers(api):
    token = api.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
