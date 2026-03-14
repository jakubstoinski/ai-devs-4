import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="../resources/.env")

sys.path.append("..")

ACCESS_LEVEL_API_URL = "https://hub.ag3nts.org/api/accesslevel"


def get_access_level(name: str, surname: str, birth_year: int) -> dict:
    """Look up the access level of a person by name, surname, and birth year.

    Args:
        name: Person's first name
        surname: Person's last name
        birth_year: Person's year of birth

    Returns:
        Response JSON from the access level API
    """
    api_key = os.getenv("CENTRAL_TOKEN")
    if not api_key:
        raise ValueError("CENTRAL_TOKEN not set in environment")

    payload = {
        "apikey": api_key,
        "name": name,
        "surname": surname,
        "birthYear": birth_year,
    }

    response = requests.post(ACCESS_LEVEL_API_URL, json=payload)
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code}: {response.text}", response=response)
    return response.json()


GET_ACCESS_LEVEL_TOOL = {
    "type": "function",
    "function": {
        "name": "get_access_level",
        "description": "Look up the access level of a person by their first name, last name, and birth year.",
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
                "birth_year": {
                    "type": "integer",
                    "description": "Person's year of birth",
                },
            },
            "required": ["name", "surname", "birth_year"],
        },
    },
}


if __name__ == "__main__":
    result = get_access_level("Jan", "Kowalski", 1987)
    print("Access level result:", result)
