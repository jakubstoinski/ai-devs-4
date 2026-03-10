import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")


def get_llm_client() -> OpenAI:
    """Return an OpenAI-compatible client pointed at the LLM router."""
    api_key = os.getenv("LLM_ROUTER_TOKEN")
    if not api_key:
        raise ValueError("LLM_ROUTER_TOKEN not set in environment")

    return OpenAI(
        api_key=api_key,
        base_url="https://llmrouter.gft.com/",
    )
