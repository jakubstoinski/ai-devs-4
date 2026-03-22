import sys
import json
import logging
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn
from mcp.client.sse import sse_client
from mcp import ClientSession
from common.llm_client import get_llm_client

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_server")

MCP_SERVER_URL = "http://localhost:5624/sse"

llm_client = get_llm_client()

# sessionID -> list of messages [{role, content}]
sessions: dict[str, list[dict]] = {}

SYSTEM_PROMPT = (
    "You are a helpful human assistant. Respond naturally and conversationally, "
    "as a knowledgeable person would. Keep responses concise and friendly. "
    "You have access to tools for managing packages — use them when relevant."
    "act like a human and answer about any unrelevant to ligistcs question the best you can."
    "If package is redirect please report that package ahs been redirected as ordered in user language"
)


async def get_mcp_tools() -> list[dict]:
    """Fetch tool definitions from the MCP server and convert to OpenAI format."""
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

    openai_tools = []
    for tool in tools_result.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        })
    logger.info("fetched %d tools from MCP server: %s", len(openai_tools), [t["function"]["name"] for t in openai_tools])
    return openai_tools


async def call_mcp_tool(name: str, args: dict) -> str:
    """Call a tool on the MCP server and return the result as a string."""
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args)

    content = result.content
    if content and hasattr(content[0], "text"):
        return content[0].text
    return json.dumps([c.model_dump() for c in content])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting agent server, MCP backend: %s", MCP_SERVER_URL)
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    logger.info(">>> %s %s | body: %s", request.method, request.url.path, body.decode(errors="replace"))
    response = await call_next(request)
    logger.info("<<< status=%d", response.status_code)
    return response


class ChatRequest(BaseModel):
    sessionID: str
    msg: str


class ChatResponse(BaseModel):
    msg: str


@app.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.sessionID
    logger.info("chat request | session=%s msg=%r", session_id, request.msg)

    if session_id not in sessions:
        logger.info("new session: %s", session_id)
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    sessions[session_id].append({"role": "user", "content": request.msg})
    logger.debug("session history length: %d", len(sessions[session_id]))

    try:
        tools = await get_mcp_tools()

        # agentic loop — keep going until no more tool calls
        while True:
            logger.info("calling LLM for session=%s", session_id)
            response = llm_client.chat.completions.create(
                model="gpt-5-mini",
                messages=sessions[session_id],
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            assistant_msg: dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ]
            sessions[session_id].append(assistant_msg)

            if not message.tool_calls:
                reply = message.content
                logger.info("LLM final reply | session=%s reply=%r", session_id, reply)
                break

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                logger.info("tool call | name=%s args=%s", name, args)

                try:
                    result = await call_mcp_tool(name, args)
                except Exception as te:
                    result = json.dumps({"error": str(te)})
                    logger.error("tool error | name=%s error=%s", name, te)

                logger.info("tool result | name=%s result=%s", name, result)
                sessions[session_id].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

    except Exception as e:
        logger.error("error | session=%s error=%s\n%s", session_id, e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(msg=reply)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
