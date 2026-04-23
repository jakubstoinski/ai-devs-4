import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json

API_KEY = os.getenv("CENTRAL_TOKEN")
HUB = "https://hub.ag3nts.org/verify"
BASE = "https://oko.ag3nts.org"

session = requests.Session()
session.post(BASE + "/", data={
    "action": "login",
    "login": "Zofia",
    "password": "Zofia2026!",
    "access_key": API_KEY
})

# Try 'add' action on hub API
print("=== Try 'add' action ===")
r = requests.post(HUB, json={
    "apikey": API_KEY,
    "task": "okoeditor",
    "answer": {
        "action": "add",
        "page": "incydenty",
        "title": "MOVE08 Wykryto ruch ludzi w okolicach miasta Komarowo",
        "content": "Wykryto ruch ludzi."
    }
})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# Check if there's a "new entry" form on the web panel
print("\n=== Check /new /incydenty/new /add ===")
for path in ["/new", "/incydenty/new", "/add", "/incydenty/add", "/nowy-incydent"]:
    resp = session.get(BASE + path)
    print(f"{resp.status_code} {path} ({len(resp.text)} chars)")
    if resp.status_code == 200 and len(resp.text) > 500:
        import re
        title = re.search(r'<title>(.*?)</title>', resp.text)
        if title:
            print(f"  Title: {title.group(1)}")

# Try the hub API with a "notatki" page ID that might not exist in incydenty
# Actually all 6 IDs exist in both. Let me check if there are more on notatki
print("\n=== Check notatki page IDs ===")
r = session.get(BASE + "/notatki")
import re
nota_ids = re.findall(r'href="/notatki/([a-f0-9]+)"', r.text)
nota_ids = list(dict.fromkeys(nota_ids))
print(f"Notatki IDs: {nota_ids}")

r = session.get(BASE + "/")
inc_ids = re.findall(r'href="/incydenty/([a-f0-9]+)"', r.text)
inc_ids = list(dict.fromkeys(inc_ids))
print(f"Incydenty IDs: {inc_ids}")

only_in_notatki = [x for x in nota_ids if x not in inc_ids]
print(f"Only in notatki (not in incydenty): {only_in_notatki}")
