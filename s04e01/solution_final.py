import os
import requests
import json
import time
import uuid
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
API_KEY = os.getenv("CENTRAL_TOKEN")
HUB = "https://hub.ag3nts.org/verify"
SKOLWIN_ID = "380792b2c86d9c5be670b3bde48e187b"

# IDs found from the web panel (all existing incidents)
INCIDENT_IDS = [
    "380792b2c86d9c5be670b3bde48e187b",  # MOVE03 Skolwin
    "ff3313a39099222e325f03b378680e3c",   # PROB02 Domatowo
    "bcdfc393f811cc05d3a189c679f50659",   # PROB01 VHF
    "8875c5a166cb04ea6fedde59b0ad6501",   # PROB02 IRC
    "8b04cb375286948cbe22b446b81921ba",   # PROB02 telemetry
    "351c0d9c90d66b4c040fff1259dd191d",   # PROB01 PMR
]


def call_hub(answer, retries=3):
    payload = {"apikey": API_KEY, "task": "okoeditor", "answer": answer}
    for attempt in range(retries):
        r = requests.post(HUB, json=payload)
        result = r.json()
        if result.get("code") == -775:
            print(f"  [banned, waiting 30s...]")
            time.sleep(30)
            continue
        return result
    return result


def wait_for_unban(max_wait=300):
    print("Checking ban status...")
    for i in range(max_wait // 15):
        r = requests.post(HUB, json={
            "apikey": API_KEY, "task": "okoeditor", "answer": {"action": "help"}
        })
        result = r.json()
        if result.get("code") != -775:
            print("Unbanned!")
            return True
        print(f"  Still banned, waiting 15s... ({(i+1)*15}s elapsed)")
        time.sleep(15)
    return False


# Wait for unban
if not wait_for_unban():
    print("Could not unban, exiting")
    exit(1)

# 1. Update Skolwin incident: keep MOVE03 prefix, change to animals
print("\n=== 1. Update Skolwin incident: MOVE03 + animal classification ===")
result = call_hub({
    "action": "update",
    "page": "incydenty",
    "id": SKOLWIN_ID,
    "title": "MOVE03 Obserwacja aktywności zwierząt nieopodal miasta Skolwin",
    "content": (
        "Czujniki zarejestrowały ruch w okolicach Skolwina. "
        "Po analizie ustalono, że zaobserwowane obiekty to zwierzęta – bobry przemieszczające się wzdłuż rzeki. "
        "Charakterystyczny nieregularny wzorzec ruchu jest typowy dla aktywności zwierząt w pobliżu wody. "
        "Nie stwierdzono obecności ludzi ani pojazdów. "
        "Raport sklasyfikowany jako obserwacja zwierząt."
    )
})
print(json.dumps(result, indent=2, ensure_ascii=False))

# 2. Skolwin task is already done from previous run — verify
print("\n=== 2. Verify Skolwin task status ===")
result = call_hub({
    "action": "update",
    "page": "zadania",
    "id": SKOLWIN_ID,
    "done": "YES",
    "content": (
        "Zbadano nagrania z okolic Skolwina. "
        "Widziano tam zwierzęta – bobry przemieszczające się wzdłuż rzeki. "
        "Brak obecności ludzi ani pojazdów. Sprawa zamknięta."
    )
})
print(json.dumps(result, indent=2, ensure_ascii=False))

# 3. Try to add Komarowo incident - first try 'add' action
print("\n=== 3a. Try 'add' action for Komarowo ===")
result = call_hub({
    "action": "add",
    "page": "incydenty",
    "title": "MOVE08 Wykryto ruch ludzi w okolicach miasta Komarowo",
    "content": (
        "Sensory w sektorze zachodnim zarejestrowały podejrzany ruch w pobliżu "
        "niezamieszkałego miasta Komarowo. "
        "Zidentyfikowano sylwetki ludzkie przemieszczające się w rejonie opuszczonych budynków. "
        "Ruch odbiega od standardowego wzorca dla tej lokalizacji. "
        "Rekomenduje się weryfikację terenu przez patrole operacyjne."
    )
})
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get("code") not in [100, 110, 120]:
    # 'add' failed — try using the last incident ID (PMR) to update to Komarowo
    print("\n=== 3b. Update existing incident to Komarowo ===")
    last_id = "351c0d9c90d66b4c040fff1259dd191d"
    result = call_hub({
        "action": "update",
        "page": "incydenty",
        "id": last_id,
        "title": "MOVE08 Wykryto ruch ludzi w okolicach miasta Komarowo",
        "content": (
            "Sensory w sektorze zachodnim zarejestrowały podejrzany ruch w pobliżu "
            "niezamieszkałego miasta Komarowo. "
            "Zidentyfikowano sylwetki ludzkie przemieszczające się w rejonie opuszczonych budynków. "
            "Ruch odbiega od standardowego wzorca dla tej lokalizacji. "
            "Rekomenduje się weryfikację terenu przez patrole operacyjne."
        )
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))

# 4. Done
print("\n=== 4. Done ===")
result = call_hub({"action": "done"})
print(json.dumps(result, indent=2, ensure_ascii=False))
