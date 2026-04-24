import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

API_KEY = os.getenv("CENTRAL_TOKEN")
URL = "https://hub.ag3nts.org/verify"
TASK = "windpower"

CUTOFF_WIND = 14       # m/s — above this is a dangerous storm
MIN_PROD_WIND = 6      # m/s — minimum wind for 4-5 kW production at pitch=0


def call(action, **kwargs):
    payload = {"apikey": API_KEY, "task": TASK, "answer": {"action": action, **kwargs}}
    r = requests.post(URL, json=payload, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text, "_status": r.status_code}


def poll_results(expected_count: int, timeout: float = 30.0) -> list:
    results = []
    deadline = time.time() + timeout
    while len(results) < expected_count:
        if time.time() > deadline:
            print(f"  WARNING: timeout — got {len(results)}/{expected_count} results")
            break
        r = call("getResult")
        if r.get("code") == 11:  # no result ready yet
            time.sleep(0.15)
            continue
        results.append(r)
        src = r.get("sourceFunction", "unknown")
        print(f"  [result {len(results)}/{expected_count}] sourceFunction={src}")
    return results


# ---------------------------------------------------------------------------
# Step 1: Start session
# ---------------------------------------------------------------------------
print("=== Starting service window ===")
start_resp = call("start")
print(f"  {start_resp}")
session_start = time.time()

# ---------------------------------------------------------------------------
# Step 2: Queue data requests in parallel
# ---------------------------------------------------------------------------
print("\n=== Queuing data requests ===")

def queue_get(param):
    r = call("get", param=param)
    print(f"  queued {param}: code={r.get('code')}")
    return param, r

with ThreadPoolExecutor(max_workers=2) as ex:
    futures = [ex.submit(queue_get, p) for p in ("weather", "powerplantcheck")]
    queued = {param: resp for param, resp in (f.result() for f in as_completed(futures))}

# ---------------------------------------------------------------------------
# Step 3: Collect weather + powerplant results
# ---------------------------------------------------------------------------
print("\n=== Collecting data results ===")
data_results = poll_results(2, timeout=25)

weather_data = None
powerplant_data = None
for r in data_results:
    src = r.get("sourceFunction")
    if src == "weather":
        weather_data = r
    elif src == "powerplantcheck":
        powerplant_data = r

if not weather_data or not powerplant_data:
    print("ERROR: missing data")
    sys.exit(1)

forecast = weather_data["forecast"]
deficit_str = powerplant_data.get("powerDeficitKw", "4-5")
print(f"  Power deficit: {deficit_str} kW")
print(f"  Forecast entries: {len(forecast)}")

# Show all wind values (useful for debugging production window)
print("  All forecast wind values >= 4 m/s:")
for e in forecast:
    if float(e["windMs"]) >= 4.0:
        print(f"    {e['timestamp']} → {e['windMs']} m/s")

# ---------------------------------------------------------------------------
# Step 4: Analyse forecast
# ---------------------------------------------------------------------------
print("\n=== Analysing forecast ===")

storm_entries = []
best_production = None      # (wind, entry) — track highest non-storm wind
storm_timestamps = set()

for entry in forecast:
    ts = entry["timestamp"]       # "2026-04-24 18:00:00"
    wind = float(entry["windMs"])
    date_part, time_part = ts.split(" ")

    if wind > CUTOFF_WIND:
        storm_entries.append({
            "startDate": date_part,
            "startHour": time_part,
            "windMs": wind,
            "pitchAngle": 90,
            "turbineMode": "idle",
        })
        storm_timestamps.add(ts)
        print(f"  STORM at {ts} — wind={wind} m/s → pitch=90, idle")

for entry in forecast:
    ts = entry["timestamp"]
    wind = float(entry["windMs"])
    date_part, time_part = ts.split(" ")
    if ts in storm_timestamps:
        continue
    if wind < 4.0:
        continue
    # Prefer earliest slot that covers the deficit; track best by wind speed
    if best_production is None or wind > best_production[0]:
        best_production = (wind, {
            "startDate": date_part,
            "startHour": time_part,
            "windMs": wind,
            "pitchAngle": 0,
            "turbineMode": "production",
        })

production_entry = best_production[1] if best_production else None
if production_entry:
    print(f"  PRODUCTION at {production_entry['startDate']} {production_entry['startHour']} — wind={production_entry['windMs']} m/s → pitch=0, production")
else:
    print("  WARNING: no suitable production window found")

all_configs = storm_entries + ([production_entry] if production_entry else [])
print(f"\n  Total config points: {len(all_configs)}")

# ---------------------------------------------------------------------------
# Step 5: Queue unlockCodeGenerator for all config points in parallel
# ---------------------------------------------------------------------------
print("\n=== Queuing unlockCode generation ===")

def queue_unlock(cfg):
    r = call(
        "unlockCodeGenerator",
        startDate=cfg["startDate"],
        startHour=cfg["startHour"],
        windMs=cfg["windMs"],
        pitchAngle=cfg["pitchAngle"],
    )
    print(f"  queued unlockCode {cfg['startDate']} {cfg['startHour']}: code={r.get('code')}")
    return cfg, r

with ThreadPoolExecutor(max_workers=len(all_configs)) as ex:
    futures = [ex.submit(queue_unlock, cfg) for cfg in all_configs]
    for f in as_completed(futures):
        f.result()

# ---------------------------------------------------------------------------
# Step 6: Collect unlock codes
# ---------------------------------------------------------------------------
print("\n=== Collecting unlock codes ===")
unlock_results = poll_results(len(all_configs), timeout=25)

print("\nRaw unlock results:")
for r in unlock_results:
    print(f"  {json.dumps(r)}")

# Build a mapping: (startDate, startHour) -> unlockCode
# The result echoes request params inside signedParams.
unlock_map = {}
for r in unlock_results:
    signed = r.get("signedParams", {})
    sd = signed.get("startDate")
    sh = signed.get("startHour")
    code = r.get("unlockCode")
    if sd and sh and code:
        unlock_map[(sd, sh)] = code
        print(f"  mapped ({sd}, {sh}) -> {code}")

# ---------------------------------------------------------------------------
# Step 7: Build and send batch config
# ---------------------------------------------------------------------------
print("\n=== Sending batch config ===")

configs = {}
for cfg in all_configs:
    key = f"{cfg['startDate']} {cfg['startHour']}"
    unlock_code = unlock_map.get((cfg["startDate"], cfg["startHour"]), "")
    configs[key] = {
        "pitchAngle": cfg["pitchAngle"],
        "turbineMode": cfg["turbineMode"],
        "unlockCode": unlock_code,
    }
    print(f"  {key}: pitch={cfg['pitchAngle']}, mode={cfg['turbineMode']}, code={unlock_code!r}")

config_resp = call("config", configs=configs)
print(f"\n  Config response: {config_resp}")

# ---------------------------------------------------------------------------
# Step 8: Turbinecheck (required before done)
# ---------------------------------------------------------------------------
print("\n=== Running turbinecheck ===")
call("get", param="turbinecheck")
tc_results = poll_results(1, timeout=20)
print(f"  Turbinecheck: {tc_results}")

# ---------------------------------------------------------------------------
# Step 9: Done
# ---------------------------------------------------------------------------
elapsed = time.time() - session_start
print(f"\n=== Sending done (elapsed {elapsed:.1f}s) ===")
done_resp = call("done")
print(f"  {done_resp}")