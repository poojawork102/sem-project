"""Create approved-looking traffic needed to train the Isolation Forest baseline."""
import argparse
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000/v1/submissions")
parser.add_argument("--count", type=int, default=25)
args = parser.parse_args()
for i in range(args.count):
    response = httpx.post(args.url, json={"full_name": f"Normal Student {i}", "email": f"normal.student.{i}@gmail.com", "ip_address": f"198.51.100.{i + 10}", "payload": {"course": "CSE", "city": "Pune"}}, timeout=5)
    print(response.status_code, response.json().get("action"))
