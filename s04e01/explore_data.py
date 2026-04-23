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

session = requests.Session()
session.post(BASE + "/", data={
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": API_KEY
})

def extract_text(html):
    # Remove style/script blocks
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    # Remove tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Normalize whitespace
    return re.sub(r'\s+', ' ', html).strip()

# Get all incidents
r = session.get(BASE + "/")
# Find all incident links
incidents = re.findall(r'href="/incydenty/([a-f0-9]+)"', r.text)
incidents = list(dict.fromkeys(incidents))  # deduplicate
print(f"Found {len(incidents)} incidents: {incidents}")

for inc_id in incidents:
    r2 = session.get(f"{BASE}/incydenty/{inc_id}")
    text = extract_text(r2.text)
    # Find relevant parts
    title_m = re.search(r'hero-title[^>]*>([^<]+)', r2.text)
    pill_m = re.findall(r'class="pill"[^>]*>([^<]+)', r2.text)
    content_m = re.search(r'detail-content[^>]*>([^<]+)', r2.text)
    print(f"\n--- Incident {inc_id} ---")
    if title_m:
        print(f"Title: {title_m.group(1).strip()}")
    if pill_m:
        print(f"Pills: {pill_m}")
    if content_m:
        print(f"Content (start): {content_m.group(1).strip()[:200]}")
