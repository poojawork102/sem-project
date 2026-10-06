"""Detection logic, admin workflow and applicant-facing privacy."""
from app.detector import analyse_submission, choose_action
from app.models import Action, ActivityLog, Application


def portal_body(name="Asha Verma", email="asha@example.com", **extra):
    body = {"full_name": name, "email": email, "phone": "9999999999", "program": "BTech CSE",
            "date_of_birth": "2005-01-01", "city": "Pune",
            "statement": "This is a sufficiently long personal statement for validation."}
    body.update(extra)
    return body


def add_application(db, name, email, ip="10.1.1.1", status="allow", **kw):
    row = Application(full_name=name, email=email, ip_address=ip, status=status, payload="{}", **kw)
    db.add(row)
    db.commit()
    return row


# ---- detection ---------------------------------------------------------------

def test_clean_submission_is_allowed(api):
    body = api.post("/v1/portal/applications", json=portal_body()).json()
    assert body["action"] == "allow"
    assert body["reference_code"].startswith("CAP-")


def test_default_status_matches_action_enum(db_factory):
    with db_factory() as db:
        row = Application(full_name="No Status", email="n@example.com", ip_address="1.1.1.1", payload="{}")
        db.add(row)
        db.commit()
        assert row.status == Action.ALLOW.value


def test_duplicate_email_is_found_case_insensitively(db_factory):
    with db_factory() as db:
        add_application(db, "Old Person", "Mixed.Case@Example.com")
        score, reasons = analyse_submission(db, "Someone Else", "mixed.case@example.com", "10.9.9.9")
    assert score >= 30
    assert any("Email exactly matches" in r for r in reasons)


def test_duplicate_email_found_even_when_more_than_1000_newer_rows(db_factory):
    """Regression: the old limit(1000) scan missed matches older than the first 1000 rows."""
    with db_factory() as db:
        add_application(db, "Very Old", "old.one@example.com")
        db.add_all([Application(full_name=f"Filler {i}", email=f"f{i}@example.com", ip_address=f"10.0.{i // 250}.{i % 250}", status="allow", payload="{}") for i in range(1100)])
        db.commit()
        _, reasons = analyse_submission(db, "Brand New", "old.one@example.com", "10.8.8.8")
    assert any("Email exactly matches" in r for r in reasons)


def test_similar_name_alone_is_not_a_duplicate(db_factory):
    """Regression: Priya Patil / Priya Patel are different people when nothing else matches."""
    with db_factory() as db:
        add_application(db, "Priya Patil", "priya.patil@example.com", ip="10.1.1.1")
        score, reasons = analyse_submission(db, "Priya Patel", "priya.patel@example.com", "10.2.2.2")
    assert choose_action(score) == "allow"
    assert any("not counted alone" in r for r in reasons)


def test_similar_name_plus_same_ip_counts(db_factory):
    with db_factory() as db:
        add_application(db, "Priya Patil", "priya.patil@example.com", ip="10.1.1.1")
        _, reasons = analyse_submission(db, "Priya Patel", "priya.patel@example.com", "10.1.1.1")
    assert any("same IP/flood signal agrees" in r for r in reasons)


def test_ip_escalation_reaches_captcha_then_block(api):
    actions = [api.post("/v1/portal/applications", json=portal_body(f"Person Number{chr(97 + i) * 3}", f"p{i}@example.com")).json()["action"] for i in range(4)]
    assert actions[:3] == ["allow", "allow", "allow"]
    assert actions[3] == "captcha"  # 4th request from the same IP in a minute
    repeat = api.post("/v1/portal/applications", json=portal_body("Zed Quill", "p0@example.com")).json()
    assert repeat["action"] == "block"  # over the IP limit AND a duplicate email


# ---- applicant privacy ---------------------------------------------------------

def test_portal_response_hides_score_and_reasons(api):
    body = api.post("/v1/portal/applications", json=portal_body()).json()
    assert set(body) == {"action", "created_at", "reference_code", "captcha_simulated", "notice"}


def test_status_lookup_ignores_email_case(api):
    ref = api.post("/v1/portal/applications", json=portal_body(email="Asha@Example.com")).json()["reference_code"]
    response = api.post("/v1/portal/application-status", json={"reference_code": ref.lower(), "email": "asha@example.com"})
    assert response.status_code == 200


def test_oversized_submission_is_rejected(api):
    response = api.post("/v1/portal/applications", json=portal_body(junk="x" * 25_000))
    assert response.status_code == 413


# ---- admin auth + workflow -------------------------------------------------------

def test_admin_endpoints_require_token(api):
    for path in ("/v1/admin/applications", "/v1/admin/activity", "/v1/admin/reports/summary", "/v1/admin/ai/status"):
        assert api.get(path).status_code in (401, 403), path
    assert api.post("/v1/admin/cleanup").status_code in (401, 403)
    assert api.post("/v1/admin/chat", json={"message": "hi"}).status_code in (401, 403)


def test_forged_token_is_rejected(api):
    assert api.get("/v1/admin/applications", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


def test_cleanup_deletes_only_confirmed_spam_and_keeps_audit_rows(api, admin_headers, db_factory):
    for i in range(3):
        api.post("/v1/portal/applications", json=portal_body(f"Cleanup Person{chr(97 + i) * 3}", f"c{i}@example.com"))
    apps = api.get("/v1/admin/applications", headers=admin_headers).json()
    spam_id = apps[0]["id"]
    assert api.put(f"/v1/admin/applications/{spam_id}/spam", params={"confirmed": True}, headers=admin_headers).status_code == 200
    result = api.post("/v1/admin/cleanup", headers=admin_headers).json()
    assert result["deleted_confirmed_spam_records"] == 1
    with db_factory() as db:
        assert db.query(Application).count() == 2
        assert db.query(ActivityLog).count() == 3  # audit rows are retained


def test_override_updates_application_and_audit_log(api, admin_headers, db_factory):
    api.post("/v1/portal/applications", json=portal_body())
    row = api.get("/v1/admin/applications", headers=admin_headers).json()[0]
    response = api.put(f"/v1/admin/activity/{row['activity_id']}/override", json={"action": "block", "note": "manual review"}, headers=admin_headers)
    assert response.status_code == 200
    with db_factory() as db:
        assert db.get(Application, row["id"]).status == "block"
        log = db.get(ActivityLog, row["activity_id"])
        assert log.final_action == "block" and log.admin_override_by == "admin"
        assert log.suggested_action == "allow"  # original decision stays in the audit trail


def test_override_rejects_unknown_action(api, admin_headers):
    api.post("/v1/portal/applications", json=portal_body())
    row = api.get("/v1/admin/applications", headers=admin_headers).json()[0]
    response = api.put(f"/v1/admin/activity/{row['activity_id']}/override", json={"action": "allowed", "note": "typo"}, headers=admin_headers)
    assert response.status_code == 422
