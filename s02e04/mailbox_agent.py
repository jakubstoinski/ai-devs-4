import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.llm_client import get_llm_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

ZMAIL_URL = "https://hub.ag3nts.org/api/zmail"
VERIFY_URL = "https://hub.ag3nts.org/verify"
APIKEY = os.getenv("CENTRAL_TOKEN")
MODEL = "gpt-4.1-mini"

RESOURCES_DIR = Path(__file__).parent / "resources"
RESOURCES_DIR.mkdir(exist_ok=True)


def zmail_request(action: str, page: int = 1, query: str = None, ids=None, thread_id: int = None) -> dict:
    import time
    payload = {"apikey": APIKEY, "action": action, "page": page}
    if query is not None:
        payload["query"] = query
    if ids is not None:
        payload["ids"] = ids
    if thread_id is not None:
        payload["threadID"] = thread_id
    resp = requests.post(ZMAIL_URL, json=payload)
    data = resp.json()
    if isinstance(data, dict) and data.get("code") == -9999:
        print("[Rate limited] Waiting 10s...")
        time.sleep(10)
        resp = requests.post(ZMAIL_URL, json=payload)
        data = resp.json()
    return data


def submit_answer(password: str, date: str, confirmation_code: str) -> dict:
    payload = {
        "apikey": APIKEY,
        "task": "mailbox",
        "answer": {
            "password": password,
            "date": date,
            "confirmation_code": confirmation_code,
        },
    }
    resp = requests.post(VERIFY_URL, json=payload)
    return resp.json()


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_mail",
            "description": "Search the mailbox using Gmail-style operators (from:, to:, subject:, OR, AND). Returns list of messages with metadata but NOT full body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. 'from:proton.me' or 'subject:password'"},
                    "page": {"type": "integer", "description": "Page number, starting at 1", "default": 1},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inbox",
            "description": "Get all inbox messages (paginated, no body).",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "description": "Page number, starting at 1", "default": 1},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_messages",
            "description": "Get full content of one or more messages by their rowID (integer) or messageID (32-char hash). Pass a single value or a list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "description": "A single rowID (integer), a single messageID (32-char hash), or a list of them.",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "integer"},
                            {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
                        ],
                    },
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_thread",
            "description": "Get list of message IDs in a thread (no body). Use threadID from search/inbox results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "integer", "description": "Thread ID"},
                },
                "required": ["thread_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_rate_limit",
            "description": "Reset the API rate limit counter. Call this if you get rate limit errors.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit the three collected values to the hub and get the flag. Use when you have all three: password, date, confirmation_code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "password": {"type": "string", "description": "The employee system password found in the mailbox"},
                    "date": {"type": "string", "description": "Attack date in YYYY-MM-DD format"},
                    "confirmation_code": {"type": "string", "description": "Ticket confirmation code starting with SEC- (36 chars total)"},
                },
                "required": ["password", "date", "confirmation_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_api_help",
            "description": "Get the API help documentation to learn all available actions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = """You are a security researcher searching an email inbox to find three pieces of information:

1. **date** - when the security department plans an attack on the power plant (format YYYY-MM-DD)
2. **password** - the employee system password that is likely still in the mailbox
3. **confirmation_code** - ticket confirmation code sent by the security department (format: SEC- + 32 chars = 36 chars total)

Key facts:
- A person named Wiktor (from proton.me domain) sent an email ratting us out
- The mailbox is active - new messages may arrive during your search
- Use search operators: from:, to:, subject:, OR, AND
- Always fetch full message content before drawing conclusions from a message

Strategy:
1. Search broadly first (from:proton.me, subject:password, subject:security, subject:attack, subject:SEC-)
2. Read full message content using get_messages with the messageID or rowID
3. For threads, use get_thread to list messages then get_messages to read them
4. Keep searching until all three values are found
5. The mailbox may have many pages - paginate if needed
6. If something isn't found, retry later as new messages may arrive
7. Call reset_rate_limit if you get rate limit errors

When you have all three values, call submit_answer to get the flag."""


def run_tool(name: str, args: dict) -> str:
    if name == "get_api_help":
        result = zmail_request("help")
    elif name == "get_inbox":
        result = zmail_request("getInbox", page=args.get("page", 1))
    elif name == "search_mail":
        result = zmail_request("search", page=args.get("page", 1), query=args["query"])
    elif name == "get_messages":
        result = zmail_request("getMessages", ids=args["ids"])
    elif name == "get_thread":
        result = zmail_request("getThread", thread_id=args["thread_id"])
    elif name == "reset_rate_limit":
        result = zmail_request("reset")
    elif name == "submit_answer":
        result = submit_answer(args["password"], args["date"], args["confirmation_code"])
        log_result = {"action": "submit_answer", "args": args, "result": result}
        with open(RESOURCES_DIR / "submission_log.json", "w") as f:
            json.dump(log_result, f, indent=2, ensure_ascii=False)
        print(f"\n[SUBMISSION RESULT]: {result}")
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, ensure_ascii=False)


def main():
    client = get_llm_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Start searching the mailbox to find the date, password, and confirmation_code. Begin by checking the help and then search systematically."},
    ]

    iteration = 0
    max_iterations = 50

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(f"Agent response (no tool calls): {msg.content}")
            break

        for tc in msg.tool_calls:
            import time
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"[Tool] {name}({args})")
            time.sleep(1)

            result = run_tool(name, args)
            result_preview = result[:500] + "..." if len(result) > 500 else result
            print(f"[Result] {result_preview}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        with open(RESOURCES_DIR / "agent_messages.json", "w") as f:
            serializable = []
            for m in messages:
                if hasattr(m, "model_dump"):
                    serializable.append(m.model_dump())
                else:
                    serializable.append(m)
            json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nAgent finished after {iteration} iterations.")


if __name__ == "__main__":
    main()
