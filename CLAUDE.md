# CLAUDE.md — DSADPS (Data Shuffling Attack Detection & Prevention System)

College-admission portal + security agent. Every submission is scored (rules + ML) and gets allow / captcha / block.
Stack: FastAPI, SQLAlchemy (SQLite dev / Postgres Docker), scikit-learn Isolation Forest, XGBoost, Gemini chatbot, vanilla JS dashboard.
This is a university PBL project that must be explained in a viva — prefer clear, explainable code over clever code.

## Environment (Windows, CMD)
- Python 3.11 venv: `.venv\Scripts\activate.bat`
- Run server: `uvicorn app.main:app --reload` (restart after editing `.env`; --reload ignores it)
- Tests: `python -m pytest` (plain `pytest` fails until pyproject.toml is added)
- Simulators: `python scripts\simulate_normal_traffic.py --count 25`, `python scripts\simulate_attack.py --attack --count 6`
- Reset data: stop server, `rmdir /s /q data`

## Rules
- Never read, print, or commit `.env`, `data/`, `reports/`, or API keys.
- One focused change per commit, conventional message (`fix:`, `feat:`, `test:`, `ci:`, `refactor:`, `docs:`).
- Work on a branch, never directly on `main`.
- Add or update a test for every bug fix.
- Keep the SRS rule score as the authoritative, explainable decision; ML is supplementary.
- Explain each change briefly so the owner can defend it in a viva.

## Backlog (do in order, one phase per branch)

### Phase 1 — Security (branch: fix/security)
1. Stored XSS: admin.js / portal.js render applicant fields via innerHTML unescaped; JWT in localStorage. Add an `esc()` helper or use textContent everywhere.
2. `/v1/submissions` is unauthenticated and trusts client `ip_address` → IP rate limit bypassable. Require an API key for this endpoint or derive IP server-side.
3. Remove the hardcoded "Demo Credentials" box from the admin login page.
4. Block is unreachable: max IP(40)+duplicate(30)=70 → captcha. Add a hard rule (e.g. IP over limit AND duplicate → block) or rebalance; keep reasons explainable.
5. Fail at startup if JWT_SECRET / ADMIN_PASSWORD are defaults. Use `secrets.compare_digest` in login; add login attempt limiting.
6. Count-then-insert race in `analyse_submission` (concurrent requests bypass limits) — document or mitigate.
7. CAPTCHA action is never enforced — implement (e.g. Cloudflare Turnstile) or clearly label as simulated.
8. Status lookup returns PII (phone, DOB, statement) with only a 6-hex ref code; limit fields + rate limit.

### Phase 2 — Bugs + tests (branch: fix/logic-tests)
1. Duplicate check: `limit(1000)` without order_by scans oldest rows; email match done in Python. Query email directly (lowercased), compare names against recent rows ordered by submitted_at desc.
2. `simulate_normal_traffic.py` names ("Normal Student N") are 94% similar → baseline rows get duplicate score 30, polluting Isolation Forest training. Use Faker names.
3. `models.py` Application.status default "allowed" vs code using "allow". Introduce a status Enum.
4. `seed_data.py` writes statuses directly and `import_csv.py` skips ML — both must reuse the single submission pipeline.
5. 90% name similarity alone false-positives common names (Priya Patil/Patel) — only count with another signal.
6. Add pyproject.toml (`[tool.pytest.ini_options] pythonpath = ["."]`), conftest.py with TestClient + in-memory SQLite, ~15-20 tests: allow path, IP escalation, duplicate email, 401 without token, cleanup only deletes confirmed spam and keeps audit rows, override updates both tables, XSS regression.

### Phase 3 — DevSecOps CI (branch: ci/pipeline)
- `.github/workflows/ci.yml`: ruff, pytest, bandit, pip-audit, trivy (image), gitleaks.
- `requirements-dev.txt` for pytest/ruff/faker; pre-commit config.
- Dockerfile: non-root USER, HEALTHCHECK on /health. Fix compose (psycopg missing, stray sqlite volume).

### Phase 4 — Refactor (branch: refactor/structure)
- Split main.py into routers/ (portal, admin, auth) + services/submission.py.
- One features.py shared by detector, Isolation Forest, XGBoost (currently 3 extractors, ~10 queries/submission).
- Load ML models once and cache; reload after training (currently joblib.load per request).
- XGBoost: held-out test split; stop reporting training accuracy; labels from admin overrides, not rule output.
- `payload` → JSON column; pagination on admin list endpoints.

### Phase 5 — Ops (branch: feat/observability)
- Structured logging for decisions, logins, overrides, cleanup. Replace bare `except Exception`.
- Alembic migrations instead of ensure_schema ALTERs.
- Replace deprecated: on_event → lifespan, datetime.utcnow → timezone-aware, google-generativeai → google-genai, xgboost use_label_encoder.
- Chatbot sends applicant PII to Gemini + prompt-injection via applicant names — mask fields, document limitation.

### Phase 6 — Presentation (branch: docs/readme)
- Rename GitHub repo to admitshield (UI rename itself is in Phase 7).
- Rewrite README (fix `cd dsadps-agent`, remove boilerplate GitHub section, add architecture, screenshots, known limitations, XGBoost + chatbot).
- docs/ with SRS + DFDs; LICENSE (MIT); repo description + topics.
- Frontend cleanup: split admin.js, move 91 inline styles to CSS.

### Phase 7 — Rename + UI palette (branch: feat/ui-refresh, created from fix/security)
Name: **AdmitShield** (tagline "Admissions security"). The user-facing UI must never show "DSADPS".
- Admin brand: "AdmitShield" + small "Admissions security" under it. Badge: "Protection active".
- Portal copy: say "automatic security check", not DSADPS. Backend names, file names, env vars, and the SRS title may keep DSADPS.
- Also update: FastAPI title, HTML <title>s, reports.py chart title, README heading.
- Remove the hardcoded "Demo Credentials" box on the admin login (Phase 1 item 3 is done here, not in fix/security).
- Remove fake marketing stats (98.4%, 45+, $42M, 18k+); use real content or [PLACEHOLDER].

Step A (no visual change): move every inline style="" in admin.js, portal.js, index.html, portal.html into CSS classes, and replace hardcoded hex colours with design-system.css tokens. Before/after must look identical.

Step B (apply palette). Portal + shared tokens in design-system.css :root:
```
--bg-main:#FFFBEF; --bg-card:#FFFFFF; --bg-card-subtle:#FFF4D1; --bg-raised:#FFFDF7;
--butter-100:#FFF6D6; --butter-200:#FFEDB0; --butter-300:#FDE38A;
--lavender-50:#F6F2FF; --lavender-100:#ECE5FF; --lavender-200:#DACFFF; --lavender-400:#9C87F5;
--brand-purple:#6D4FE0; --brand-purple-hover:#5A3DC8; --brand-purple-deep:#432C9A; --brand-glow:rgba(109,79,224,.22);
--text-primary:#241A3D; --text-secondary:#5B5270; --text-muted:#8A8299; --border-light:rgba(36,26,61,.09);
--success:#2F9E6E; --success-bg:#E6F6EE; --success-text:#1D6B4A;
--warning:#E0782A; --warning-bg:#FFEDDC; --warning-text:#9A4A12;
--danger:#D9445A; --danger-bg:#FDE8EC; --danger-text:#9B2337;
--info:#6D4FE0; --info-bg:#F6F2FF; --info-text:#432C9A;
--shadow-sm:0 1px 0 rgba(255,255,255,.9) inset,0 1px 2px rgba(36,26,61,.06),0 2px 6px -2px rgba(67,44,154,.10);
--shadow-md:0 1px 0 rgba(255,255,255,.9) inset,0 2px 4px rgba(36,26,61,.05),0 10px 24px -8px rgba(67,44,154,.18);
--shadow-lg:0 1px 0 rgba(255,255,255,.9) inset,0 4px 8px rgba(36,26,61,.05),0 24px 48px -12px rgba(67,44,154,.24);
```
Admin dashboard (index.html) gets class `admin-theme` on <body> (dark aubergine, option B):
```
--bg-main:#14101F; --bg-sidebar:#100C1A; --bg-card:#1C1630; --bg-card-subtle:#251D3D; --bg-raised:#2F2550;
--border-light:rgba(255,255,255,.07); --text-primary:#F1ECFF; --text-secondary:#B3A9CC; --text-muted:#8A80A6;
--brand-purple:#B09BFF; --on-brand:#1A1230; --butter-accent:#FFE08A;
--success:#5EE0A8; --success-bg:rgba(94,224,168,.14);
--warning:#FFA45C; --warning-bg:rgba(255,164,92,.14);
--danger:#FF7A8A; --danger-bg:rgba(255,122,138,.14);
--shadow-md:0 1px 0 rgba(255,255,255,.04) inset,0 8px 24px -6px rgba(0,0,0,.55);
```
Rules: butter is never text colour and never a status colour. Warning is orange, not yellow. One filled purple button per view; others outlined. Active nav item gets a 3px butter inset bar. Cards: 18-20px radius + inset top highlight. Portal nav labels short and white-space:nowrap (Programs, Dashboard, Apply, Status, Documents, FAQ). Font: Plus Jakarta Sans for everything (drop Inter), JetBrains Mono for IPs/scores/refs.
Reference preview: https://claude.ai/artifact/UFcXpEYmCxkz14VaZ28atD
