import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "resources" / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client

CENTRAL_TOKEN = os.getenv("CENTRAL_TOKEN")
API_URL = "https://hub.ag3nts.org/verify"

NOTES_DIR = Path(__file__).parent / "resources"


def call_filesystem_api(answer):
    payload = {
        "apikey": CENTRAL_TOKEN,
        "task": "filesystem",
        "answer": answer,
    }
    r = requests.post(API_URL, json=payload)
    return r.json()


def parse_notes_with_llm():
    client = get_llm_client()

    ogloszenia = (NOTES_DIR / "ogłoszenia.txt").read_text(encoding="utf-8")
    rozmowy = (NOTES_DIR / "rozmowy.txt").read_text(encoding="utf-8")
    transakcje = (NOTES_DIR / "transakcje.txt").read_text(encoding="utf-8")

    prompt = f"""Analyze these notes from Natan and extract structured trade data. Return ONLY valid JSON.

=== OGLOSZENIA (city needs/demands) ===
{ogloszenia}

=== ROZMOWY (conversations - who manages which city) ===
{rozmowy}

=== TRANSAKCJE (which city sells which good) ===
{transakcje}

Extract and return JSON with this exact structure:
{{
  "cities": {{
    "CityName": {{
      "good_name_no_polish_chars": quantity_number,
      ...
    }}
  }},
  "people": {{
    "First_Last": "CityName"
  }},
  "goods_for_sale": {{
    "good_name_no_polish_chars": ["CityName1", "CityName2"]
  }}
}}

Rules:
- City names: exact Polish names as values (e.g. "Darzlubie", "Opalino")
- Good names in cities dict and goods_for_sale: LOWERCASE, no Polish characters (rz->rz, l with stroke->l, o with accent->o, etc.), nominative singular (e.g. ryz not ryzu, mlotek not mlotki, lopata not lopaty, ziemniak not ziemniaki, wolowina not wolowiny, maka not maki)
- People keys: LOWERCASE, "first_last" format with underscore, no Polish characters (only a-z, 0-9, _). Each city must have EXACTLY ONE responsible person.
  - If you see "Konkel" and "Lena" separately for the same city, combine into "lena_konkel"
  - If you see "Kisiel" and "Rafal" for Brudzewo: "Rafal" is likely "Rafal Kisiel" (same person), combine as "rafal_kisiel"
  - Natan Rams manages Domatowo
- Person values: exact city name (e.g. "Domatowo")
- quantities: numbers only (no units)
- goods_for_sale values: list of cities that SELL that good (from transakcje.txt)

Return ONLY the JSON object, no explanation."""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    return json.loads(raw)


def build_batch(data):
    cities = data["cities"]
    people = data["people"]
    goods_for_sale = data["goods_for_sale"]

    ops = [{"action": "reset"}]

    # Create top-level directories
    for d in ["miasta", "osoby", "towary"]:
        ops.append({"action": "createDirectory", "path": f"/{d}"})

    # Create city files (referenced by people and goods, so first)
    for city, needs in cities.items():
        city_key = city.lower()
        content = json.dumps(needs, ensure_ascii=True)
        ops.append({
            "action": "createFile",
            "path": f"/miasta/{city_key}",
            "content": content,
        })

    # Create person files (link to city)
    for person_key, city in people.items():
        city_key = city.lower()
        file_name = person_key.lower()
        display = person_key.replace("_", " ").title()
        content = f"{display}\n[{city}](/miasta/{city_key})"
        ops.append({
            "action": "createFile",
            "path": f"/osoby/{file_name}",
            "content": content,
        })

    # Create goods files (link to selling city/cities)
    for good, selling_cities in goods_for_sale.items():
        links = "\n".join(f"[{c}](/miasta/{c.lower()})" for c in selling_cities)
        ops.append({
            "action": "createFile",
            "path": f"/towary/{good}",
            "content": links,
        })

    return ops


def main():
    print("Parsing notes with LLM...")
    data = parse_notes_with_llm()
    print("Extracted data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\nBuilding filesystem operations...")
    ops = build_batch(data)
    print(f"Total operations: {len(ops)}")

    print("\nExecuting batch operations...")
    result = call_filesystem_api(ops)
    print("Batch result:", result)

    if result.get("code") != 0:
        print("Error in batch, listing current filesystem...")
        ls_result = call_filesystem_api({"action": "listFiles", "path": "/"})
        print("Root:", ls_result)
        return

    print("\nSubmitting for verification...")
    done_result = call_filesystem_api({"action": "done"})
    print("Done result:", done_result)


if __name__ == "__main__":
    main()