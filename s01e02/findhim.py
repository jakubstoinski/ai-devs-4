import os
import sys
import json

from dotenv import load_dotenv

load_dotenv(dotenv_path="../resources/.env")

sys.path.append("..")

from common.llm_client import get_llm_client
from common.central_client import send_to_central
from get_location import get_location, GET_LOCATION_TOOL
from get_access_level import get_access_level, GET_ACCESS_LEVEL_TOOL
from haversine import haversine_km, find_closest_power_plant, FIND_CLOSEST_POWER_PLANT_TOOL

# --- Load data ---

with open("resources/people_sent.json", encoding="utf-8") as f:
    suspects = json.load(f)

with open("resources/findhim_locations.json", encoding="utf-8") as f:
    findhim_data = json.load(f)

power_plants = findhim_data["power_plants"]

# Hardcoded coordinates to ensure deterministic distance calculations
CITY_COORDS = {
    "Zabrze":                 {"lat": 50.3249, "lon": 18.7857},
    "Piotrków Trybunalski":   {"lat": 51.4058, "lon": 19.7034},
    "Grudziądz":              {"lat": 53.4837, "lon": 18.7536},
    "Tczew":                  {"lat": 53.7772, "lon": 18.7773},
    "Radom":                  {"lat": 51.4027, "lon": 21.1471},
    "Chelmno":                {"lat": 53.3489, "lon": 18.4249},
    "Żarnowiec":              {"lat": 54.5833, "lon": 18.1667},
}

# Build enriched list of active power plants with fixed coordinates
active_power_plants = [
    {"code": data["code"], **CITY_COORDS[city]}
    for city, data in power_plants.items()
    if data["is_active"] and city in CITY_COORDS
]

# --- Build prompt ---

suspects_text = json.dumps(suspects, ensure_ascii=False, indent=2)
active_power_plants_text = json.dumps(active_power_plants, ensure_ascii=False, indent=2)

SYSTEM_PROMPT = f"""You are an investigator. Your job is to find the single suspect who was ever closest to any power plant.

You have a list of suspects and a list of power plants (with their city names and codes).

Follow these steps exactly:

PHASE 1 — Call get_location for every suspect to collect all their spotted locations.

PHASE 2 — For each suspect, call find_closest_power_plant once with:
- "name" and "surname" of the suspect
- "person_locations": all their spotted locations as a list of {{"lat", "lon"}} objects
- "power_plants": use EXACTLY the list provided below — do not modify or guess coordinates.
The function returns the closest power plant code and distance for that suspect.
Track the global minimum across all suspects to find the single closest (suspect, power plant) pair.

PHASE 3 — Call get_access_level for that single closest suspect.

PHASE 4 — Return ONLY a JSON object (no markdown, no extra text):
{{
  "name": "<suspect first name>",
  "surname": "<suspect last name>",
  "accessLevel": <integer access level>,
  "powerPlant": "<power plant code e.g. PWR1234PL>"
}}

Active power plants (use these exact coordinates):
{active_power_plants_text}

Suspects:
{suspects_text}
"""

# --- Agentic tool-calling loop ---

client = get_llm_client()
tools = [GET_LOCATION_TOOL, GET_ACCESS_LEVEL_TOOL, FIND_CLOSEST_POWER_PLANT_TOOL]

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "Find the single suspect who was ever closest to any power plant, get their access level, and return the result JSON."},
]

print("Starting LLM agent loop...\n")

while True:
    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    message = response.choices[0].message
    messages.append(message)

    if message.tool_calls:
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            print(f"Tool call: {fn_name}({fn_args})")

            if fn_name == "get_location":
                result = get_location(**fn_args)
            elif fn_name == "get_access_level":
                result = get_access_level(**fn_args)
            elif fn_name == "find_closest_power_plant":
                result = find_closest_power_plant(**fn_args)
            else:
                result = {"error": f"Unknown tool: {fn_name}"}

            print(f"  -> {result}\n")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    else:
        # LLM finished — parse the answer
        answer_text = message.content.strip()
        print("LLM final answer:", answer_text)
        answer = json.loads(answer_text)
        break

# --- Send to central ---

print("\nSending to central...")
result = send_to_central("findhim", answer)
print("Central response:", result)