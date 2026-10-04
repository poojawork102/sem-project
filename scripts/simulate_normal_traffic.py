"""Create approved-looking traffic needed to train the Isolation Forest baseline."""
import argparse
import os
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000/v1/submissions")
parser.add_argument("--count", type=int, default=25)
parser.add_argument("--api-key", default=os.environ.get("SUBMISSIONS_API_KEY", ""), help="X-API-Key for /v1/submissions (defaults to $SUBMISSIONS_API_KEY)")
args = parser.parse_args()
headers = {"X-API-Key": args.api_key} if args.api_key else {}
for i in range(args.count):
    response = httpx.post(args.url, json={"full_name": f"Normal Student {i}", "email": f"normal.student.{i}@gmail.com", "ip_address": f"198.51.100.{i + 10}", "payload": {"course": "CSE", "city": "Pune"}}, headers=headers, timeout=5)
    print(response.status_code, response.json().get("action"))
