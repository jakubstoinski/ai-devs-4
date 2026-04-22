import sys
import time
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client as get_client
from common.central_client import send_to_central

CENTRAL_TOKEN = "24f3a2ea-4f23-45a4-9056-fe5ddf3869b9"
SHELL_URL = "https://hub.ag3nts.org/api/shell"

def shell_cmd(cmd: str) -> str:
    """Execute a command on the virtual machine shell API."""
    try:
        resp = requests.post(SHELL_URL, json={"apikey": CENTRAL_TOKEN, "cmd": cmd}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps(data)
        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 10))
            return f"RATE_LIMITED: wait {retry_after}s before retrying"
        elif resp.status_code == 403:
            try:
                data = resp.json()
                ban_seconds = data.get("ban_seconds", "unknown")
                return f"BANNED for {ban_seconds}s: security violation"
            except Exception:
                return f"BANNED: {resp.text}"
        elif resp.status_code == 503:
            return "SERVICE_UNAVAILABLE: retry after a moment"
        else:
            return f"HTTP_{resp.status_code}: {resp.text[:500]}"
    except requests.exceptions.Timeout:
        return "TIMEOUT: request took too long"
    except Exception as e:
        return f"ERROR: {str(e)}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Execute a shell command on the virtual machine. Use this to explore the filesystem, run programs, and edit files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["cmd"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit the ECCS code to the central hub once you have it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The ECCS code (format: ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)"
                    }
                },
                "required": ["code"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are an expert system administrator tasked with getting a firmware application working on a restricted Linux VM.

Your goal:
1. Run /opt/firmware/cooler/cooler.bin to get an ECCS code
2. The binary requires a password - find it in the filesystem
3. Configure settings.ini if needed to make the binary work correctly
4. Get the ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx code and submit it

Important rules:
- Do NOT look in /etc, /root, or /proc/
- Respect .gitignore files - don't touch files/directories listed there
- The shell API has non-standard commands - start with `help` to see what's available
- If you get RATE_LIMITED or BANNED responses, wait before retrying
- If banned, you'll need to wait the specified seconds
- File editing works differently than standard Linux - check `help` for edit commands
- Work sequentially - plan your next action based on what you learn

When you find the ECCS code, use the submit_answer tool immediately."""

def run_agent():
    client = get_client()
    messages = [
        {"role": "user", "content": "Please start by running `help` to see available commands, then work through the steps to get the firmware running and obtain the ECCS code."}
    ]

    print("Starting firmware agent...")
    max_iterations = 50

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---")

        response = client.chat.completions.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            max_tokens=4096
        )

        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})

        if msg.content:
            print(f"Agent: {msg.content}")

        if not msg.tool_calls:
            print("Agent finished without tool calls.")
            break

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"Tool: {fn_name}({args})")

            if fn_name == "shell":
                result = shell_cmd(args["cmd"])
                print(f"Result: {result[:500]}")

                # Handle ban/rate limit with automatic wait
                if "RATE_LIMITED" in result or "wait" in result.lower():
                    wait_match = [w for w in result.split() if w.isdigit()]
                    wait_time = int(wait_match[0]) if wait_match else 15
                    print(f"Waiting {wait_time}s for rate limit...")
                    time.sleep(wait_time)

            elif fn_name == "submit_answer":
                code = args["code"]
                print(f"Submitting answer: {code}")
                result = send_to_central("firmware", {"confirmation": code})
                print(f"Submission result: {result}")
                result = f"Submitted! Response: {result}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })

    print("\nAgent loop complete.")


if __name__ == "__main__":
    run_agent()
