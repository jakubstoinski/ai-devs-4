import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests

BASE = "https://oko.ag3nts.org"
LOGIN_DATA = {
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": os.getenv("CENTRAL_TOKEN")
}

session = requests.Session()
session.post(BASE + "/", data=LOGIN_DATA)

paths = [
    "/unban",
    "/ban",
    "/unban/24f3a2ea-4f23-45a4-9056-fe5ddf3869b9",
    "/apikeys",
    "/apikey",
    "/settings",
    "/admin",
    "/security",
    "/status",
]

for path in paths:
    r = session.get(BASE + path)
    print(f"{r.status_code} {path} ({len(r.text)} chars)")
    if r.status_code == 200 and "ban" in r.text.lower():
        print("  *** CONTAINS 'ban' ***")
