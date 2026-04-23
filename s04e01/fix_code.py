import os
import requests
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")
API_KEY = os.getenv("CENTRAL_TOKEN")
HUB = "https://hub.ag3nts.org/verify"
SKOLWIN_ID = "380792b2c86d9c5be670b3bde48e187b"


def call_hub(answer):
    r = requests.post(HUB, json={"apikey": API_KEY, "task": "okoeditor", "answer": answer})
    result = r.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


# Fix Skolwin incident: use MOVE04 (animals) instead of RECO03
print("=== Fix Skolwin incident: MOVE04 (animals) ===")
call_hub({
    "action": "update",
    "page": "incydenty",
    "id": SKOLWIN_ID,
    "title": "MOVE04 Obserwacja aktywności zwierząt nieopodal miasta Skolwin",
    "content": (
        "Czujniki zarejestrowały ruch w okolicach Skolwina. "
        "Po analizie ustalono, że zaobserwowane obiekty to zwierzęta – bobry przemieszczające się wzdłuż rzeki. "
        "Nie stwierdzono obecności ludzi ani pojazdów. "
        "Raport sklasyfikowany jako obserwacja zwierząt (MOVE04)."
    )
})

# Also fix Komarowo incident: MOVE01 (person) is correct for human movement
print("\n=== Fix Komarowo incident: MOVE01 (person) ===")
call_hub({
    "action": "update",
    "page": "incydenty",
    "id": "351c0d9c90d66b4c040fff1259dd191d",
    "title": "MOVE01 Wykryto ruch ludzi w okolicach miasta Komarowo",
    "content": (
        "Sensory w sektorze zachodnim zarejestrowały podejrzany ruch w pobliżu "
        "niezamieszkałego miasta Komarowo. "
        "Zidentyfikowano sylwetki ludzkie przemieszczające się w rejonie opuszczonych budynków. "
        "Ruch odbiega od standardowego wzorca dla tej lokalizacji. "
        "Rekomenduje się weryfikację terenu przez patrole operacyjne."
    )
})

print("\n=== Done ===")
call_hub({"action": "done"})
