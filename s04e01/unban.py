import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json

BASE = "https://oko.ag3nts.org"
HUB = "https://hub.ag3nts.org/verify"
API_KEY = os.getenv("CENTRAL_TOKEN")
LOGIN_DATA = {
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": API_KEY
}

session = requests.Session()

# Login
r = session.post(BASE + "/", data=LOGIN_DATA)
print(f"Login: {r.status_code}")

# Check what page we landed on
if "zorientowali" in r.text or "naruszenie" in r.text:
    print("Got security/ban page - will logout to unban")
    # Submit the logout form
    r2 = session.post(BASE + "/", data={"action": "logout"})
    print(f"Logout: {r2.status_code}, chars: {len(r2.text)}")

    # Re-login
    r3 = session.post(BASE + "/", data=LOGIN_DATA)
    print(f"Re-login: {r3.status_code}")
    if "zorientowali" in r3.text:
        print("Still on ban page")
    elif "Ostatnie incydenty" in r3.text:
        print("Successfully re-logged in!")
else:
    print("Landed on normal page, no ban detected in web session")

# Check if API key ban is cleared
r = requests.post(HUB, json={
    "apikey": API_KEY,
    "task": "okoeditor",
    "answer": {"action": "help"}
})
print(f"\nHub API status: {r.status_code}")
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
