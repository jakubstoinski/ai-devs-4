import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

AGENT_URL = "https://zewhq-31-183-237-26.a.free.pinggy.link"

api_key = os.getenv("CENTRAL_TOKEN")
if not api_key:
    raise ValueError("CENTRAL_TOKEN not set in environment")

payload = {
    "apikey": api_key,
    "task": "proxy",
    "answer": {
    "url": AGENT_URL,
    "sessionID": "Dephamen123"
  }
}

response = requests.post("https://hub.ag3nts.org/verify", json=payload)
print(f"Status: {response.status_code}")
print(response.json())
