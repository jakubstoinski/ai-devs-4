import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
import requests
import json

API_KEY = os.getenv("CENTRAL_TOKEN")
HUB = "https://hub.ag3nts.org/verify"
SKOLWIN_ID = "380792b2c86d9c5be670b3bde48e187b"


def call_hub(answer):
    r = requests.post(HUB, json={"apikey": API_KEY, "task": "okoeditor", "answer": answer})
    result = r.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


# Try RECO03 prefix — RECO may be the animal/recon classification
print("=== Try RECO03 prefix ===")
result = call_hub({
    "action": "update",
    "page": "incydenty",
    "id": SKOLWIN_ID,
    "title": "RECO03 Obserwacja aktywności zwierząt nieopodal miasta Skolwin",
    "content": (
        "Czujniki zarejestrowały ruch w okolicach Skolwina. "
        "Po analizie ustalono, że zaobserwowane obiekty to zwierzęta – bobry przemieszczające się wzdłuż rzeki. "
        "Nie stwierdzono obecności ludzi ani pojazdów. "
        "Raport sklasyfikowany jako obserwacja zwierząt."
    )
})

if result.get("code") == 110:
    print("\n=== Done check ===")
    call_hub({"action": "done"})
