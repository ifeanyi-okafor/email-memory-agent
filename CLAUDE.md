# Email Memory Agent

A **multi-agent AI system** that connects to Gmail, reads emails, builds a local memory vault of structured markdown files about you, and lets you query that memory through a browser chat interface.

Built as a tutorial project to teach: multi-agent systems, MCP (Model Context Protocol), Gmail OAuth, file-based memory, agent orchestration, FastAPI, and SSE streaming.

---

## Architecture

```
Browser (index.html)
    │  HTTP + SSE
    ▼
FastAPI Server (web/app.py)
    │
    ▼
Orchestrator (orchestrator.py)   ← keyword-routes requests
    │
    ├── EmailReaderAgent    → reads gmail via GmailMCPServer
    │        │                    (gmail_server.py)
    │        ▼
    ├── MemoryWriterAgent   → writes vault via MemoryMCPServer
    │                            (memory_server.py)
    │
    ├── ActionAgent         → scans vault + graph, writes action_required
    │                            files via MemoryMCPServer + graph tools
    │
    └── QueryAgent          → searches vault via MemoryMCPServer
                                 (memory_server.py)

Memory Vault (vault/)
  decisions/ people/ commitments/ action_required/
  _graph.json (knowledge graph — bidirectional adjacency map)
  Each file: YAML frontmatter + markdown body + [[wiki-links]]
```

---

## Key Files

| File | Role |
|------|------|
| `main.py` | Entry point — starts uvicorn on port 8000 |
| `orchestrator.py` | Routes build/query/stats requests to agents |
| `agents/base_agent.py` | Base class: agentic loop, tool-call handling |
| `agents/email_reader.py` | Agent 1: fetches & analyzes emails |
| `agents/memory_writer.py` | Agent 2: writes structured memory files |
| `agents/query_agent.py` | Agent 3: searches vault & answers questions |
| `agents/action_agent.py` | Agent 4: generates Eisenhower-prioritized action items |
| `mcp_servers/gmail_server.py` | MCP server exposing Gmail API as tools |
| `mcp_servers/memory_server.py` | MCP server exposing vault read/write + graph tools |
| `memory/vault.py` | Vault helpers: init, search, stats, read/write |
| `memory/graph.py` | Knowledge graph: build, traverse, backlink injection |
| `config/settings.py` | Central config: vault path, Claude model, Gmail scopes |
| `web/app.py` | FastAPI backend with SSE streaming endpoint |
| `web/static/index.html` | Browser chat UI |
| `.env` | Secrets (not committed) — see `.env.example` |

---

## Running the Project

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy .env.example → .env and fill in your API key
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=sk-ant-...

# 3. Set up Gmail OAuth (one-time) — see TUTORIAL.md Part 4

# 4. Start the server
python main.py

# 5. Open http://localhost:8000 in your browser
```

Custom port/host:
```bash
python main.py --port 3000
python main.py --host 0.0.0.0  # network access
```

---

## Environment Variables

See `.env.example` for all variables. Required:

- `ANTHROPIC_API_KEY` — Claude API key (required, app exits if missing)
- Gmail OAuth credentials — `client_id`, `client_secret`, `token` path

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude (`anthropic` SDK) |
| Tool Protocol | MCP (`mcp` SDK) |
| Gmail | Google API Python Client + OAuth2 |
| Web framework | FastAPI + uvicorn |
| Streaming | Server-Sent Events (SSE) |
| Memory storage | File-based markdown vault |
| Terminal output | `rich` |
| Config | `python-dotenv` + `pyyaml` |

---

## Key Patterns & Gotchas

- **Agent data flow**: Agents share no state. Output of `EmailReaderAgent` is passed as a text prompt to `MemoryWriterAgent`.
- **MCP tools**: Each agent gets tool definitions from an MCP server. Tool calls are handled in `base_agent.py`'s agentic loop.
- **Memory file format**: YAML frontmatter + markdown body + `[[wiki-links]]`. Never break this format — the vault parser depends on it.
- **Orchestrator routing**: Keyword matching (`build`/`scan` → build pipeline, `refresh`/`prioritize`/`actions` → action refresh, `stats` → stats, else → query). Intent logic lives in `orchestrator.py:route()`.
- **Knowledge graph**: `_graph.json` is a bidirectional adjacency map rebuilt after every `write_memory()`. Backlinks are injected into file frontmatter. Graph logic lives in `memory/graph.py`.
- **Action Required**: Uses Eisenhower matrix (`urgent-important`, `important-not-urgent`, `urgent-not-important`, `neither`). ActionAgent reads the full vault + graph to generate justified action items.
- **NEVER commit**: `token.json`, `.env`, any OAuth credentials. These are user secrets.
- **Vault location**: Configured in `config/settings.py`. Defaults to `memory/vault/` relative to project root.

---

## Agent Descriptions

| Agent | Trigger | What it does |
|-------|---------|--------------|
| `EmailReaderAgent` | User says "build", "scan", "read emails" | Calls `read_emails` MCP tool, produces JSON observations |
| `MemoryWriterAgent` | After EmailReader (pipeline) | Calls `write_memory` + `search_vault` MCP tools |
| `ActionAgent` | After build (auto) or "refresh"/"prioritize" | Reads full vault + graph, creates Eisenhower-classified action items |
| `QueryAgent` | Any other message | Calls `search_vault` + `read_memory` + graph tools, synthesizes answer |
