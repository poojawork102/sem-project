"""Generate portal-like traffic to demonstrate normal, duplicate, and flood signals."""
import argparse
import os
import random
import time
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000/v1/submissions")
parser.add_argument("--count", type=int, default=10)
parser.add_argument("--attack", action="store_true")
parser.add_argument("--api-key", default=os.environ.get("SUBMISSIONS_API_KEY", ""), help="X-API-Key for /v1/submissions (defaults to $SUBMISSIONS_API_KEY)")
args = parser.parse_args()
headers = {"X-API-Key": args.api_key} if args.api_key else {}
for i in range(args.count):
    ip = "203.0.113.9" if args.attack else f"198.51.100.{i % 50 + 1}"
    payload = {"full_name": "Attack Bot" if args.attack else f"Student {i}", "email": "attack@example.com" if args.attack else f"student{i}@example.com", "ip_address": ip, "payload": {"course": "CSE"}}
    response = httpx.post(args.url, json=payload, headers=headers, timeout=5)
    print(response.status_code, response.json())
    time.sleep(0.05)
