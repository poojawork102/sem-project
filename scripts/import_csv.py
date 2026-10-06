"""
Import applications from a CSV file into the DSADPS database.

Usage:
    python scripts/import_csv.py --file data/applicants.csv
    python scripts/import_csv.py --file data/applicants.csv --program "Computer Science & AI"
    python scripts/import_csv.py --file data/applicants.csv --ip 192.168.1.1 --dry-run

The importer auto-detects column mappings via fuzzy header matching.
Required columns: full_name (or name/student_name), email
Optional columns: phone, program, city, date_of_birth, statement, ip_address

Each record is run through the DSADPS detection engine so risk scores
and activity logs are populated automatically.
"""
import argparse
import csv
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, ensure_schema
from app.detector import analyse_submission, choose_action
from pydantic import ValidationError
from app.schemas import SubmissionIn
from app.submission import process_submission

# ---------------------------------------------------------------------------
# Column mapping - maps various header names to our canonical field names
# ---------------------------------------------------------------------------
COLUMN_ALIASES = {
    "full_name": ["full_name", "fullname", "name", "student_name", "student name",
                   "applicant_name", "applicant name", "candidate_name", "candidate name",
                   "first_name", "firstname"],
    "email": ["email", "email_address", "email address", "e-mail", "mail",
              "student_email", "applicant_email"],
    "phone": ["phone", "phone_number", "phone number", "mobile", "mobile_number",
              "contact", "contact_number", "tel", "telephone"],
    "program": ["program", "programme", "course", "department", "dept",
                "branch", "major", "stream", "field_of_study", "field of study"],
    "city": ["city", "location", "hometown", "home_city", "place", "address_city"],
    "date_of_birth": ["date_of_birth", "dob", "birth_date", "birthdate",
                       "date of birth", "birthday"],
    "statement": ["statement", "sop", "personal_statement", "personal statement",
                   "statement_of_purpose", "essay", "motivation", "cover_letter"],
    "ip_address": ["ip_address", "ip", "client_ip", "source_ip"],
}


def match_columns(headers):
    """Map CSV headers to canonical field names using fuzzy matching."""
    mapping = {}
    normalized_headers = [h.strip().lower().replace("-", "_") for h in headers]

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            for idx, header in enumerate(normalized_headers):
                if header == alias or SequenceMatcher(None, header, alias).ratio() > 0.85:
                    mapping[canonical] = idx
                    break
            if canonical in mapping:
                break

    return mapping


def import_csv(file_path, default_program="", default_ip="127.0.0.1", dry_run=False, train_model=True):
    Path("data").mkdir(exist_ok=True)
    ensure_schema()

    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    # Read CSV
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)

    print(f"Found {len(rows)} rows in {file_path}")
    print(f"Headers: {headers}")

    # Map columns
    mapping = match_columns(headers)
    print(f"\nColumn mapping detected:")
    for field, idx in mapping.items():
        print(f"  {field} <- '{headers[idx]}' (column {idx})")

    if "full_name" not in mapping:
        print("\nError: Could not find a 'name' or 'full_name' column. Please ensure your CSV has one.")
        print("Accepted headers: " + ", ".join(COLUMN_ALIASES["full_name"]))
        sys.exit(1)

    if "email" not in mapping:
        print("\nError: Could not find an 'email' column. Please ensure your CSV has one.")
        print("Accepted headers: " + ", ".join(COLUMN_ALIASES["email"]))
        sys.exit(1)

    if dry_run:
        print("\n--- DRY RUN (no data will be written) ---")

    db = SessionLocal()
    imported = 0
    skipped = 0
    risk_dist = {"allow": 0, "captcha": 0, "block": 0}

    for row_num, row in enumerate(rows, start=2):
        # Extract fields
        def get(field, default=""):
            idx = mapping.get(field)
            if idx is not None and idx < len(row):
                val = row[idx].strip()
                return val if val else default
            return default

        full_name = get("full_name")
        email = get("email")

        # Validate required fields
        if not full_name or len(full_name) < 2:
            print(f"  Row {row_num}: Skipped - missing or invalid name: '{full_name}'")
            skipped += 1
            continue
        if not email or "@" not in email:
            print(f"  Row {row_num}: Skipped - missing or invalid email: '{email}'")
            skipped += 1
            continue

        phone = get("phone", "+91-0000000000")
        program = get("program", default_program)
        city = get("city", "")
        dob = get("date_of_birth", "")
        statement = get("statement", "Imported application.")
        ip_address = get("ip_address", default_ip)

        payload = {
            "date_of_birth": dob,
            "city": city,
            "statement": statement,
            "phone": phone,
            "program": program,
        }
        try:
            data = SubmissionIn(full_name=full_name, email=email, ip_address=ip_address, payload=payload)
        except ValidationError as exc:
            print(f"  Row {row_num}: Skipped - {exc.errors()[0]['loc'][0]}: {exc.errors()[0]['msg']}")
            skipped += 1
            continue

        if dry_run:
            # Score only: analyse_submission reads the DB but writes nothing.
            score, _reasons = analyse_submission(db, full_name, email, ip_address)
            action = choose_action(score)
        else:
            # Same single pipeline as a live submission: rules + ML scores + audit log.
            decision, _application = process_submission(data, db)
            action = decision.action
        risk_dist[action] = risk_dist.get(action, 0) + 1
        imported += 1

    if not dry_run:
        db.commit()

    print(f"\n{'[DRY RUN] Would import' if dry_run else 'Imported'}: {imported} records")
    print(f"Skipped: {skipped} rows")
    print(f"Risk distribution:")
    print(f"  Allow:   {risk_dist.get('allow', 0)}")
    print(f"  Captcha: {risk_dist.get('captcha', 0)}")
    print(f"  Block:   {risk_dist.get('block', 0)}")

    if not dry_run and train_model and imported >= 20:
        print("\nTraining Isolation Forest model on imported data...")
        from app.ml_agent import train as train_ai
        result = train_ai(db)
        if result.get("trained"):
            print(f"  Model trained on {result['samples']} approved samples.")
        else:
            print(f"  Training skipped: {result.get('message', 'unknown reason')}")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import applications from a CSV file into DSADPS.")
    parser.add_argument("--file", "-f", required=True, help="Path to the CSV file")
    parser.add_argument("--program", default="", help="Default program for rows missing a program column")
    parser.add_argument("--ip", default="127.0.0.1", help="Default IP address for rows missing an IP column")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be imported without writing to DB")
    parser.add_argument("--no-train", action="store_true", help="Skip AI model training after import")
    args = parser.parse_args()
    import_csv(args.file, default_program=args.program, default_ip=args.ip, dry_run=args.dry_run, train_model=not args.no_train)
