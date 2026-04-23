import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json

BASE = "https://oko.ag3nts.org"
HUB = "https://hub.ag3nts.org/verify"
API_KEY = os.getenv("CENTRAL_TOKEN")

# First check what the old session shows when browsing
old_cookies = {}
try:
    with open("/tmp/oko_cookies.txt") as f:
        for line in f:
            if not line.startswith("#") and line.strip():
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    old_cookies[parts[5]] = parts[6]
    print("Old cookies:", old_cookies)
except Exception as e:
    print(f"Error reading cookies: {e}")

# Try to GET the root page with old cookies to see if ban page shows
s = requests.Session()
if old_cookies:
    s.cookies.update(old_cookies)

r = s.get(BASE + "/")
print(f"\nGET / with old cookies: {r.status_code}, len={len(r.text)}")

if "zorientowali" in r.text or "naruszenie" in r.text:
    print("Old session is in ban state - submitting logout to unban")
    r2 = s.post(BASE + "/", data={"action": "logout"})
    print(f"Logout: {r2.status_code}")

    # Check hub API
    r3 = requests.post(HUB, json={
        "apikey": API_KEY, "task": "okoeditor", "answer": {"action": "help"}
    })
    print(f"Hub after logout: {r3.status_code}")
    print(json.dumps(r3.json(), indent=2, ensure_ascii=False))
else:
    print("Old session shows normal page, not ban page")
    # Show title
    import re
    title = re.search(r"<title>(.*?)</title>", r.text)
    if title:
        print(f"Page title: {title.group(1)}")

# Check hub API current state
print("\n--- Current hub API state ---")
r = requests.post(HUB, json={
    "apikey": API_KEY, "task": "okoeditor", "answer": {"action": "help"}
})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
