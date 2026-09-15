"""Generate portal-like traffic to demonstrate normal, duplicate, and flood signals."""
import argparse
import random
import time
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000/v1/submissions")
parser.add_argument("--count", type=int, default=10)
parser.add_argument("--attack", action="store_true")
args = parser.parse_args()
for i in range(args.count):
    ip = "203.0.113.9" if args.attack else f"198.51.100.{i % 50 + 1}"
    payload = {"full_name": "Attack Bot" if args.attack else f"Student {i}", "email": "attack@example.test" if args.attack else f"student{i}@example.test", "ip_address": ip, "payload": {"course": "CSE"}}
    response = httpx.post(args.url, json=payload, timeout=5)
    print(response.status_code, response.json())
    time.sleep(0.05)

