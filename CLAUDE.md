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
- Rename project (candidate: AdmitShield), update FastAPI title, HTML titles, chart title.
- Rewrite README (fix `cd dsadps-agent`, remove boilerplate GitHub section, add architecture, screenshots, known limitations, XGBoost + chatbot).
- docs/ with SRS + DFDs; LICENSE (MIT); repo description + topics.
- Frontend cleanup: split admin.js, move 91 inline styles to CSS.
