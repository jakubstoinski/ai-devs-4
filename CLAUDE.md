# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI-devs 4: Builders** — a practical training course on building production AI agent applications. Each episode (s01eXX / s02eXX) is a self-contained task that builds on previous results and submits answers to a central verification hub at `hub.ag3nts.org`.

## Environment Setup

Python 3.13 with a `.venv/` at the repo root. API keys live in `resources/.env` (not tracked):
```
CENTRAL_TOKEN=<hub token>
LLM_ROUTER_TOKEN=<LLM router token>
```

Activate the venv: `source .venv/bin/activate`

## Running Episodes

### S01E01
```bash
cd s01e01 && python filter_people.py
# Outputs: s01e02/resources/people_sent.json
```

### S01E02
```bash
cd s01e02 && python findhim.py
# Requires: s01e02/resources/people_sent.json (from s01e01)
```

### S01E03 (requires three terminals)
```bash
# Terminal 1 — MCP server
cd common && python mcp_server.py        # port 5624 SSE

# Terminal 2 — Agent server
cd s01e03 && python agent_server.py      # port 3000

# Terminal 3 — Register with hub
cd s01e03 && python register_agent.py
```

### S01E04
```bash
cd s01e04 && python submit_declaration.py
```

### S01E05
```bash
cd s01e05 && python railway.py
```

## Architecture

### Common Utilities (`common/`)
- **`llm_client.py`** — Returns an `OpenAI`-compatible client pointing to `https://llmrouter.gft.com/` using `LLM_ROUTER_TOKEN`. Always use this instead of instantiating `OpenAI` directly.
- **`central_client.py`** — `send_to_central(task, answer)` POSTs answers to `hub.ag3nts.org/verify`. Every episode ends by calling this.
- **`mcp_server.py`** — FastMCP server exposing package tools (`check_package`, `redirect_package`) on SSE at port 5624. Used by s01e03.
- **`llm_models.md`** — Reference list of models available through the LLM router (GPT-4.1/5/5.1, Claude Opus/Sonnet/Haiku).

### Episode Pattern
Each episode follows this progression:
1. Fetch or read input data
2. Run an agentic loop (LLM + optional tools)
3. Submit the answer via `send_to_central()`

### Agentic Loop Pattern
```
call LLM → check for tool_calls → execute tools → feed results back → repeat until no tool_calls → extract final answer
```

- **S01E02**: local Python functions as tools
- **S01E03**: tools dispatched to an MCP server over SSE; `agent_server.py` converts MCP tool definitions to OpenAI format and executes via `session.call_tool(name, args)`
- **S01E05**: no fixed tools — LLM receives API response each iteration and decides the next JSON action to POST (`{"action": "...", "route": "..."}`)

### Tool Schema Convention
Tool definitions follow the OpenAI function-calling schema (`{"type": "function", "function": {...}}`). Each tool is defined as a module-level constant (e.g., `GET_LOCATION_TOOL`). See `s01e02/get_location.py` for a canonical example.

### Structured Output
S01E01 uses Pydantic models with `response_format={"type": "json_schema", ...}` for guaranteed JSON output from the LLM.

### Rate-Limit & Retry Handling
S01E05 demonstrates the production-ready retry pattern used for hub APIs:
- 503 → exponential backoff (`10s × attempt`, capped at 120s, max 30 retries)
- 429 → parse `Retry-After` / `X-RateLimit-Reset` headers
- Soft rate-limit signals in response body → detect and wait

## Key External APIs
| URL | Purpose |
|-----|---------|
| `https://llmrouter.gft.com/` | LLM inference (OpenAI-compatible) |
| `https://hub.ag3nts.org/verify` | Task answer submission |
| `https://hub.ag3nts.org/api/location` | Location lookup (s01e02) |
| `https://hub.ag3nts.org/api/accesslevel` | Access level lookup (s01e02) |
| `https://hub.ag3nts.org/api/packages` | Package management (s01e03 via MCP) |
