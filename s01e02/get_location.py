import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="../resources/.env")

sys.path.append("..")

LOCATION_API_URL = "https://hub.ag3nts.org/api/location"


def get_location(name: str, surname: str) -> dict:
    """Look up the location of a person by name and surname.

    Args:
        name: Person's first name
        surname: Person's last name

    Returns:
        Response JSON from the location API
    """
    api_key = os.getenv("CENTRAL_TOKEN")
    if not api_key:
        raise ValueError("CENTRAL_TOKEN not set in environment")

    payload = {
        "apikey": api_key,
        "name": name,
        "surname": surname,
    }

    response = requests.post(LOCATION_API_URL, json=payload)
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code}: {response.text}", response=response)
    return response.json()


# Tool definition for LLM function calling
GET_LOCATION_TOOL = {
    "type": "function",
    "function": {
        "name": "get_location",
        "description": "Look up all locations where a person has been seen, by their first name and last name. Returns a list of locations.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Person's first name",
                },
                "surname": {
                    "type": "string",
                    "description": "Person's last name",
                },
            },
            "required": ["name", "surname"],
        },
    },
}


if __name__ == "__main__":
    result = get_location("Cezary", "Żurek")
    print("Location result:", result)
