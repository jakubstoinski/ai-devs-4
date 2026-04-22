"""
S03E01 — Sensor anomaly detection agent.

Strategy:
1. Programmatic checks (no LLM):
   - Active sensor values out of range
   - Inactive sensor fields non-zero (sensor returns data it shouldn't)
2. LLM checks (operator notes only):
   - Deduplicate notes (only 2032 unique out of 9999)
   - Classify each unique note as "ok" or "problem"
   - Cross-reference with programmatic data state
   - Flag mismatches (note says OK but data bad, or note says problem but data OK)
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client
from common.central_client import send_to_central

RESOURCES = Path(__file__).parent / "resources"

SENSOR_FIELDS = {
    "temperature": "temperature_K",
    "pressure":    "pressure_bar",
    "water":       "water_level_meters",
    "voltage":     "voltage_supply_v",
    "humidity":    "humidity_percent",
}

VALID_RANGES = {
    "temperature_K":       (553, 873),
    "pressure_bar":        (60, 160),
    "water_level_meters":  (5.0, 15.0),
    "voltage_supply_v":    (229.0, 231.0),
    "humidity_percent":    (40.0, 80.0),
}

ALL_FIELDS = list(SENSOR_FIELDS.values())


def get_active_fields(sensor_type: str) -> set[str]:
    parts = [p.strip() for p in sensor_type.split("/")]
    return {SENSOR_FIELDS[p] for p in parts if p in SENSOR_FIELDS}


def check_data_anomaly(record: dict) -> bool:
    """Return True if the measurement data itself is anomalous."""
    active = get_active_fields(record["sensor_type"])
    for field in ALL_FIELDS:
        val = record.get(field, 0)
        if field in active:
            lo, hi = VALID_RANGES[field]
            if not (lo <= val <= hi):
                return True
        else:
            if val != 0:
                return True
    return False


def classify_notes_with_llm(unique_notes: list[str]) -> dict[str, str]:
    """
    Classify a batch of operator notes as 'ok' or 'problem'.
    Returns a dict mapping note text -> classification.
    Sends all notes in one request to minimise cost.
    """
    client = get_llm_client()

    numbered = "\n".join(f"{i+1}. {note}" for i, note in enumerate(unique_notes))

    prompt = f"""You are analysing operator notes from an industrial sensor system.
For each numbered note below, classify whether the operator is reporting that everything is OK ('ok') or that there is a problem/anomaly ('problem').

Reply ONLY with a JSON object mapping the note number (as string) to either "ok" or "problem".
Example: {{"1": "ok", "2": "problem", "3": "ok"}}

Notes:
{numbered}"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = json.loads(response.choices[0].message.content)
    return {unique_notes[int(k) - 1]: v for k, v in raw.items()}


def classify_all_notes(note_to_files: dict[str, list[str]]) -> dict[str, str]:
    """Classify all unique notes, batching to stay within context limits."""
    unique_notes = list(note_to_files.keys())
    print(f"  Classifying {len(unique_notes)} unique notes via LLM...")

    BATCH = 200
    result = {}
    for i in range(0, len(unique_notes), BATCH):
        batch = unique_notes[i : i + BATCH]
        print(f"    Batch {i // BATCH + 1}: notes {i+1}–{i+len(batch)}")
        result.update(classify_notes_with_llm(batch))

    return result


def main():
    files = sorted(f for f in os.listdir(RESOURCES) if f.endswith(".json"))
    print(f"Processing {len(files)} sensor files...")

    anomalous_ids = set()
    note_to_files: dict[str, list[str]] = defaultdict(list)
    file_data_state: dict[str, bool] = {}  # file_id -> data_ok

    # --- Phase 1: programmatic checks ---
    print("Phase 1: programmatic data checks...")
    for fname in files:
        file_id = fname.replace(".json", "")
        record = json.loads((RESOURCES / fname).read_text())

        data_bad = check_data_anomaly(record)
        file_data_state[file_id] = not data_bad
        if data_bad:
            anomalous_ids.add(file_id)

        note_to_files[record["operator_notes"]].append(file_id)

    print(f"  Data anomalies found: {len(anomalous_ids)}")

    # --- Phase 2: LLM note classification ---
    print("Phase 2: LLM operator-note classification...")
    note_classification = classify_all_notes(note_to_files)

    # Cross-reference note vs data
    for note, file_ids in note_to_files.items():
        note_says_ok = note_classification.get(note, "ok") == "ok"
        for file_id in file_ids:
            data_ok = file_data_state[file_id]
            if note_says_ok and not data_ok:
                # Note says OK, but data is bad → anomaly already captured; note is also wrong
                anomalous_ids.add(file_id)
            elif not note_says_ok and data_ok:
                # Note says problem, but data is fine → anomaly (false alarm note)
                anomalous_ids.add(file_id)

    anomaly_list = sorted(anomalous_ids)
    print(f"\nTotal anomalous files: {len(anomaly_list)}")
    print("Sample IDs:", anomaly_list[:10])

    # --- Phase 3: Submit ---
    print("\nSubmitting to central hub...")
    result = send_to_central("evaluation", {"recheck": anomaly_list})
    print("Response:", result)


if __name__ == "__main__":
    main()
