import os
import sys
import csv
import io
import requests
from dotenv import load_dotenv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

CENTRAL_API_URL = "https://hub.ag3nts.org/verify"
CENTRAL_TOKEN = os.getenv("CENTRAL_TOKEN")


def get_csv_data() -> list[dict]:
    url = f"https://hub.ag3nts.org/data/{CENTRAL_TOKEN}/categorize.csv"
    resp = requests.get(url)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


def reset_counter() -> dict:
    payload = {"apikey": CENTRAL_TOKEN, "task": "categorize", "answer": {"prompt": "reset"}}
    resp = requests.post(CENTRAL_API_URL, json=payload)
    return resp.json()


def submit_prompt(prompt_template: str, item: dict) -> dict:
    filled = (
        prompt_template
        .replace("{code}", item["code"])
        .replace("{id}", item["code"])
        .replace("{description}", item["description"])
    )
    payload = {
        "apikey": CENTRAL_TOKEN,
        "task": "categorize",
        "answer": {"prompt": filled},
    }
    resp = requests.post(CENTRAL_API_URL, json=payload)
    return resp.json()


def run_cycle(prompt_template: str) -> tuple[bool, list[dict]]:
    items = get_csv_data()
    results = []
    for item in items:
        result = submit_prompt(prompt_template, item)
        print(f"  [{item['code']}] {item['description'][:50]} -> {result}")
        results.append({"item": item, "result": result})
        if "{FLG:" in str(result) or "FLG:" in str(result):
            return True, results
    return False, results


def refine_prompt(client, current_prompt: str, results: list[dict]) -> str:
    summary = "\n".join(
        f"- code={r['item']['code']}, desc={r['item']['description']!r}, hub={r['result']}"
        for r in results
    )
    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4-6",
        messages=[
            {
                "role": "user",
                "content": f"""You are a prompt engineer optimizing a classification prompt.

Rules:
1. Classify each item as DNG (dangerous) or NEU (neutral).
2. Items related to reactor/nuclear fuel cassettes MUST always be NEU.
3. The TOTAL filled prompt (static part + item data) must stay under 100 tokens (GPT tokenizer).
4. Put static instructions FIRST (for prompt caching), then {{id}} and {{description}} at the end.
5. Write the prompt in English only.

Current prompt template:
{current_prompt}

Results from hub (check hub response for errors):
{summary}

Return ONLY the improved prompt template (with {{id}} and {{description}} placeholders), nothing else.""",
            }
        ],
    )
    return response.choices[0].message.content.strip()


def main():
    client = get_llm_client()

    # Compact starting prompt: static instructions first, variables last
    current_prompt = (
        "Reply DNG (dangerous) or NEU (neutral). "
        "Reactor/nuclear fuel items: always NEU. "
        "Item {code}: {description}"
    )

    for attempt in range(1, 16):
        print(f"\n=== Attempt {attempt} ===")
        print(f"Prompt: {current_prompt!r}")

        reset_result = reset_counter()
        print(f"Reset: {reset_result}")

        success, results = run_cycle(current_prompt)

        if success:
            print("\nSUCCESS! Flag received.")
            for r in results:
                if "FLG:" in str(r["result"]):
                    print(r["result"])
            break

        current_prompt = refine_prompt(client, current_prompt, results)
        print(f"Refined prompt: {current_prompt!r}")
    else:
        print("Max attempts reached without success.")


if __name__ == "__main__":
    main()