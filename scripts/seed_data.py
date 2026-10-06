"""
Seed the DSADPS database with ~500 realistic college admission applications.

Usage:
    python scripts/seed_data.py              # wipe + seed 500 records
    python scripts/seed_data.py --append     # keep existing data, add more
    python scripts/seed_data.py --count 200  # custom count
    python scripts/seed_data.py --no-train   # skip AI model training
"""
import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from app.database import SessionLocal, ensure_schema
from pydantic import ValidationError
from app.models import ActivityLog, Application
from app.schemas import SubmissionIn
from app.submission import process_submission

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROGRAMS = [
    "Computer Science & AI",
    "Data Science & Analytics",
    "Business Administration",
    "Psychology & Behavioral Science",
    "Mechanical Engineering",
    "Electrical Engineering",
    "Civil Engineering",
    "Biotechnology",
    "Economics",
    "Media & Communications",
    "Mathematics",
    "Physics",
    "Environmental Science",
    "Law & Public Policy",
]

INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh", "Bhopal",
    "Nagpur", "Indore", "Coimbatore", "Thiruvananthapuram", "Kochi",
    "Visakhapatnam", "Mysore", "Noida", "Gurgaon", "Patna", "Ranchi",
    "Dehradun", "Surat", "Vadodara",
]

STATEMENTS = [
    "I am passionate about leveraging technology to solve real-world problems. "
    "My experience in competitive programming and open-source contributions has "
    "prepared me to thrive in a rigorous academic environment.",

    "Growing up in a small town, I witnessed the transformative power of education. "
    "I aspire to pursue higher studies to contribute to my community and drive "
    "meaningful change through innovation.",

    "My internship at a leading research lab ignited my interest in data-driven "
    "decision making. I am eager to explore advanced analytical methods and their "
    "applications in healthcare and sustainability.",

    "As the first in my family to pursue a professional degree, I bring a unique "
    "perspective and unwavering determination. I believe in lifelong learning and "
    "aim to bridge the gap between theory and practice.",

    "I have always been fascinated by the intersection of business and technology. "
    "My goal is to develop innovative solutions that address the needs of underserved "
    "markets while creating sustainable social impact.",

    "My academic journey has been shaped by curiosity and perseverance. From "
    "participating in science olympiads to leading student organizations, I have "
    "consistently sought opportunities for intellectual growth.",

    "Having volunteered at rural schools for two years, I understand the challenges "
    "in our education system. I want to apply scientific thinking to design scalable "
    "solutions for learning accessibility.",

    "I am drawn to the interdisciplinary nature of this program. Combining my "
    "background in mathematics with domain expertise will help me tackle complex "
    "problems in finance and operations research.",

    "Through my projects in embedded systems and IoT, I have developed a strong "
    "foundation in both hardware and software. I look forward to pushing the "
    "boundaries of smart infrastructure at Northstar University.",

    "My passion for behavioral science began when I observed how subtle design "
    "changes could dramatically improve user engagement. I am excited to explore "
    "the cognitive science behind human decision-making.",
]

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_dob() -> str:
    """Date of birth for a typical 17-22 year old applicant."""
    age = random.randint(17, 22)
    dob = datetime.now() - timedelta(days=age * 365 + random.randint(0, 364))
    return dob.strftime("%Y-%m-%d")


def random_phone() -> str:
    return f"+91-{random.randint(70000, 99999)}{random.randint(10000, 99999)}"


def random_ip(pool=None) -> str:
    if pool:
        return random.choice(pool)
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


# ---------------------------------------------------------------------------
# Seed generators
# ---------------------------------------------------------------------------

def generate_normal(count, base_time):
    """Normal applicants - unique names, diverse IPs, low risk."""
    records = []
    for i in range(count):
        offset = timedelta(
            days=random.uniform(0, 7),
            hours=random.uniform(0, 23),
            minutes=random.uniform(0, 59),
        )
        submitted_at = base_time - offset
        name = fake.name()
        email_base = name.lower().replace(" ", ".").replace("..", ".")
        email = f"{email_base}{random.randint(1, 999)}@{random.choice(['gmail.com', 'yahoo.co.in', 'outlook.com', 'hotmail.com', 'protonmail.com'])}"
        program = random.choice(PROGRAMS)
        city = random.choice(INDIAN_CITIES)
        ip = random_ip()

        records.append({
            "full_name": name,
            "email": email,
            "phone": random_phone(),
            "program": program,
            "ip_address": ip,
            "submitted_at": submitted_at,
            "confirmed_spam": False,
            "payload": {
                "date_of_birth": random_dob(),
                "city": city,
                "statement": random.choice(STATEMENTS),
                "phone": random_phone(),
                "program": program,
            },
        })
    return records


def generate_suspicious(count, base_time, normal_names):
    """Suspicious applicants - duplicate emails, similar names, repeated IPs."""
    records = []
    suspicious_ips = [random_ip() for _ in range(5)]

    for i in range(count):
        offset = timedelta(
            days=random.uniform(0, 7),
            hours=random.uniform(0, 23),
            minutes=random.uniform(0, 59),
        )
        submitted_at = base_time - offset
        ip = random_ip(suspicious_ips)

        strategy = random.choice(["duplicate_email", "similar_name", "same_ip"])
        has_dup_email = False
        has_sim_name = False
        ip_hits = random.randint(1, 2)

        if strategy == "duplicate_email":
            base_name = random.choice(normal_names)
            name = fake.name()
            email = f"{base_name.lower().replace(' ', '.').replace('..', '.')}@gmail.com"
            has_dup_email = True
        elif strategy == "similar_name":
            base_name = random.choice(normal_names)
            parts = base_name.split()
            name = parts[0] + " " + fake.last_name() if len(parts) > 1 else base_name + "a"
            email = f"{name.lower().replace(' ', '.')}{random.randint(1, 99)}@{random.choice(['gmail.com', 'yahoo.co.in'])}"
            has_sim_name = random.random() > 0.4
        else:
            name = fake.name()
            email = f"{name.lower().replace(' ', '.')}{random.randint(1, 99)}@gmail.com"
            ip_hits = random.randint(2, 4)

        program = random.choice(PROGRAMS)
        city = random.choice(INDIAN_CITIES)

        records.append({
            "full_name": name,
            "email": email,
            "phone": random_phone(),
            "program": program,
            "ip_address": ip,
            "submitted_at": submitted_at,
            "confirmed_spam": False,
            "payload": {
                "date_of_birth": random_dob(),
                "city": city,
                "statement": random.choice(STATEMENTS),
                "phone": random_phone(),
                "program": program,
            },
        })
    return records


def generate_attacks(count, base_time):
    """Attack-pattern applicants - rapid-fire from same IP, identical emails, flood."""
    records = []
    attack_ips = [random_ip() for _ in range(3)]
    attack_emails = ["bot.attacker@tempmail.org", "spam.flood@throwaway.com", "fake.apps@mailinator.com"]

    burst_start = base_time
    for i in range(count):
        # A bot fires in bursts: ~6 submissions seconds apart from one IP, then a quiet gap.
        # The pipeline only sees an "IP over its limit" if they land inside one minute.
        if i % 6 == 0:
            burst_start = base_time - timedelta(days=random.randint(0, 6), hours=random.uniform(0, 20))
            ip = random.choice(attack_ips)
        submitted_at = burst_start + timedelta(seconds=(i % 6) * 5)

        name = random.choice(["Attack Bot", "Test User", "Spam Account", "Fake Applicant", "Bot Submit"])
        email = random.choice(attack_emails)
        program = random.choice(PROGRAMS[:4])  # attackers usually target popular programs

        # Some attacks get manually confirmed as spam
        confirmed_spam = random.random() > 0.5

        records.append({
            "full_name": name,
            "email": email,
            "phone": "+91-0000000000",
            "program": program,
            "ip_address": ip,
            "submitted_at": submitted_at,
            "confirmed_spam": confirmed_spam,
            "payload": {
                "date_of_birth": "2000-01-01",
                "city": "Unknown",
                "statement": "automated submission " * 3,
                "phone": "+91-0000000000",
                "program": program,
            },
        })
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(total_count=500, append=False, train_model=True):
    Path("data").mkdir(exist_ok=True)
    ensure_schema()
    db = SessionLocal()

    if not append:
        print("Clearing existing data...")
        db.query(ActivityLog).delete()
        db.query(Application).delete()
        db.commit()

    base_time = datetime.utcnow()

    # Split: 70% normal, 20% suspicious, 10% attacks
    normal_count = int(total_count * 0.70)
    suspicious_count = int(total_count * 0.20)
    attack_count = total_count - normal_count - suspicious_count

    print(f"Generating {normal_count} normal + {suspicious_count} suspicious + {attack_count} attack records...")

    normal_records = generate_normal(normal_count, base_time)
    normal_names = [r["full_name"] for r in normal_records]
    suspicious_records = generate_suspicious(suspicious_count, base_time, normal_names)
    attack_records = generate_attacks(attack_count, base_time)

    all_records = normal_records + suspicious_records + attack_records
    random.shuffle(all_records)

    # Every record goes through the SAME pipeline as a live submission (rules + both ML
    # models + audit log), replayed in time order so the rate/flood windows make sense.
    # Nothing here writes a status by hand.
    decisions = {"allow": 0, "captcha": 0, "block": 0}
    inserted = skipped = spam_count = 0
    sample_allowed = []
    for rec in sorted(all_records, key=lambda r: r["submitted_at"]):
        try:
            data = SubmissionIn(full_name=rec["full_name"], email=rec["email"], ip_address=rec["ip_address"], payload=rec["payload"])
        except ValidationError:
            skipped += 1
            continue
        decision, application = process_submission(data, db, at=rec["submitted_at"])
        decisions[decision.action] += 1
        inserted += 1
        if rec["confirmed_spam"]:
            application.confirmed_spam = True
            spam_count += 1
        elif decision.action == "allow" and len(sample_allowed) < 5:
            sample_allowed.append((application.reference_code, rec["email"], rec["full_name"]))
    db.commit()

    print(f"\nInserted {inserted} records through the detection pipeline ({skipped} skipped as invalid).")
    print(f"  Allow:   {decisions['allow']}")
    print(f"  Captcha: {decisions['captcha']}")
    print(f"  Block:   {decisions['block']}")
    print(f"  Confirmed spam: {spam_count}")

    # Train the Isolation Forest model
    if train_model:
        print("\nTraining Isolation Forest model...")
        from app.ml_agent import train as train_ai
        result = train_ai(db)
        if result.get("trained"):
            print(f"  Model trained on {result['samples']} approved samples.")
        else:
            print(f"  Training skipped: {result.get('message', 'unknown reason')}")

    if sample_allowed:
        print("\nSample reference codes for portal 'Track Status' testing:")
        for ref, email, name in sample_allowed:
            print(f"  {ref}  |  {email}  |  {name}")

    db.close()
    print("\nDone! Start the server and visit:")
    print("  Student Portal: http://127.0.0.1:8000/")
    print("  Admin Dashboard: http://127.0.0.1:8000/admin")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the DSADPS database with realistic data.")
    parser.add_argument("--count", type=int, default=500, help="Total number of records to generate (default: 500)")
    parser.add_argument("--append", action="store_true", help="Keep existing data and add new records on top")
    parser.add_argument("--no-train", action="store_true", help="Skip AI model training after seeding")
    args = parser.parse_args()
    seed(total_count=args.count, append=args.append, train_model=not args.no_train)
