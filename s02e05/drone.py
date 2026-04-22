import sys
import os
import base64
import json
import re
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.llm_client import get_llm_client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'resources', '.env'))
CENTRAL_TOKEN = os.getenv('CENTRAL_TOKEN')
VERIFY_URL = "https://hub.ag3nts.org/verify"


def analyze_dam_sector():
    client = get_llm_client()
    image_path = os.path.join(os.path.dirname(__file__), 'resources', 'drone.png')
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"}
                },
                {
                    "type": "text",
                    "text": (
                        "This aerial map has a red grid overlay dividing it into sectors. "
                        "Count vertical and horizontal red lines carefully (not image edges). "
                        "Cols = vertical_dividers+1, rows = horizontal_dividers+1.\n"
                        "The dam has artificially boosted bright turquoise/teal/cyan water. "
                        "Find the brightest blue/teal sector. Column 1=left, row 1=top.\n"
                        "Return JSON only: "
                        "{\"cols\": N, \"rows\": N, \"dam_col\": N, \"dam_row\": N}"
                    )
                }
            ]
        }],
        max_tokens=200
    )

    content = response.choices[0].message.content
    print(f"Vision model response: {content}")

    match = re.search(r'\{[^}]+\}', content)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Could not parse JSON from: {content}")


def send_instructions(instructions):
    payload = {
        "apikey": CENTRAL_TOKEN,
        "task": "drone",
        "answer": {"instructions": instructions}
    }
    print(f"Sending: {instructions}")
    response = requests.post(VERIFY_URL, json=payload)
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data


def find_dam_sector_iteratively(initial_col, initial_row):
    """Use API feedback to narrow down the exact dam sector."""
    # Try the vision model's suggestion first, then search nearby
    candidates = [(initial_col, initial_row)]
    # Add broader search area around the initial guess
    for dc in range(-2, 4):
        for dr in range(-2, 4):
            c, r = initial_col + dc, initial_row + dr
            if c >= 1 and r >= 1 and (c, r) != (initial_col, initial_row):
                candidates.append((c, r))

    for col, row in candidates:
        result = send_instructions([
            f"setDestinationObject(PWR6132PL)",
            f"set({col},{row})",
            "set(engineON)",
            "set(100%)",
            "set(50m)",
            "set(destroy)",
            "set(return)",
            "flyToLocation"
        ])
        msg = str(result)
        if '{FLG:' in msg:
            print(f"\nSUCCESS! Dam sector: ({col},{row})")
            return result, col, row
        if 'power plant' in msg.lower() or 'pretending' in msg.lower():
            print(f"  ({col},{row}) = power plant area, skipping column {col}")
        elif 'nearby' in msg.lower():
            print(f"  ({col},{row}) = near dam but not exact")
        elif 'return' in msg.lower() or 'lose it' in msg.lower():
            # Already handled return, but got this? Try without
            pass
        elif 'power' in msg.lower() and 'engine' in msg.lower():
            print(f"  ({col},{row}) = engine power issue")

    return None, None, None


def main():
    print("=== Step 1: Analyze map with vision model ===")
    map_info = analyze_dam_sector()
    dam_col = map_info['dam_col']
    dam_row = map_info['dam_row']
    print(f"Vision model suggests dam at: ({dam_col},{dam_row})")

    print("\n=== Step 2: Find exact dam sector via API feedback ===")
    result, col, row = find_dam_sector_iteratively(dam_col, dam_row)

    if result and '{FLG:' in str(result):
        flag = str(result.get('message', ''))
        print(f"\nFlag obtained: {flag}")
    else:
        print("\nCould not find flag. Last result:", result)


if __name__ == '__main__':
    main()
