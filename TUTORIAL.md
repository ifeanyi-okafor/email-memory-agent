# Building Your First Multi-Agent System with MCP: The Email Memory Agent

## A Beginner-Friendly Python Tutorial

**What You'll Build:** A multi-agent AI system with a **web-based UI** that connects to your Gmail, reads your emails, builds a local memory vault of "you" using markdown files, and lets you query that memory through a chat interface in your browser.

**What You'll Learn:** Multi-agent systems, MCP (Model Context Protocol), Gmail OAuth, file-based memory systems, agent orchestration, FastAPI web backends, and SSE streaming.

**Prerequisites:** Python 3.10+, a Google account, an Anthropic API key, basic Python knowledge.

**Time to Complete:** 3-4 hours

---

## Table of Contents

1. [Understanding the Concepts](#part-1-understanding-the-concepts)
2. [Project Architecture](#part-2-project-architecture)
3. [Environment Setup](#part-3-environment-setup)
4. [Gmail OAuth Connection](#part-4-gmail-oauth-connection)
5. [The Memory Vault System](#part-5-the-memory-vault-system)
6. [Building the MCP Servers](#part-6-building-the-mcp-servers)
7. [Building the Agents](#part-7-building-the-agents)
8. [The Orchestrator](#part-8-the-orchestrator)
9. [The Web App](#part-9-the-web-app)
10. [Running the Full System](#part-10-running-the-full-system)
11. [Next Steps](#part-11-next-steps)

---

## Part 1: Understanding the Concepts

### Multi-Agent Systems

Think of a small company with specialists: an Email Reader fetches and parses emails, a Memory Writer creates structured files, and a Query Agent answers questions. Each has one job. The Orchestrator is the manager who routes work.

Why not one agent? Modularity (swap components), focused prompts (better results), debuggability (know which agent failed), and scalability (add agents without rewriting).

### MCP (Model Context Protocol)

MCP is an open standard (by Anthropic) defining how AI models connect to tools — like USB for AI. Tools are exposed as MCP servers. Any MCP client can discover and call them.

### The Memory Vault

Structured memories stored as markdown files in typed folders (decisions, preferences, people, topics, commitments, communication_style). Each file has YAML frontmatter and wiki-links. Human-readable, git-trackable, Obsidian-compatible.

---

## Part 2: Project Architecture

### System Diagram

```
  Browser (Web UI)  ←HTTP/SSE→  FastAPI Server  →  Orchestrator
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                              Email Reader      Memory Writer      Query Agent
                                    │                 │                 │
                                    ▼                 ▼                 ▼
                               Gmail API         vault/ files      vault/ files
```

### File Structure

```
email-memory-agent/
├── config/settings.py        # Configuration
├── tools/gmail_tools.py      # Gmail OAuth + email fetching
├── memory/vault.py           # Vault file operations
├── agents/
│   ├── base_agent.py         # Shared agentic loop
│   ├── email_reader.py       # Agent 1
│   ├── memory_writer.py      # Agent 2
│   └── query_agent.py        # Agent 3
├── orchestrator.py           # Routes requests to agents
├── mcp_servers/              # MCP protocol wrappers
├── web/
│   ├── app.py                # FastAPI backend
│   └── static/index.html     # Frontend
├── main.py                   # Entry point
└── vault/                    # Memory files (created at runtime)
```

### Key Decisions

| Choice | Why |
|--------|-----|
| **Claude Sonnet** | Created MCP, great at structured output |
| **FastAPI** | Async, auto-docs, SSE support |
| **Single HTML file** | Zero build tools needed |
| **SSE (not WebSockets)** | One-way stream is all we need |
| **Markdown files** | 74% effectiveness vs 68.5% for databases |
| **Text search** | Outperforms embeddings for LLM agents |

---

## Part 3: Environment Setup

```bash
mkdir email-memory-agent && cd email-memory-agent
python -m venv venv && source venv/bin/activate
mkdir -p config tools memory agents mcp_servers web/static
touch config/__init__.py tools/__init__.py memory/__init__.py agents/__init__.py mcp_servers/__init__.py web/__init__.py
```

Create `requirements.txt`, then `pip install -r requirements.txt`. Create `.env` with your `ANTHROPIC_API_KEY`. Set up Gmail OAuth credentials at Google Cloud Console and save as `config/credentials.json`.

See the project zip for the complete `requirements.txt` and `.env.example`.

---

## Part 4: Gmail OAuth Connection

We'll build `tools/gmail_tools.py` step by step. Every line is explained.

### Step 1: Imports

```python
import os, json, base64, pickle
from datetime import datetime, timedelta
from pathlib import Path
from email.utils import parseaddr
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
```

Each import has a job: `base64` decodes email bodies, `pickle` saves tokens to disk, `parseaddr` splits "Jane <jane@co.com>" into name and address, and the Google imports handle OAuth.

### Step 2: Constants and auth check

```python
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_PATH = Path('config/token.pickle')
CREDENTIALS_PATH = Path('config/credentials.json')

def is_authenticated():
    if not TOKEN_PATH.exists():
        return False
    try:
        with open(TOKEN_PATH, 'rb') as f:
            creds = pickle.load(f)
        return creds and (creds.valid or (creds.expired and creds.refresh_token))
    except Exception:
        return False
```

`SCOPES` ensures read-only access. `is_authenticated()` checks if a saved token exists and is usable — the web frontend calls this on page load.

### Step 3: Full authentication

```python
def get_gmail_service():
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())          # Silent refresh
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)   # Opens browser
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, 'wb') as f:
            pickle.dump(creds, f)

    return build('gmail', 'v1', credentials=creds)
```

Three scenarios: (a) valid token → use it, (b) expired token → refresh silently, (c) no token → open browser for consent. `run_local_server(port=0)` starts a tiny temp server, opens Google's consent page, and receives the callback.

### Step 4: Fetch emails

```python
def fetch_emails(max_results=50, query='', days_back=30):
    service = get_gmail_service()
    after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
    full_query = f'after:{after_date}'
    if query:
        full_query = f'{query} {full_query}'

    results = service.users().messages().list(userId='me', q=full_query, maxResults=max_results).execute()
    messages = results.get('messages', [])
    if not messages:
        return []

    emails = []
    for msg_ref in messages:
        try:
            msg = service.users().messages().get(userId='me', id=msg_ref['id'], format='full').execute()
            email_data = _parse_message(msg)
            if email_data:
                emails.append(email_data)
        except:
            continue
    return emails
```

Two-step process: get IDs first (fast), then fetch full content (slower). The `_parse_message` function flattens Gmail's nested format into a simple dictionary with subject, from, to, date, body, and labels. The `_extract_body` function handles plain text, HTML, and nested multipart emails using recursion.

See the complete commented file in `tools/gmail_tools.py`.

---

## Part 5: The Memory Vault System

We'll build `memory/vault.py` — the filing cabinet.

### Step 1: Setup and initialization

```python
import os, re, hashlib
from datetime import datetime
from pathlib import Path
import yaml

VAULT_ROOT = Path('vault')
MEMORY_TYPES = ['decisions', 'preferences', 'people', 'topics', 'commitments', 'communication_style']

def initialize_vault():
    for memory_type in MEMORY_TYPES:
        (VAULT_ROOT / memory_type).mkdir(parents=True, exist_ok=True)
    if not (VAULT_ROOT / '_index.md').exists():
        _write_initial_index()
    return str(VAULT_ROOT)
```

Creates six folders plus a master index file.

### Step 2: Safe filenames

```python
def _slugify(text):
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60]
    short_hash = hashlib.md5(text.encode()).hexdigest()[:4]
    return f"{slug}-{short_hash}"
```

"Prefers Morning Meetings" → "prefers-morning-meetings-a1b2". The hash ensures uniqueness.

### Step 3: Write memories

```python
def write_memory(title, memory_type, content, priority='🟡', tags=None, related_to=None, source_emails=None):
    slug = _slugify(title)
    filepath = VAULT_ROOT / memory_type / f"{slug}.md"

    frontmatter = {'title': title, 'date': datetime.now().strftime('%Y-%m-%d'),
                   'category': memory_type, 'priority': priority, 'tags': tags or [], 'related_to': related_to or []}
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    wiki_links = ''
    if related_to:
        wiki_links = '\n**Related:** ' + ', '.join([f'[[{e}]]' for e in related_to]) + '\n'

    filepath.write_text(f"---\n{yaml_str.strip()}\n---\n\n# {title}\n\n{wiki_links}\n{content}\n")
    update_index(str(filepath.relative_to(VAULT_ROOT)), memory_type, title)
    return str(filepath)
```

Each file gets YAML frontmatter + markdown content + wiki-links. The `update_index` call adds a row to `_index.md`.

### Step 4: Read, search, list, stats

```python
def read_memory(filepath):     # Split file into frontmatter dict + content string
def search_vault(query):       # Text search across all files, returns snippets
def list_memories(type=None):  # List all files with basic metadata
def get_vault_stats():         # Count files per category: {'total': 15, 'people': 4, ...}
```

`search_vault` uses simple text matching — finds the query in the file, extracts 100 characters of context around the match. Research shows this outperforms vector search for LLM agents.

See the complete commented file in `memory/vault.py`.

---

## Part 6: Building the MCP Servers

MCP servers wrap our tools in the standard protocol. Our agents call tools directly (simpler), but these show how to make them discoverable:

```python
# Pattern for both servers:
server = Server("server-name")

@server.list_tools()
async def list_tools():
    return [Tool(name="...", description="...", inputSchema={...})]

@server.call_tool()
async def call_tool(name, arguments):
    if name == "read_emails":
        return [TextContent(type="text", text=json.dumps(fetch_emails(**arguments)))]
```

`list_tools` advertises capabilities. `call_tool` executes them. See `mcp_servers/gmail_server.py` and `mcp_servers/memory_server.py`.

---

## Part 7: Building the Agents

### The Base Agent — the agentic loop

Every agent inherits from `BaseAgent` which implements the core loop:

```python
class BaseAgent:
    def __init__(self):
        self.system_prompt = "..."
        self.tools = []
        self.conversation_history = []

    def run(self, user_message, max_tool_rounds=10):
        self.conversation_history.append({"role": "user", "content": user_message})

        for round in range(max_tool_rounds):
            response = client.messages.create(
                model=MODEL, system=self.system_prompt,
                tools=self.tools, messages=self.conversation_history)

            if response.stop_reason == "tool_use":
                # Execute tools, send results back, loop again
                ...
            else:
                # Final answer — extract text and return
                return final_text
```

In plain English: send message → Claude responds → if Claude wants a tool, run it and send results back → repeat until Claude gives a final text answer.

### Agent 1: Email Reader

Inherits BaseAgent. System prompt says "fetch emails, analyze patterns, output JSON observations." One tool: `read_emails`. When `run()` is called, Claude calls `read_emails`, receives email data, and produces structured observations.

### Agent 2: Memory Writer

System prompt says "write observations as memory files, check for duplicates first." Four tools: `write_memory`, `search_vault`, `list_memories`, `get_vault_stats`. Claude searches before writing to avoid duplicates.

### Agent 3: Query Agent

System prompt says "answer questions using the vault, speak in second person." Five read-only tools. Claude reads the index, searches, reads full files, and synthesizes conversational answers.

See the complete commented files in `agents/`.

---

## Part 8: The Orchestrator

Routes requests to the right agent(s):

```python
class Orchestrator:
    def __init__(self):
        initialize_vault()
        self.email_reader = EmailReaderAgent()
        self.memory_writer = MemoryWriterAgent()
        self.query_agent = QueryAgent()

    def build_memory(self, user_input):
        reader_result = self.email_reader.run(user_input)      # Step 1
        writer_result = self.memory_writer.run(                  # Step 2
            f"Process these observations:\n{reader_result}")
        return writer_result

    def query_memory(self, user_input):
        return self.query_agent.run(user_input)
```

`build_memory` is a pipeline: Agent 1 output → Agent 2 input. See `orchestrator.py`.

---

## Part 9: The Web App

### Backend (`web/app.py`)

**Auth:** `GET /api/auth/status` checks token, `POST /api/auth/google` triggers OAuth flow in a background thread.

**SSE Build:** Pipeline runs in a thread, posts events to a queue, async generator yields SSE strings to the browser.

**Query:** `POST /api/query` runs the Query Agent via `run_in_executor`.

**Vault:** `GET /api/stats`, `GET /api/memories`, `GET /api/memory/{path}`, `GET /api/search`.

### Frontend (`web/static/index.html`)

Single HTML file with three tabs: Build (SSE log), Query (chat), Browse (vault explorer with modal). Uses `EventSource` for SSE, `fetch` for queries, CSS custom properties for theming.

### Entry Point (`main.py`)

Loads `.env`, validates API key, starts uvicorn: `uvicorn.run("web.app:app", host="127.0.0.1", port=8000)`.

---

## Part 10: Running the Full System

```bash
cd email-memory-agent
source venv/bin/activate
python main.py
# → Open http://localhost:8000
```

1. **Connect Gmail** — Click "Connect Gmail" in the banner → approve in browser → banner turns green
2. **Build Memory** — Set days/emails, click Build, watch live SSE log
3. **Query** — Chat tab: "What kind of person am I?" → Agent searches vault and answers
4. **Browse** — Stats cards, type filter, click cards to see full content in modal
5. **API Docs** — Visit http://localhost:8000/docs for interactive Swagger UI
6. **Obsidian** — Open `vault/` folder in Obsidian for graph view

---

## Part 11: Next Steps

- **Full MCP transport** — Connect agents via `mcp.ClientSession` instead of direct calls
- **More data sources** — Add Slack, Calendar, Document MCP servers
- **Embedding search** — Add ChromaDB for large vaults
- **Production** — Encrypted tokens, rate limiting, circuit breakers, async agents

---

## Glossary

| Term | Definition |
|------|-----------|
| **Agent** | An LLM with a role, prompt, and tools |
| **MCP** | Model Context Protocol — standard for AI↔tool communication |
| **Orchestrator** | Routes requests to agents |
| **Memory Vault** | Folder of typed markdown files |
| **Frontmatter** | YAML metadata between `---` markers |
| **Wiki-link** | `[[entity]]` syntax for connections |
| **Agentic Loop** | Think → tool → result → think again |
| **FastAPI** | Python web framework (our backend) |
| **SSE** | Server-Sent Events (live progress stream) |
| **OAuth** | Secure login delegation protocol |
| **Pipeline** | Agent 1 output → Agent 2 input |

---

*Built as a learning tutorial. Inspired by ClawVault's insight that markdown files outperform specialized databases for LLM memory.*
