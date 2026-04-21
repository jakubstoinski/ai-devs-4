#!/usr/bin/env python3
"""Agentic log analyzer for s02e03 - failure task."""

import re
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../resources/.env'))

API_KEY = os.getenv('CENTRAL_TOKEN')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'resources/failure.log')
HUB_VERIFY = 'https://hub.ag3nts.org/verify'

# Conservative token estimate: 1 token ≈ 3.5 chars
def estimate_tokens(text: str) -> int:
    return int(len(text) / 3.5) + 1

def compress_event(line: str) -> str:
    """Compress a log line to a shorter form while keeping key info."""
    # Parse: [2026-04-20 HH:MM:SS] [LEVEL] COMPONENT message
    m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}\] \[(\w+)\] (.+)', line)
    if not m:
        return line.strip()
    date, time, level, msg = m.group(1), m.group(2), m.group(3), m.group(4)

    # Shorten common message patterns
    compressions = [
        (r'ECCS8 reported runaway outlet temperature\. Protection interlock initiated reactor trip\.',
         'ECCS8 runaway outlet temp. Reactor trip.'),
        (r'ECCS8 core cooling cannot maintain safe gradient\. Immediate protective actions are required\.',
         'ECCS8 cooling gradient unsafe. Protective action.'),
        (r'ECCS8 cannot remove heat with the current WTANK07 volume\. Reactor protection initiates critical stop\.',
         'ECCS8 heat removal failed (WTANK07 low). Critical stop.'),
        (r'Critical boundary exceeded on ECCS8\. Emergency interlock keeps the reactor in protected mode\.',
         'ECCS8 critical boundary exceeded. Emergency interlock.'),
        (r'Coolant inventory in WTANK07 is below critical threshold for full-loop operation\. ECCS8 cannot guarantee reactor heat removal and automatic shutdown is mandatory\.',
         'WTANK07 inventory critical. ECCS8 shutdown mandatory.'),
        (r'Insufficient cooling capacity confirmed after incomplete WTANK07 refill\. Reactor protection system executes final shutdown sequence\.',
         'WTANK07 refill incomplete. Reactor final shutdown.'),
        (r'WSTPOOL2 absorption path reached emergency boundary\. Heat rejection is no longer sufficient\.',
         'WSTPOOL2 heat rejection failed.'),
        (r'WSTPOOL2 entered critical protection state during startup\. Immediate shutdown safeguards remain active\.',
         'WSTPOOL2 critical protection state.'),
        (r'WTANK07 coolant level is below critical threshold\. Shutdown logic is moving to hard trip stage\.',
         'WTANK07 coolant critical. Hard trip.'),
        (r'Final trip complete because WTANK07 remained under critical water level\. FIRMWARE confirms safe shutdown state with all core operations halted\.',
         'WTANK07 low -> final trip. FIRMWARE: core halted.'),
        (r'WTRPMP lost stable prime under peak thermal demand\. Core loop continuity is compromised\.',
         'WTRPMP lost prime. Core loop disrupted.'),
        (r'PWR01 can no longer sustain stable feed for cooling auxiliaries\. Critical loads are shedding\.',
         'PWR01 feed unstable. Load shedding.'),
        (r'FIRMWARE entered emergency guard branch after repeated safety faults\. Manual override is locked\.',
         'FIRMWARE emergency guard. Override locked.'),
        (r'Safety bootstrap read missing environment marker SAFETY_CHECK=pass\. FIRMWARE continues in restricted validation mode\.',
         'FIRMWARE missing SAFETY_CHECK=pass. Restricted mode.'),
        (r'STMTURB12 decoupling sequence forced by thermal risk\. Energy conversion is terminated\.',
         'STMTURB12 thermal decoupling. Energy terminated.'),
        # WARN/ERRO compressions
        (r'Thermal drift on ECCS8 exceeds advisory threshold\. Corrective ramp is queued\.',
         'ECCS8 thermal drift advisory.'),
        (r'Fill trajectory in WTANK07 is slower than expected\. Cooling reserve may become constrained\.',
         'WTANK07 fill rate low.'),
        (r'FIRMWARE validation queue returned nonblocking fault set\. Runtime proceeds in constrained mode\.',
         'FIRMWARE validation fault. Constrained mode.'),
        (r'Flow margin on WTRPMP is below preferred startup profile\. Monitoring continues without immediate trip\.',
         'WTRPMP flow margin low.'),
        (r'Input ripple on PWR01 crossed warning limits\. Stability window is narrowed\.',
         'PWR01 input ripple warning.'),
        (r'Pressure jitter near STMTURB12 is above baseline\. Automatic damping remains engaged\.',
         'STMTURB12 pressure jitter.'),
        (r'FIRMWARE watchdog acknowledged delayed subsystem poll\.',
         'FIRMWARE watchdog delay.'),
        (r'ECCS8 reports rising return temperature\. Cooling headroom is decreasing\.',
         'ECCS8 rising return temp.'),
        (r'Waste heat relay to WSTPOOL2 is approaching soft cap\.',
         'WSTPOOL2 heat relay near cap.'),
        (r'PWR01 transient disturbed auxiliary pump control\. Recovery completed with degraded margin\.',
         'PWR01 transient, aux pump degraded.'),
        (r'WTANK07 indicates unstable refill trend\. Available coolant inventory is no longer guaranteed\.',
         'WTANK07 refill unstable.'),
        (r'STMTURB12 feedback loop exceeded correction budget\. Thermal conversion rate is reduced\.',
         'STMTURB12 correction budget exceeded.'),
        (r'WTRPMP duty cycle is elevated for current load\.',
         'WTRPMP duty cycle elevated.'),
        (r'Level sensor reconciliation for WTANK07 returned minor mismatch\.',
         'WTANK07 sensor mismatch.'),
        (r'WTRPMP suction profile is inconsistent with expected coolant volume\. Mechanical stress is increasing\.',
         'WTRPMP suction inconsistent. Stress rising.'),
        (r'FIRMWARE reports a trend outside preferred startup envelope\.',
         'FIRMWARE startup trend anomaly.'),
        (r'Heat transfer path to WSTPOOL2 is saturated\. Dissipation lag continues to accumulate\.',
         'WSTPOOL2 heat path saturated.'),
        (r'Cooling efficiency on ECCS8 dropped below operational target\.',
         'ECCS8 cooling efficiency below target.'),
        (r'WTANK07 level estimate dropped near minimum reserve line\. Automatic refill request timed out\.',
         'WTANK07 near minimum, refill timeout.'),
        (r'ECCS8 return circuit temperature rose faster than prediction\. Emergency bias remains armed\.',
         'ECCS8 return temp rising fast. Emergency bias armed.'),
        (r'WTRPMP reported repeated cavitation signatures\. Output pressure cannot be held\.',
         'WTRPMP cavitation. Pressure unstable.'),
        (r'Advisory threshold crossed on WTANK07\.',
         'WTANK07 advisory threshold crossed.'),
        (r'Power stability on PWR01 is highly unstable under startup load\.',
         'PWR01 highly unstable under load.'),
        (r'WSTPOOL2 shows moderate parameter drift during initialization\.',
         'WSTPOOL2 param drift.'),
        (r'Preventive warning issued for WTRPMP due to unstable short-term readings\.',
         'WTRPMP unstable readings.'),
        (r'PWR01 failed a recovery step in the active sequence\.',
         'PWR01 recovery failed.'),
        (r'WTANK07 reports a trend outside preferred startup envelope\.',
         'WTANK07 startup trend anomaly.'),
        (r'Cooling reserve trend in WTANK07 keeps falling during load rise\. ECCS8 is approaching a nonrecoverable limit\.',
         'WTANK07 cooling reserve falling. ECCS8 near limit.'),
        (r'ECCS8 fails to recover thermal margin while WTANK07 remains partially filled\.',
         'ECCS8 thermal margin unrecoverable. WTANK07 partial.'),
        (r'Operational fault persisted on ECCS8 after retry cycle\.',
         'ECCS8 persistent fault.'),
        (r'ECCS8 shows moderate parameter drift during initialization\.',
         'ECCS8 param drift.'),
        (r'Preventive warning issued for WTANK07 due to unstable short-term readings\.',
         'WTANK07 unstable readings.'),
        (r'ECCS8 returned inconsistent feedback under load\.',
         'ECCS8 inconsistent feedback.'),
        (r'Coolant level in WTANK07 is below critical reserve for sustained operation\.',
         'WTANK07 below critical reserve.'),
        (r'Control response from WTANK07 exceeded error budget\.',
         'WTANK07 error budget exceeded.'),
        (r'WTANK07 failed a recovery step in the active sequence\.',
         'WTANK07 recovery failed.'),
        (r'Operational fault persisted on WTANK07 after retry cycle\.',
         'WTANK07 persistent fault.'),
        (r'WTANK07 returned inconsistent feedback under load\.',
         'WTANK07 inconsistent feedback.'),
        (r'ECCS8 failed a recovery step in the active sequence\.',
         'ECCS8 recovery step failed.'),
    ]

    compressed_msg = msg
    for pattern, replacement in compressions:
        if re.search(pattern, msg):
            compressed_msg = replacement
            break

    return f'[{date} {time}] [{level}] {compressed_msg}'

def load_and_filter_logs():
    """Load log, filter WARN/ERRO/CRIT, and deduplicate intelligently."""
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()

    # Filter to WARN/ERRO/CRIT only
    filtered = [l.strip() for l in lines if re.search(r'\[WARN\]|\[ERRO\]|\[CRIT\]', l)]

    # Group by (component, level, message_type) - keep first occurrence of each unique event type
    # Plus ALL CRIT events for timeline
    seen_warn_erro = set()  # (component, level, msg_pattern) -> only first
    result = []

    for line in filtered:
        m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}\] \[(\w+)\] (\w+)\s+(.*)', line)
        if not m:
            continue
        date, time, level, component, msg = m.groups()

        # Truncate message to first sentence for dedup key
        msg_key = msg.split('.')[0][:80]
        event_key = (component, level, msg_key)

        if level == 'CRIT':
            result.append(line)
        elif level in ('WARN', 'ERRO'):
            if event_key not in seen_warn_erro:
                seen_warn_erro.add(event_key)
                result.append(line)

    return result

def build_compressed_log(events: list[str], max_tokens: int = 1400) -> str:
    """Build compressed log string within token limit."""
    compressed = [compress_event(e) for e in events]

    # Deduplicate: keep only FIRST occurrence per (component, msg_key) for CRIT
    # Keep first per type for WARN/ERRO
    crit_seen = {}   # (component, msg_key) -> first_line
    warn_seen = {}   # (component, level, msg_key) -> first_line
    result_lines = []

    for line in compressed:
        m = re.match(r'\[.+?\] \[(\w+)\] (\w+)\s*(.*)', line)
        if not m:
            continue
        level, component, msg = m.groups()
        msg_key = msg.split('.')[0][:60]
        key = (component, msg_key)

        if level == 'CRIT':
            if key not in crit_seen:
                crit_seen[key] = line
                result_lines.append(line)
        else:
            wkey = (component, level, msg_key)
            if wkey not in warn_seen:
                warn_seen[wkey] = line
                result_lines.append(line)

    result = '\n'.join(result_lines)
    tokens = estimate_tokens(result)
    print(f"After dedup: {len(result_lines)} events, ~{tokens} tokens")

    return result

def submit_logs(logs_str: str) -> dict:
    """Submit logs to hub and return response."""
    payload = {
        "apikey": API_KEY,
        "task": "failure",
        "answer": {"logs": logs_str}
    }
    resp = requests.post(HUB_VERIFY, json=payload)
    return resp.json()

def add_events_for_component(component: str, current_events: list[str]) -> list[str]:
    """Add all events for a specific component from the log file."""
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()

    existing_lines = set(current_events)
    new_events = []

    for line in lines:
        line = line.strip()
        if component in line and re.search(r'\[WARN\]|\[ERRO\]|\[CRIT\]', line):
            if line not in existing_lines:
                new_events.append(line)

    return new_events

def main():
    print("=== Failure Log Agent ===")

    # Step 1: Build initial compressed log
    events = load_and_filter_logs()
    print(f"Filtered events: {len(events)} WARN/ERRO/CRIT")

    logs_str = build_compressed_log(events)
    tokens = estimate_tokens(logs_str)
    lines_count = len(logs_str.split('\n'))
    print(f"Compressed log: {lines_count} lines, ~{tokens} tokens")

    if tokens > 1500:
        print(f"WARNING: Estimated {tokens} tokens, may exceed limit!")

    # Save for inspection
    with open('/Users/jbso/New Repo/ai-devs-4/s02e03/resources/compressed_log.txt', 'w') as f:
        f.write(logs_str)
    print("Saved compressed log to resources/compressed_log.txt")

    # Step 2: Submit and iterate
    iteration = 0
    current_events = events.copy()

    while iteration < 5:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        logs_str = build_compressed_log(current_events)
        tokens = estimate_tokens(logs_str)
        print(f"Submitting: {len(logs_str.split(chr(10)))} lines, ~{tokens} tokens")

        if tokens > 1500:
            print("Token limit exceeded, need further compression")
            break

        response = submit_logs(logs_str)
        print(f"Response: {json.dumps(response, indent=2)}")

        # Check for flag
        if 'FLG:' in str(response):
            print("\n*** GOT FLAG! ***")
            break

        # Check message for feedback
        msg = response.get('message', '') or response.get('hint', '') or str(response)

        if response.get('code') == 0 or 'congratulations' in msg.lower():
            print("Success!")
            break

        # Extract missing components from feedback and add their events
        # Common patterns: "cannot analyze COMPONENT", "missing data for COMPONENT"
        components_to_add = re.findall(r'\b(ECCS8|WSTPOOL2|WTANK07|WTRPMP|PWR01|FIRMWARE|STMTURB12)\b', msg)

        if components_to_add:
            print(f"Feedback mentions components: {components_to_add}")
            for comp in set(components_to_add):
                new_evts = add_events_for_component(comp, [compress_event(e) for e in current_events])
                if new_evts:
                    print(f"  Adding {len(new_evts)} events for {comp}")
                    current_events.extend(new_evts)
        else:
            print("No specific components mentioned, stopping")
            break

if __name__ == '__main__':
    main()
