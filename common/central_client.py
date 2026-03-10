import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

CENTRAL_API_URL = "https://hub.ag3nts.org/verify"


def send_to_central(task: str, answer) -> dict:
    """Send answer to central hub.

    Args:
        task: task name (e.g. "people")
        answer: answer payload (string, list, or dict)

    Returns:
        Response JSON from central hub
    """
    api_key = os.getenv("CENTRAL_TOKEN")
    if not api_key:
        raise ValueError("CENTRAL_TOKEN not set in environment")

    payload = {
        "apikey": api_key,
        "task": task,
        "answer": answer,
    }

    response = requests.post(CENTRAL_API_URL, json=payload)
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code}: {response.text}", response=response)
    return response.json()
