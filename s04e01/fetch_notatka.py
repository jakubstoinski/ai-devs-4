import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json
import re

BASE = "https://oko.ag3nts.org"
HUB = "https://hub.ag3nts.org/verify"
API_KEY = os.getenv("CENTRAL_TOKEN")
SKOLWIN_ID = "380792b2c86d9c5be670b3bde48e187b"

# Check API ban status first
r = requests.post(HUB, json={"apikey": API_KEY, "task": "okoeditor", "answer": {"action": "help"}})
if r.json().get("code") == -775:
    print("BANNED - stop")
    exit(1)
print("API OK")

session = requests.Session()
session.post(BASE + "/", data={
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": API_KEY
})

# Fetch ONLY the notatka detail page
r = session.get(f"{BASE}/notatki/{SKOLWIN_ID}")
with open("/Users/jbso/New Repo/ai-devs-4/s04e01/resources/notatka_skolwin.html", "w") as f:
    f.write(r.text)

# Extract content
html = r.text
html_no_style = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
html_no_script = re.sub(r'<script.*?</script>', '', html_no_style, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', ' ', html_no_script)
text = re.sub(r'\s+', ' ', text).strip()

# Find the relevant section
idx = text.find("Kody")
if idx > -1:
    print("Coding section found:")
    print(text[max(0,idx-100):idx+1000])
else:
    idx = text.find("RECO")
    if idx > -1:
        print("RECO section:")
        print(text[max(0,idx-200):idx+1000])
    else:
        print("Full text (last 2000 chars):")
        print(text[-2000:])

# Check ban status after
r = requests.post(HUB, json={"apikey": API_KEY, "task": "okoeditor", "answer": {"action": "help"}})
print(f"\nAPI status after: {r.json().get('code')} {r.json().get('message','')[:50]}")
