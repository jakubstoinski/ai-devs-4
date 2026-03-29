# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI-devs 4: Builders** — a practical training course on building production AI agent applications. Each episode (s01eXX) is a self-contained task that builds on previous results and submits answers to a central verification hub at `hub.ag3nts.org`.

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

### S01E03 (requires two terminals)
```bash
# Terminal 1 — MCP server
cd common && python mcp_server.py        # port 5624 SSE

# Terminal 2 — Agent server
cd s01e03 && python agent_server.py      # port 3000

# Terminal 3 — Register with hub
cd s01e03 && python register_agent.py
```

## Architecture

### Common Utilities (`common/`)
- **`llm_client.py`** — Returns an `OpenAI`-compatible client pointing to `https://llmrouter.gft.com/` using `LLM_ROUTER_TOKEN`. Use this instead of instantiating OpenAI directly.
- **`central_client.py`** — `send_to_central(task, answer)` POSTs answers to `hub.ag3nts.org/verify`. Every episode ends by calling this.
- **`mcp_server.py`** — FastMCP server exposing package tools (`check_package`, `redirect_package`) on SSE at port 5624. Used by s01e03.
- **`llm_models.md`** — Reference list of models available through the LLM router.

### Episode Pattern
Each episode follows this progression:
1. Fetch or read input data
2. Run an agentic loop (LLM + optional tools)
3. Submit the answer via `send_to_central()`

### Agentic Loop Pattern (S01E02, S01E03)
```
call LLM → check for tool_calls → execute tools → feed results back → repeat until no tool_calls → extract final answer
```

S01E03 externalizes tool execution to an MCP server. The `agent_server.py` connects to `common/mcp_server.py` via SSE and dispatches tool calls there.

### Tool Schema Convention
Tool definitions follow the OpenAI function-calling schema. See `s01e02/get_location.py` and `s01e02/get_access_level.py` for canonical examples.

## Key External APIs
| URL | Purpose |
|-----|---------|
| `https://llmrouter.gft.com/` | LLM inference (OpenAI-compatible) |
| `https://hub.ag3nts.org/verify` | Task answer submission |
| `https://hub.ag3nts.org/api/location` | Location lookup (used in s01e02) |
| `https://hub.ag3nts.org/api/accesslevel` | Access level lookup (used in s01e02) |
| `https://hub.ag3nts.org/api/packages` | Package management (used via MCP in s01e03) |