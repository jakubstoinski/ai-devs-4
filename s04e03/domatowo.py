#!/usr/bin/env python3
"""S04E03 — Domatowo rescue mission.

Map analysis (11x11, cols A-K, rows 1-11):
- Block3 (3-story, tallest): F1, G1, F2, G2 (north); A10-C11, H10-I11 (south)
- Roads: B1-D1, D2,E2,I2, D3,I3, D4,I4, D5,I5, A6-J6, D7, D8, B9-J9

Strategy:
  3 transporters (each with 1 scout):
  T1 -> E2 -> scout covers F2,G2,G1,F1
  T2 -> B9 -> scout covers B10,A10,A11,B11,C11,C10
  T3 -> H9 -> scout covers H10,H11,I11,I10
  Total est. ~165 action pts out of 300
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "resources", ".env"))

API_KEY = os.getenv("CENTRAL_TOKEN")
HUB_URL = "https://hub.ag3nts.org/verify"
TASK = "domatowo"

person_found_at: str | None = None


def call_api(answer: dict) -> dict:
    payload = {"apikey": API_KEY, "task": TASK, "answer": answer}
    resp = requests.post(HUB_URL, json=payload, timeout=30)
    data = resp.json()
    print(f"  <- {json.dumps(data, ensure_ascii=False)[:400]}")
    return data


def reset():
    print("[reset]")
    return call_api({"action": "reset"})


def get_map() -> dict:
    print("[getMap]")
    return call_api({"action": "getMap"})


def search_symbol(symbol: str) -> dict:
    print(f"[searchSymbol {symbol}]")
    return call_api({"action": "searchSymbol", "symbol": symbol})


def get_logs() -> dict:
    print("[getLogs]")
    return call_api({"action": "getLogs"})


def get_objects() -> dict:
    print("[getObjects]")
    return call_api({"action": "getObjects"})


def create_transporter(passengers: int) -> dict:
    print(f"[create transporter passengers={passengers}]")
    return call_api({"action": "create", "type": "transporter", "passengers": passengers})


def move_unit(obj_id: str, where: str) -> dict:
    print(f"[move {obj_id[:8]}... -> {where}]")
    return call_api({"action": "move", "object": obj_id, "where": where})


def dismount(transporter_id: str, passengers: int) -> dict:
    print(f"[dismount {transporter_id[:8]}... passengers={passengers}]")
    return call_api({"action": "dismount", "object": transporter_id, "passengers": passengers})


def inspect(scout_id: str) -> dict:
    print(f"[inspect scout {scout_id[:8]}...]")
    return call_api({"action": "inspect", "object": scout_id})


def call_helicopter(destination: str) -> dict:
    print(f"[callHelicopter -> {destination}]")
    return call_api({"action": "callHelicopter", "destination": destination})


def check_for_person(result: dict, position: str) -> bool:
    global person_found_at
    result_str = json.dumps(result, ensure_ascii=False).lower()
    found_keywords = ["person", "found", "partisan", "człowiek", "partyzant",
                      "survivor", "ocalały", "human", "mieszkaniec", "ukryw"]
    if any(kw in result_str for kw in found_keywords):
        person_found_at = position
        print(f"*** PERSON FOUND at {position}! ***")
        return True
    # Some APIs return a code indicating success/finding
    if result.get("code") in [21, 22, 23, 50, 51] and "inspect" in result_str:
        person_found_at = position
        print(f"*** PERSON FOUND at {position} (code {result.get('code')})! ***")
        return True
    return False


def scout_inspect_at(scout_id: str, current_pos: str, target_pos: str) -> tuple[str, bool]:
    """Move scout to target (if different), then inspect. Returns new position and found status."""
    global person_found_at
    if person_found_at:
        return current_pos, True

    if current_pos != target_pos:
        move_unit(scout_id, target_pos)
        time.sleep(0.5)

    result = inspect(scout_id)
    time.sleep(0.5)
    found = check_for_person(result, target_pos)
    return target_pos, found


def main():
    global person_found_at

    print("=== Domatowo Rescue Mission ===")

    # Verify block3 positions using searchSymbol
    b3_result = search_symbol("B3")
    time.sleep(0.5)
    b3_fields = b3_result.get("fields", [])
    print(f"Block3 fields from API: {b3_fields}")

    if not b3_fields:
        # Fallback from visual map analysis
        b3_fields = ["F1", "G1", "F2", "G2",
                     "A10", "B10", "C10", "H10", "I10",
                     "A11", "B11", "C11", "H11", "I11"]
        print(f"Using fallback block3 positions: {b3_fields}")

    # Cluster the block3 fields
    north = sorted([f for f in b3_fields if int(f[1:]) <= 5])
    south_west = sorted([f for f in b3_fields if int(f[1:]) > 5 and f[0] <= "D"])
    south_east = sorted([f for f in b3_fields if int(f[1:]) > 5 and f[0] > "D"])

    print(f"North: {north}")
    print(f"South-West: {south_west}")
    print(f"South-East: {south_east}")

    # ── T1: covers north cluster (F1, G1, F2, G2) ──────────────────────────
    # Route: A6 -> D6 -> D2 -> E2 (then dismount scout)
    print("\n--- Creating T1 for north cluster ---")
    t1 = create_transporter(1)
    time.sleep(0.5)
    t1_id = t1.get("object", "")
    t1_scouts = [s["id"] for s in t1.get("crew", [])]
    print(f"T1 id={t1_id[:8]}, spawn={t1.get('spawn')}, scouts={[s[:8] for s in t1_scouts]}")

    # Move T1 to E2 (road adjacent to F2)
    move_unit(t1_id, "E2")
    time.sleep(0.5)

    # Dismount 1 scout
    dismount_result = dismount(t1_id, 1)
    time.sleep(0.5)
    print(f"Dismount result: {dismount_result}")

    # Scout is near E2 — get updated objects to find scout position
    objs = get_objects()
    time.sleep(0.5)
    # Find scout position
    s1_id = t1_scouts[0] if t1_scouts else None
    s1_pos = "E2"
    for obj in objs.get("objects", []):
        if obj.get("id") == s1_id:
            s1_pos = obj.get("position", "E2")
            break
    print(f"Scout 1 at: {s1_pos}")

    # Search north cluster: F2, G2, G1, F1
    north_search_order = ["F2", "G2", "G1", "F1"]
    for target in north_search_order:
        if person_found_at:
            break
        if target in north:
            s1_pos, found = scout_inspect_at(s1_id, s1_pos, target)

    # ── T2: covers south-west cluster ──────────────────────────────────────
    if not person_found_at and south_west:
        print("\n--- Creating T2 for south-west cluster ---")
        t2 = create_transporter(1)
        time.sleep(0.5)
        t2_id = t2.get("object", "")
        t2_scouts = [s["id"] for s in t2.get("crew", [])]
        print(f"T2 id={t2_id[:8]}, spawn={t2.get('spawn')}, scouts={[s[:8] for s in t2_scouts]}")

        # Move T2 to B9 (road adjacent to B10, C10, A10)
        move_unit(t2_id, "B9")
        time.sleep(0.5)

        dismount(t2_id, 1)
        time.sleep(0.5)

        objs2 = get_objects()
        time.sleep(0.5)
        s2_id = t2_scouts[0] if t2_scouts else None
        s2_pos = "B9"
        for obj in objs2.get("objects", []):
            if obj.get("id") == s2_id:
                s2_pos = obj.get("position", "B9")
                break
        print(f"Scout 2 at: {s2_pos}")

        sw_search_order = ["B10", "A10", "A11", "B11", "C11", "C10"]
        for target in sw_search_order:
            if person_found_at:
                break
            if target in south_west:
                s2_pos, found = scout_inspect_at(s2_id, s2_pos, target)

    # ── T3: covers south-east cluster ──────────────────────────────────────
    if not person_found_at and south_east:
        print("\n--- Creating T3 for south-east cluster ---")
        t3 = create_transporter(1)
        time.sleep(0.5)
        t3_id = t3.get("object", "")
        t3_scouts = [s["id"] for s in t3.get("crew", [])]
        print(f"T3 id={t3_id[:8]}, spawn={t3.get('spawn')}, scouts={[s[:8] for s in t3_scouts]}")

        # Move T3 to H9 (road adjacent to H10, I10)
        move_unit(t3_id, "H9")
        time.sleep(0.5)

        dismount(t3_id, 1)
        time.sleep(0.5)

        objs3 = get_objects()
        time.sleep(0.5)
        s3_id = t3_scouts[0] if t3_scouts else None
        s3_pos = "H9"
        for obj in objs3.get("objects", []):
            if obj.get("id") == s3_id:
                s3_pos = obj.get("position", "H9")
                break
        print(f"Scout 3 at: {s3_pos}")

        se_search_order = ["H10", "H11", "I11", "I10"]
        for target in se_search_order:
            if person_found_at:
                break
            if target in south_east:
                s3_pos, found = scout_inspect_at(s3_id, s3_pos, target)

    # ── Final check and helicopter call ───────────────────────────────────
    print("\n=== Final Status ===")
    logs = get_logs()
    time.sleep(0.3)
    print(f"Logs: {json.dumps(logs, ensure_ascii=False, indent=2)[:1000]}")

    # Also check logs for person location — look for positive find messages
    if not person_found_at:
        positive_keywords = ["go mamy", "znaleziono człowieka", "partyzant", "człowiek",
                             "mężczyzna", "kobieta", "survivor", "found him", "ocalały"]
        for entry in logs.get("logs", []):
            msg = entry.get("msg", "").lower()
            if any(kw in msg for kw in positive_keywords):
                person_found_at = entry.get("field")
                print(f"Found from logs: {person_found_at} (msg: {entry.get('msg')})")
                break

    if person_found_at:
        print(f"\n=== Calling helicopter to {person_found_at} ===")
        result = call_helicopter(person_found_at)
        print(f"FINAL RESULT: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        print("\n=== PERSON NOT FOUND - checking expenses ===")
        call_api({"action": "expenses"})


if __name__ == "__main__":
    main()