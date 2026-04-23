import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json
import re
import os

BASE = "https://oko.ag3nts.org"
API_KEY = os.getenv("CENTRAL_TOKEN")
RESOURCES = "/Users/jbso/New Repo/ai-devs-4/s04e01/resources"

session = requests.Session()
session.post(BASE + "/", data={
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": API_KEY
})

IDS = [
    "380792b2c86d9c5be670b3bde48e187b",
    "ff3313a39099222e325f03b378680e3c",
    "bcdfc393f811cc05d3a189c679f50659",
    "8875c5a166cb04ea6fedde59b0ad6501",
    "8b04cb375286948cbe22b446b81921ba",
    "351c0d9c90d66b4c040fff1259dd191d",
]

for page in ["incydenty", "zadania"]:
    print(f"\n{'='*60}")
    print(f"PAGE: {page}")
    print('='*60)
    for eid in IDS:
        r = session.get(f"{BASE}/{page}/{eid}")
        fname = f"{RESOURCES}/{page}_{eid[:8]}.html"
        with open(fname, "w") as f:
            f.write(r.text)

        # Extract title from <h2 class="hero-title">
        title_m = re.search(r'class="hero-title"[^>]*>\s*([^<]+)', r.text)
        # Extract pill content
        pills = re.findall(r'class="pill"[^>]*>([^<]+)', r.text)
        # Extract detail-content (may span lines)
        content_m = re.search(r'class="detail-content"[^>]*>(.*?)</p>', r.text, re.DOTALL)

        title = title_m.group(1).strip() if title_m else "N/A"
        content_preview = ""
        if content_m:
            c = re.sub(r'\s+', ' ', content_m.group(1)).strip()
            content_preview = c[:150]

        print(f"\nID: {eid[:16]}...")
        print(f"  Title: {title}")
        print(f"  Pills: {pills}")
        print(f"  Content: {content_preview}")
