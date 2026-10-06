# AdmitShield

Working college-admission portal plus the **Data Shuffling Attack Detection and Prevention System** described in the supplied SRS. Every applicant submission passes through the security agent before being recorded.

## What is implemented

| SRS requirement | Implementation |
| --- | --- |
| REQ-1 flood detection | rolling 5-minute counter; configurable 700-submission threshold |
| REQ-2 duplicate detection | exact email and 90% name-similarity checks; indexed database fields |
| REQ-3 per-IP rate limiting | configurable 3 submissions per minute signal |
| REQ-4 and REQ-5 risk score | explainable weighted score: IP 40%, duplicate 30%, velocity 30% |
| AI anomaly detection | optional Isolation Forest trained only from approved normal submissions; shown separately from the SRS rule score |
| REQ-6 to REQ-8 actions | allow below 40, CAPTCHA at 40–80, block above 80 |
| REQ-9 and REQ-10 dashboard | authenticated live dashboard, activity feed, and admin override endpoint |
| REQ-11 reporting | midnight UTC daily CSV generation, authenticated export, and weekly trend graph |
| REQ-12 safe cleanup | only applications explicitly marked `confirmed_spam` can be deleted; audit rows remain |

## Run locally

1. Install Python 3.12 and create a virtual environment.

   ```powershell
   cd sem-project
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

2. Open `.env` and set a strong `JWT_SECRET` and a non-default `ADMIN_PASSWORD`. **The server refuses to start with the placeholder values.** Set `SUBMISSIONS_API_KEY` too if an external system will call `/v1/submissions` (it is disabled while empty).

3. Start the API.

   ```powershell
   uvicorn app.main:app --reload
   ```

4. Open `http://127.0.0.1:8000/` for the applicant admission portal, `http://127.0.0.1:8000/admin` for the protected dashboard, or `http://127.0.0.1:8000/docs` for the API. Use `POST /v1/submissions` (header `X-API-Key`) as the integration endpoint for an external admission portal; the built-in portal uses `/v1/portal/applications`, which takes the applicant IP from the connection itself.

5. Simulate repeated bot submissions in a second terminal.

   ```powershell
   python scripts/simulate_attack.py --attack --count 6 --api-key <SUBMISSIONS_API_KEY>
   ```

6. Run the baseline tests.

   ```powershell
   python -m pytest
   ```

## Train the AI agent

The AI model needs at least 20 **normal, allowed** submissions before it can learn a baseline. With the API running, use a second terminal:

```powershell
python scripts/simulate_normal_traffic.py --count 25
```

Log in to the dashboard, click **Train AI agent**, then run a new attack simulation. The AI column will show a 0-100 anomaly score and `normal` or `anomaly`. The original rule score remains the authoritative SRS decision because it is directly explainable.

## Admin workflow

1. Call `POST /auth/login` with the credentials in `.env`; copy `access_token`.
2. In Swagger (`/docs`), click **Authorize** and enter `Bearer <access_token>`.
3. Review `GET /v1/admin/activity`, use the override endpoint where needed, and export the daily CSV.
4. Mark an application as `confirmed_spam=true` only after an admin review. The cleanup endpoint is intentionally unable to delete unconfirmed records.

## Important production work before launch

- Put the API behind HTTPS and an API gateway; never trust a user-provided IP header directly. Have the gateway inject a trusted client IP.
- Replace the demo single-admin environment credentials with your portal’s identity provider and role-based access control. Add 2FA if required.
- Use PostgreSQL, database migrations (Alembic), Redis for distributed rolling counters, a dedicated background worker for the included midnight report generation, and a real CAPTCHA provider such as Cloudflare Turnstile or hCaptcha.
- Train and evaluate the optional Isolation Forest only after collecting labelled, consented traffic. Keep these deterministic weighted signals as the administrator-facing explanation layer.
- Add a frontend dashboard after the API is stable. This backend already supplies the activity, override, and report endpoints it needs.

## Docker option

Set `POSTGRES_PASSWORD` (and the other secrets) in `.env`, then run:

```powershell
docker compose up --build
```

Compose points the API at the bundled Postgres automatically. The container runs as a non-root user and has a `/health` check.

## Security notes

- Scores, thresholds and reasons are admin-only; applicants only see the outcome and a reference code.
- Every page is served with a Content-Security-Policy (`script-src 'self'`); applicant text is HTML-escaped before display.
- The admin token lives in `sessionStorage` (cleared when the tab closes). Production should move to an HttpOnly cookie plus CSRF protection.
- Login attempts and status lookups are rate limited per IP, in memory (reset on restart, per process).
- The CAPTCHA decision is **recorded only**: no challenge is shown yet.
- The count-then-insert lock is per process; run a single worker or use a database lock for multiple workers.
- The chatbot sends applicant names (emails are masked) to Google Gemini; do not enable it for real applicant data without consent.

Never commit `.env`, database files, reports containing applicant data, or real CAPTCHA/email credentials.
