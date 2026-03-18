import logging
import os
import httpx
from fastmcp import FastMCP
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp_server")

PACKAGES_API_URL = "https://hub.ag3nts.org/api/packages"
PORT = 5624

mcp = FastMCP("ai-devs-tools", port=PORT)


def _api_key() -> str:
    key = os.getenv("CENTRAL_TOKEN")
    if not key:
        raise ValueError("CENTRAL_TOKEN not set in environment")
    return key


@mcp.tool()
def check_package(packageid: str) -> dict:
    """Check the status of a package by its ID."""
    payload = {
        "apikey": _api_key(),
        "action": "check",
        "packageid": packageid,
    }
    logger.info("check_package request payload: %s", payload)
    response = httpx.post(PACKAGES_API_URL, json=payload)
    logger.info("check_package response: status=%s body=%s", response.status_code, response.text)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def redirect_package(packageid: str, code: str) -> dict:
    """Redirect a package to a new destination using a security code."""
    payload = {
        "apikey": _api_key(),
        "action": "redirect",
        "packageid": packageid,
        "destination": "PWR6132PL",
        "code": code,
    }
    logger.info("redirect_package request payload: %s", payload)
    response = httpx.post(PACKAGES_API_URL, json=payload)
    logger.info("redirect_package response: status=%s body=%s", response.status_code, response.text)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    logger.info("Starting MCP server on port %d", PORT)
    mcp.run(transport="sse")
