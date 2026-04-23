import os
import requests
import json
import uuid
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
API_KEY = os.getenv("CENTRAL_TOKEN")
HUB = "https://hub.ag3nts.org/verify"
SKOLWIN_ID = "380792b2c86d9c5be670b3bde48e187b"


def call_hub(answer):
    payload = {"apikey": API_KEY, "task": "okoeditor", "answer": answer}
    r = requests.post(HUB, json=payload)
    result = r.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


# 1. Change Skolwin incident classification from vehicles/people to animals
print("=== 1. Update Skolwin incident: vehicles/people → animals ===")
call_hub({
    "action": "update",
    "page": "incydenty",
    "id": SKOLWIN_ID,
    "title": "ANIM03 Obserwacja aktywności zwierząt nieopodal miasta Skolwin",
    "content": (
        "Czujniki zarejestrowały ruch w okolicach Skolwina. "
        "Po dokładnej analizie danych ustalono, że zaobserwowane obiekty to zwierzęta – "
        "prawdopodobnie bobry przemieszczające się wzdłuż koryta rzeki. "
        "Charakterystyczny, nieregularny wzorzec ruchu jest typowy dla aktywności bobra w pobliżu wody. "
        "Nie potwierdzono obecności ludzi ani pojazdów. "
        "Raport sklasyfikowany jako obserwacja aktywności zwierząt, brak konieczności działań operacyjnych."
    )
})

# 2. Mark Skolwin task as done, add animal content
print("\n=== 2. Mark Skolwin task done + animal content ===")
call_hub({
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

# 3. Add Komarowo incident (new ID)
komarowo_id = uuid.uuid4().hex
print(f"\n=== 3. Add Komarowo incident (id={komarowo_id}) ===")
result = call_hub({
    "action": "update",
    "page": "incydenty",
    "id": komarowo_id,
    "title": "MOVE08 Wykryto ruch ludzi w okolicach miasta Komarowo",
    "content": (
        "Sensory w sektorze zachodnim zarejestrowały podejrzany ruch w pobliżu niezamieszkałego miasta Komarowo. "
        "Zidentyfikowano co najmniej kilka sylwetek ludzkich przemieszczających się w rejonie opuszczonych budynków. "
        "Ruch odbiega od standardowego wzorca dla tej lokalizacji. "
        "Rekomenduje się weryfikację terenu przez patrole operacyjne."
    )
})

# 4. Execute done action
print("\n=== 4. Done ===")
call_hub({"action": "done"})
