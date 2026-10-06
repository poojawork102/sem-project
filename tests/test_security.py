from fastapi.testclient import TestClient
from app.config import settings
from app.main import app

client = TestClient(app)

PAYLOAD = {
    "full_name": "Security Test Applicant",
    "email": "security.test.applicant@example.com",
    "ip_address": "203.0.113.50",
    "payload": {"course": "CSE"},
}


def test_submissions_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "submissions_api_key", "correct-key")
    response = client.post("/v1/submissions", json=PAYLOAD)
    assert response.status_code == 401


def test_submissions_rejects_wrong_api_key(monkeypatch):
    monkeypatch.setattr(settings, "submissions_api_key", "correct-key")
    response = client.post("/v1/submissions", json=PAYLOAD, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_submissions_disabled_when_key_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "submissions_api_key", "")
    response = client.post("/v1/submissions", json=PAYLOAD, headers={"X-API-Key": "anything"})
    assert response.status_code == 401


def test_submissions_accepts_correct_api_key(monkeypatch):
    monkeypatch.setattr(settings, "submissions_api_key", "correct-key")
    response = client.post("/v1/submissions", json=PAYLOAD, headers={"X-API-Key": "correct-key"})
    assert response.status_code == 200
    assert "action" in response.json()


def test_portal_applications_stays_unauthenticated(monkeypatch):
    """/v1/portal/applications is for real applicants and must never require the key."""
    monkeypatch.setattr(settings, "submissions_api_key", "correct-key")
    response = client.post("/v1/portal/applications", json={
        "full_name": "Portal Test Applicant",
        "email": "portal.test.applicant@example.com",
        "phone": "9999999999",
        "program": "BTech Computer Science",
        "date_of_birth": "2005-01-01",
        "city": "Pune",
        "statement": "This is a sufficiently long personal statement for validation.",
    })
    assert response.status_code == 200
