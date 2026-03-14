import csv
import sys
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(dotenv_path="../resources/.env")

sys.path.append("..")
from common.llm_client import get_llm_client
from common.central_client import send_to_central

TARGET_CITY = "Grudziądz"
CURRENT_YEAR = 2026
MIN_AGE = 20
MAX_AGE = 40
BATCH_SIZE = 10

ALLOWED_TAGS = [
    "IT",
    "transport",
    "edukacja",
    "medycyna",
    "praca z ludźmi",
    "praca z pojazdami",
    "praca fizyczna",
]


# --- Structured output models ---

class Person(BaseModel):
    name: str
    surname: str
    gender: str
    born: int
    city: str
    tags: list[str]


class PeopleList(BaseModel):
    people: list[Person]


# --- Step 1: Filter by city and age ---

birth_year_min = CURRENT_YEAR - MAX_AGE  # 1986
birth_year_max = CURRENT_YEAR - MIN_AGE  # 2006

candidates = []

with open("resources/people.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        birth_place = row["birthPlace"].strip()
        birth_year = int(row["birthDate"].strip().split("-")[0])

        if birth_place == TARGET_CITY and birth_year_min <= birth_year <= birth_year_max:
            candidates.append({
                "name": row["name"].strip(),
                "surname": row["surname"].strip(),
                "gender": row["gender"].strip(),
                "born": birth_year,
                "city": birth_place,
                "job": row["job"].strip(),
            })

print(f"Pre-filtered {len(candidates)} candidates. Sending to LLM in batches of {BATCH_SIZE}...\n")

# --- Step 2: Tag via LLM in batches ---

client = get_llm_client()
tagged_people = []

for i in range(0, len(candidates), BATCH_SIZE):
    batch = candidates[i:i + BATCH_SIZE]
    batch_lines = "\n".join(
        f"{p['name']} {p['surname']} ({p['gender']}, born {p['born']}, city: {p['city']}): {p['job']}"
        for p in batch
    )

    prompt = f"""You are a job classifier. For each person below, assign relevant tags from this list only:
{', '.join(ALLOWED_TAGS)}

A person can have multiple tags. Only use tags from the list above.
IMPORTANT: Only include people whose job is related to "transport" (transportation sector).
Skip people who do not work in transportation — do not include them in the response at all.
Return one entry per matching person preserving name, surname, gender, born (as integer), city, and tags (as array of strings).

People:
{batch_lines}"""

    response = client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format=PeopleList,
    )

    batch_result = response.choices[0].message.parsed
    tagged_people.extend(batch_result.people)
    print(f"Batch {i // BATCH_SIZE + 1}: tagged {len(batch_result.people)} people")

# --- Step 3: Build answer payload ---

answer = [p.model_dump() for p in tagged_people]

print(f"\nTagging complete. Sending {len(answer)} records to central...\n")

# --- Step 4: Send to central ---

result = send_to_central("people", answer)
print("Central response:", result)

if result.get("code") == 0:
    save_dir = os.path.join(os.path.dirname(__file__), "..", "s01e02", "resources")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "people_sent.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(answer, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(answer)} records to {save_path}")
