#!/usr/bin/env python3
"""
S01E05: Railway task — activate route X-01 via self-documenting API.

Uses an LLM (via common/llm_client) to:
  - Parse the help documentation and build an action plan
  - Interpret each API response and decide the next step

Handles 503 errors with retry/backoff and respects rate-limit headers.
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Make common/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
from llm_client import get_llm_client  # noqa: E402

API_KEY = "24f3a2ea-4f23-45a4-9056-fe5ddf3869b9"
ENDPOINT = "https://hub.ag3nts.org/verify"
ROUTE = "x-01"
LLM_MODEL = "gpt-4.1-mini"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# Railway API helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_reset_wait(headers: dict) -> float:
    for key, val in headers.items():
        lk = key.lower()
        if "retry-after" in lk:
            try:
                return float(val)
            except ValueError:
                pass
        if "ratelimit-reset-after" in lk or "x-ratelimit-reset-after" in lk:
            try:
                return float(val)
            except ValueError:
                pass
        if "x-ratelimit-reset" in lk or "ratelimit-reset" in lk:
            try:
                diff = float(val) - time.time()
                return max(1.0, diff)
            except ValueError:
                pass
    return 60.0


def _log_rl_headers(headers: dict):
    for key, val in headers.items():
        if any(x in key.lower() for x in ("ratelimit", "retry-after", "x-rate")):
            log(f"  [header] {key}: {val}")


def post_action(action: dict, max_retries: int = 30) -> tuple[dict | None, dict]:
    payload = {
        "apikey": API_KEY,
        "task": "railway",
        "answer": action,
    }
    log(f"→ {json.dumps(action)}")

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(ENDPOINT, json=payload, timeout=30)
            headers = dict(resp.headers)
            _log_rl_headers(headers)
            log(f"  HTTP {resp.status_code}")

            if resp.status_code == 503:
                wait = min(10 * attempt, 120)
                log(f"  503 (attempt {attempt}/{max_retries}) — waiting {wait}s …")
                time.sleep(wait)
                continue

            if resp.status_code == 429:
                wait = _parse_reset_wait(headers)
                log(f"  429 rate-limited — waiting {wait:.0f}s …")
                time.sleep(wait)
                continue

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            log(f"← {json.dumps(data, ensure_ascii=False)[:600]}")

            # Soft rate limit inside a 200 body
            if isinstance(data, dict) and not data.get("ok"):
                err = str(data.get("error", data.get("message", "")))
                if "limit" in err.lower() or "rate" in err.lower():
                    wait = _parse_reset_wait(headers)
                    log(f"  Soft rate limit — waiting {wait:.0f}s …")
                    time.sleep(wait)
                    continue

            return data, headers

        except requests.RequestException as exc:
            wait = 5 * attempt
            log(f"  Request error: {exc} — waiting {wait}s …")
            time.sleep(wait)

    log("Max retries exceeded.")
    return None, {}


def wait_if_limited(headers: dict):
    for key, val in headers.items():
        if "ratelimit-remaining" in key.lower() or "x-ratelimit-remaining" in key.lower():
            try:
                if int(val) <= 1:
                    wait = _parse_reset_wait(headers)
                    log(f"  Remaining={val} — proactive wait {wait:.0f}s …")
                    time.sleep(wait)
                return
            except ValueError:
                pass


def find_flag(data) -> str | None:
    m = re.search(r'\{FLG:[^}]+\}', json.dumps(data))
    return m.group(0) if m else None


# ──────────────────────────────────────────────────────────────────────────────
# LLM helpers
# ──────────────────────────────────────────────────────────────────────────────

llm = get_llm_client()

SYSTEM_PROMPT = """You are an assistant helping to interact with a railway route management API.
Your job is to decide what API action to take next in order to activate (open) route X-01.

The API endpoint accepts POST JSON with field "action" and optional fields like "route" and "value".
Route name is always lowercase: "x-01".

When you decide an action, respond with ONLY a valid JSON object representing the action payload,
for example: {"action": "setstatus", "route": "x-01", "value": "RTOPEN"}

If the task is complete (flag found or route is confirmed open), respond with: {"action": "done"}
If you encounter an error you cannot recover from, respond with: {"action": "abort", "reason": "..."}

Respond with JSON only — no explanation, no markdown fences."""


def llm_decide(history: list[dict]) -> dict:
    """Ask the LLM what action to take next given the conversation history."""
    log("  [LLM] Deciding next action …")
    resp = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        temperature=0,
        max_tokens=256,
    )
    raw = resp.choices[0].message.content.strip()
    log(f"  [LLM] → {raw}")

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log(f"  [LLM] Could not parse JSON: {raw}")
        return {"action": "abort", "reason": f"LLM output not JSON: {raw}"}


# ──────────────────────────────────────────────────────────────────────────────
# Main agentic loop
# ──────────────────────────────────────────────────────────────────────────────

def main():
    log("=== S01E05 Railway: activating route X-01 ===")

    # ── Step 1: get API documentation ────────────────────────────────────────
    log("\n--- Step 0: fetch help ---")
    help_data, headers = post_action({"action": "help"})
    wait_if_limited(headers)

    if help_data is None:
        log("Failed to get help. Exiting.")
        sys.exit(1)

    flag = find_flag(help_data)
    if flag:
        log(f"\nFLAG: {flag}")
        return

    # Build the LLM conversation history
    history: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Here is the API documentation returned by the 'help' action:\n"
                f"{json.dumps(help_data, ensure_ascii=False, indent=2)}\n\n"
                f"Goal: activate (open) route X-01. "
                f"What is the first API action you should call?"
            ),
        }
    ]

    max_steps = 15
    for step in range(1, max_steps + 1):
        log(f"\n--- LLM step {step}/{max_steps} ---")

        decision = llm_decide(history)

        # Record LLM decision in history
        history.append({
            "role": "assistant",
            "content": json.dumps(decision),
        })

        action_name = decision.get("action", "")

        if action_name == "done":
            log("LLM says task is done.")
            break

        if action_name == "abort":
            log(f"LLM aborted: {decision.get('reason', 'unknown')}")
            sys.exit(1)

        if not action_name:
            log(f"LLM returned unexpected: {decision}")
            break

        # Execute the action
        api_response, resp_headers = post_action(decision)
        wait_if_limited(resp_headers)

        if api_response is None:
            history.append({
                "role": "user",
                "content": "The API call failed (no response after retries). What should we do?",
            })
            continue

        # Check for flag
        flag = find_flag(api_response)
        if flag:
            log(f"\nFLAG: {flag}")
            return

        # Feed the response back to the LLM
        history.append({
            "role": "user",
            "content": (
                f"The API returned:\n{json.dumps(api_response, ensure_ascii=False, indent=2)}\n\n"
                f"What is the next action to take to activate route X-01?"
            ),
        })

    log("\nAgentloop finished. No flag found.")
    log("Final conversation history (last 3 turns):")
    for msg in history[-3:]:
        log(f"  [{msg['role']}] {msg['content'][:300]}")


if __name__ == "__main__":
    main()