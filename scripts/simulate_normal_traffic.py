"""Create approved-looking traffic needed to train the Isolation Forest baseline."""
import argparse
import os
import httpx
from faker import Faker

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000/v1/submissions")
parser.add_argument("--count", type=int, default=25)
parser.add_argument("--api-key", default=os.environ.get("SUBMISSIONS_API_KEY", ""), help="X-API-Key for /v1/submissions (defaults to $SUBMISSIONS_API_KEY)")
args = parser.parse_args()
headers = {"X-API-Key": args.api_key} if args.api_key else {}
# Faker gives realistic, dissimilar names; 'Normal Student N' names were ~94% similar to each
# other and polluted the Isolation Forest baseline with duplicate-name scores.
fake = Faker("en_IN")
for i in range(args.count):
    name = fake.name()
    response = httpx.post(args.url, json={"full_name": name, "email": f"{name.lower().replace(' ', '.')}.{i}@gmail.com", "ip_address": f"198.51.100.{i + 10}", "payload": {"course": "CSE", "city": "Pune"}}, headers=headers, timeout=5)
    print(response.status_code, response.json().get("action"))
