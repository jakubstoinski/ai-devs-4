import csv
import sys
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from rapidfuzz import process, fuzz

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client

app = FastAPI()

RESOURCES = Path(__file__).parent / "resources"

cities: dict[str, str] = {}       # code -> name
items: dict[str, str] = {}        # code -> name
item_list: list[tuple[str, str]] = []  # [(code, name)]
connections: dict[str, list[str]] = {}  # itemCode -> [cityCode]


def load_data():
    with open(RESOURCES / "cities.csv") as f:
        for row in csv.DictReader(f):
            cities[row["code"]] = row["name"]
    with open(RESOURCES / "items.csv") as f:
        for row in csv.DictReader(f):
            items[row["code"]] = row["name"]
            item_list.append((row["code"], row["name"]))
    with open(RESOURCES / "connections.csv") as f:
        for row in csv.DictReader(f):
            connections.setdefault(row["itemCode"], []).append(row["cityCode"])


load_data()

client = get_llm_client()
item_names_only = [name for _, name in item_list]


def normalize_query(query: str) -> str:
    """Use LLM to convert natural language query to concise product specification."""
    resp = client.chat.completions.create(
        model="claude-haiku-4-5",
        messages=[{
            "role": "user",
            "content": (
                "Convert this natural language query to a concise product specification "
                "in Polish (max 6 words, keep numbers and units). "
                "Return ONLY the specification, nothing else.\n\n"
                f"Query: {query}"
            )
        }],
        max_tokens=30,
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


def find_item_code(query: str) -> str | None:
    """Find best matching item code using normalized query + rapidfuzz."""
    normalized = normalize_query(query)
    match = process.extractOne(
        normalized,
        item_names_only,
        scorer=fuzz.WRatio,
        score_cutoff=50,
    )
    if not match:
        return None
    matched_name = match[0]
    for code, name in item_list:
        if name == matched_name:
            return code
    return None


class QueryRequest(BaseModel):
    params: str


@app.post("/search")
def search_item(req: QueryRequest):
    """Find cities selling a specific item. Params: natural language item description in Polish or English."""
    item_code = find_item_code(req.params)
    if not item_code:
        return {"output": "Item not found in catalog"}

    city_codes = connections.get(item_code, [])
    if not city_codes:
        return {"output": f"Item '{items[item_code]}' not available in any city"}

    city_names = sorted(cities[c] for c in city_codes if c in cities)
    result = ", ".join(city_names)

    # Trim to fit 500 byte limit
    while len(result.encode("utf-8")) > 490:
        city_names = city_names[:-1]
        result = ", ".join(city_names)

    return {"output": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
