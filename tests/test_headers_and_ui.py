"""Security headers, and a guard that the static pages stay CSP-compatible."""
from pathlib import Path

STATIC = Path("app/static")


def test_pages_send_csp_and_hardening_headers(api):
    for path in ("/", "/admin"):
        response = api.get(path)
        csp = response.headers["content-security-policy"]
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"


def test_api_responses_are_not_cached(api):
    response = api.post("/auth/login", json={"username": "x", "password": "y"})
    assert response.headers["cache-control"] == "no-store"


def test_no_inline_event_handlers_or_scripts():
    """CSP blocks inline handlers, so they would silently break; keep them out of the source."""
    for file in list(STATIC.glob("*.html")) + list(STATIC.glob("js/*.js")):
        text = file.read_text(encoding="utf-8")
        assert 'onclick="' not in text, f"inline onclick in {file}"
        assert "javascript:" not in text, f"javascript: URL in {file}"
    for html in STATIC.glob("*.html"):
        assert "<script>" not in html.read_text(encoding="utf-8"), f"inline script in {html}"


def test_login_form_has_no_prefilled_credentials():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    login = html[html.index('id="loginForm"'):html.index("</form>", html.index('id="loginForm"'))]
    assert "value=" not in login
    assert "Demo Credentials" not in html


def test_admin_token_is_not_kept_in_localstorage():
    api_js = (STATIC / "js" / "api.js").read_text(encoding="utf-8")
    assert "localStorage.setItem(this.TOKEN_KEY" not in api_js
