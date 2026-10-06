"""Phase 1 items 4-8: hard block rule, startup secrets, login limiting, race lock,
simulated CAPTCHA flag, and status-lookup minimisation. Uses a throwaway SQLite file."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main
from app.config import Settings, settings, validate_secrets
from app.database import Base, get_db
from app.detector import analyse_submission, choose_action
from app.models import Application


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def client(session_factory):
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_db
    main.login_limiter.clear()
    main.status_limiter.clear()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def portal_body(name="Portal Applicant", email="portal@example.com"):
    return {"full_name": name, "email": email, "phone": "9999999999", "program": "BTech CSE",
            "date_of_birth": "2005-01-01", "city": "Pune",
            "statement": "This is a sufficiently long personal statement for validation."}


# ---- Item 4: block is reachable -------------------------------------------------

def seed_ip_history(db, ip, count):
    for name in ["Alpha Zeta", "Bravo Yankee", "Charlie Xray", "Delta Whiskey"][:count]:
        db.add(Application(full_name=name, email=f"{name.split()[0].lower()}@example.com", ip_address=ip, status="allow", payload="{}"))
    db.commit()


def test_ip_over_limit_alone_is_captcha_not_block(session_factory):
    with session_factory() as db:
        seed_ip_history(db, "10.0.0.1", 3)
        score, _ = analyse_submission(db, "Echo Victor", "echo@example.com", "10.0.0.1")
    assert choose_action(score) == "captcha"


def test_ip_over_limit_plus_duplicate_email_is_block(session_factory):
    with session_factory() as db:
        seed_ip_history(db, "10.0.0.1", 3)
        score, reasons = analyse_submission(db, "Echo Victor", "alpha@example.com", "10.0.0.1")
    assert score == 100.0
    assert choose_action(score) == "block"
    assert any(r.startswith("Hard rule") for r in reasons)
    assert any("Email exactly matches" in r for r in reasons)  # underlying signals stay listed


def test_duplicate_without_ip_pressure_is_not_hard_blocked(session_factory):
    with session_factory() as db:
        seed_ip_history(db, "10.0.0.1", 1)
        score, reasons = analyse_submission(db, "Echo Victor", "alpha@example.com", "10.0.0.9")
    assert choose_action(score) != "block"
    assert not any(r.startswith("Hard rule") for r in reasons)


# ---- Item 5: startup secrets + login -------------------------------------------

def test_startup_rejects_default_secrets():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_secrets(Settings(jwt_secret="development-only-change-me", admin_password="a-strong-password-1"))
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        validate_secrets(Settings(jwt_secret="x" * 40, admin_password="change-me"))
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_secrets(Settings(jwt_secret="replace-with-a-long-random-secret", admin_password="a-strong-password-1"))


def test_startup_accepts_strong_secrets():
    validate_secrets(Settings(jwt_secret="x" * 40, admin_password="a-strong-password-1"))


def test_login_success_and_wrong_password(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "right-password")
    assert client.post("/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    ok = client.post("/auth/login", json={"username": "admin", "password": "right-password"})
    assert ok.status_code == 200 and "access_token" in ok.json()


def test_login_accepts_non_ascii_input_without_crashing(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "right-password")
    assert client.post("/auth/login", json={"username": "adminé", "password": "pässword"}).status_code == 401


def test_login_locked_after_five_failures_even_with_correct_password(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "right-password")
    for _ in range(5):
        assert client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    locked = client.post("/auth/login", json={"username": "admin", "password": "right-password"})
    assert locked.status_code == 429


def test_successful_login_resets_failure_count(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "right-password")
    for _ in range(4):
        client.post("/auth/login", json={"username": "admin", "password": "bad"})
    assert client.post("/auth/login", json={"username": "admin", "password": "right-password"}).status_code == 200
    for _ in range(4):
        assert client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401


# ---- Item 6: concurrent requests cannot all bypass the IP limit -----------------

def test_concurrent_submissions_respect_ip_limit(client):
    names = ["Alpha Zeta", "Bravo Yankee", "Charlie Xray", "Delta Whiskey", "Echo Victor", "Foxtrot Uniform", "Golf Tango", "Hotel Sierra"]

    def submit(name):
        email = f"{name.split()[0].lower()}@example.com"
        return client.post("/v1/portal/applications", json=portal_body(name, email)).json()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, names))
    flagged = [r for r in results if any("IP submitted" in reason for reason in r["reasons"])]
    # Limit is 3 per minute: serialized, exactly the 4th..8th see the IP over the limit.
    assert len(flagged) == len(names) - settings.rapid_submission_limit


# ---- Item 7: CAPTCHA is labelled as simulated ----------------------------------

def test_captcha_decision_is_flagged_as_simulated(client, monkeypatch):
    monkeypatch.setattr(main, "choose_action", lambda score: "captcha")
    body = client.post("/v1/portal/applications", json=portal_body()).json()
    assert body["action"] == "captcha"
    assert body["captcha_simulated"] is True
    assert "Simulated" in body["notice"]


def test_allow_decision_has_no_captcha_flag(client):
    body = client.post("/v1/portal/applications", json=portal_body()).json()
    assert body["action"] == "allow"
    assert body["captcha_simulated"] is False and body["notice"] is None


# ---- Item 8: status lookup minimisation + rate limit ---------------------------

def test_status_lookup_returns_only_minimal_fields(client):
    created = client.post("/v1/portal/applications", json=portal_body("Priya Patil", "priya@example.com")).json()
    response = client.post("/v1/portal/application-status", json={"reference_code": created["reference_code"], "email": "priya@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"reference_code", "program", "submitted_at", "status", "raw_status", "full_name"}
    assert data["full_name"] == "Priya P."
    text = response.text
    for secret in ("9999999999", "2005-01-01", "personal statement", "priya@example.com"):
        assert secret not in text


def test_status_lookup_is_rate_limited(client):
    body = {"reference_code": "CAP-20260101-AAAAAA", "email": "nobody@example.com"}
    for _ in range(10):
        assert client.post("/v1/portal/application-status", json=body).status_code == 404
    assert client.post("/v1/portal/application-status", json=body).status_code == 429
