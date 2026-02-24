# Agentic Architecture

## Agent Inventory

| Agent | File | Role | Trigger |
|-------|------|------|---------|
| Email Reader | `agents/email_reader.py` | Fetches emails from Gmail and produces structured JSON observations about the user (including `commitment_status` for commitments) | Build pipeline step 2 |
| Memory Writer | `agents/memory_writer.py` | Converts observations into structured vault files (YAML frontmatter + markdown). Sets `commitment_status` for commitment files. | Build pipeline step 3 |
| Query Agent | `agents/query_agent.py` | Searches the vault and answers user questions conversationally | Any non-keyword chat message |
| Action Agent | `agents/action_agent.py` | Scans vault + knowledge graph, creates Eisenhower-prioritized action items | Build pipeline step 4, or "refresh" keyword |
| Reconciliation Agent | `agents/reconciliation_agent.py` | Compares action items against sent emails, updates status (active/closed/expired) | Build pipeline step 5, or "reconcile" keyword |

## Agent Tools

```mermaid
graph LR
    subgraph "Email Reader"
        ER_T1[read_emails]
    end

    subgraph "Memory Writer"
        MW_T1[write_memory]
        MW_T2[read_memory]
        MW_T3[search_vault]
        MW_T4[list_memories]
        MW_T5[get_vault_stats]
    end

    subgraph "Query Agent"
        QA_T1[get_vault_index]
        QA_T2[search_vault]
        QA_T3[read_memory]
        QA_T4[list_memories]
        QA_T5[get_vault_stats]
        QA_T6[get_graph]
        QA_T7[traverse_graph]
    end

    subgraph "Action Agent"
        AA_T1[get_vault_index]
        AA_T2[search_vault]
        AA_T3[read_memory]
        AA_T4[list_memories]
        AA_T5[get_graph]
        AA_T6[traverse_graph]
        AA_T7[write_memory]
        AA_T8[get_vault_stats]
    end

    subgraph "Reconciliation Agent"
        RA_T1[search_vault]
        RA_T2[read_memory]
        RA_T3[list_memories]
        RA_T4[write_memory]
        RA_T5[fetch_sent_emails]
    end
```

## Tool Permission Matrix

Each agent receives only the tools it needs — **no agent has universal access**. This matrix shows exactly which tools each agent can call:

| Tool | EmailReader | MemoryWriter | QueryAgent | ActionAgent | ReconciliationAgent |
| ---- | :-: | :-: | :-: | :-: | :-: |
| `read_emails` | **R** | | | | |
| `fetch_sent_emails` | | | | | **R** |
| `write_memory` | | **W** | | **W** | **W** |
| `read_memory` | | **R** | **R** | **R** | **R** |
| `search_vault` | | **R** | **R** | **R** | **R** |
| `list_memories` | | **R** | **R** | **R** | **R** |
| `get_vault_index` | | | **R** | **R** | |
| `get_vault_stats` | | **R** | **R** | | |
| `get_graph` | | | **R** | **R** | |
| `traverse_graph` | | | **R** | **R** | |

**R** = read-only, **W** = write

Key observations:

- **QueryAgent is strictly read-only** — it cannot modify the vault
- **EmailReader only talks to Gmail** — no vault tools at all
- **ReconciliationAgent is the only agent with `fetch_sent_emails`** — sent mail access is tightly scoped
- Vault read tools (`search_vault`, `read_memory`, `list_memories`) are the closest to "universal" — 4 of 5 agents have them

## Orchestration Flow

```mermaid
flowchart TD
    USER[User message] --> ORCH[Orchestrator.route]
    ORCH -->|"build, scan, ingest"| BUILD[Build Pipeline]
    ORCH -->|"refresh, prioritize"| REFRESH[Action Agent]
    ORCH -->|"reconcile, check actions"| RECONCILE[Reconciliation Agent]
    ORCH -->|"deduplicate, clean vault"| DEDUP[Dedup Cleanup]
    ORCH -->|"stats, how many"| STATS[Vault Stats]
    ORCH -->|anything else| QUERY[Query Agent]

    BUILD --> B1[Step 1: Fetch emails via Gmail API]
    B1 --> B2[Step 2: Email Reader Agent - batch analyze]
    B2 --> B3[Step 3: Memory Writer Agent - create vault files]
    B3 --> B4[Step 3.5: Rebuild knowledge graph]
    B4 --> B5[Step 4: Action Agent - generate action items]
    B5 --> B6[Step 5: Reconciliation Agent - update statuses]
    B6 --> DONE[Complete]
```

## Build Pipeline Sequence

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant OR as Orchestrator
    participant ER as EmailReaderAgent
    participant MW as MemoryWriterAgent
    participant AA as ActionAgent
    participant RA as ReconciliationAgent
    participant Gmail as Gmail API
    participant Vault as Memory Vault

    FE->>API: GET /api/stream/build (SSE)
    API->>OR: build_memory()

    OR->>Gmail: fetch_emails()
    Gmail-->>OR: emails[]
    OR->>OR: Filter already-processed IDs

    loop Each batch of 10 emails
        OR->>ER: analyze_batch(batch_json)
        ER-->>OR: JSON observations
    end

    OR->>MW: run(combined_observations)
    MW->>Vault: write_memory() per observation
    Vault-->>MW: file paths

    OR->>Vault: rebuild_graph()

    OR->>AA: run("Generate action items")
    AA->>Vault: read vault + graph
    AA->>Vault: write_memory(action_required)

    OR->>RA: run("Reconcile actions")
    RA->>Gmail: fetch_sent_emails()
    RA->>Vault: read action items
    RA->>Vault: write_memory(updated status)

    OR-->>API: complete event
    API-->>FE: SSE: stage=complete
```

## Base Agent (Agentic Loop)

All agents inherit from `BaseAgent` (`agents/base_agent.py`), which provides:

```mermaid
flowchart TD
    START[run prompt] --> CALL[Call LLM with system prompt + tools]
    CALL --> CHECK{Response has tool_use?}
    CHECK -->|Yes| EXEC[Execute tool via execute_tool]
    EXEC --> APPEND[Append tool result to conversation]
    APPEND --> CALL
    CHECK -->|No| RETURN[Return text response]
```

- **LLM provider adapter**: OpenRouter (primary, OpenAI SDK format) with automatic Anthropic fallback
- **Retry logic**: 8 retries with exponential backoff (base 2s) on 429/529 errors
- **Tool-call handling**: Loops until the LLM returns a text response (no more tool calls)
- **Format conversion**: Automatically converts between OpenAI and Anthropic message/tool formats

## Agent Data Flow

Agents share **no state**. Data flows as text between pipeline stages:

```mermaid
flowchart LR
    ER[Email Reader] -->|"JSON observations text"| MW[Memory Writer]
    MW -->|"vault files on disk"| AA[Action Agent]
    AA -->|"vault files on disk"| RA[Reconciliation Agent]
```

- Email Reader output is a raw JSON string passed as a prompt to Memory Writer
- Memory Writer writes files to disk; Action Agent reads them via vault tools
- Reconciliation Agent reads action items from vault and sent emails from Gmail

## MCP Server Mapping

| MCP Server | File | Exposed Tools | Used By |
|------------|------|---------------|---------|
| Gmail MCP | `mcp_servers/gmail_server.py` | `read_emails`, `fetch_sent_emails` | Email Reader, Reconciliation Agent |
| Memory MCP | `mcp_servers/memory_server.py` | `write_memory`, `read_memory`, `search_vault`, `list_memories`, `get_vault_index`, `get_vault_stats`, `get_graph`, `traverse_graph` | Memory Writer, Query Agent, Action Agent, Reconciliation Agent |

## Key Design Decisions

- **No shared state**: Agents communicate via text output, not shared memory. This makes them independently testable and replaceable.
- **Keyword routing**: The orchestrator uses simple string matching (not LLM-based intent classification) for routing. Fast and deterministic.
- **Batch analysis**: Emails are split into batches of 10 for the Email Reader. Each batch gets a fresh agent context to stay within token limits.
- **Incremental processing**: Processed email IDs are tracked in `_processed_emails.json`. Subsequent builds skip already-processed emails.
- **Programmatic dedup**: `memory/dedup.py` runs inside `write_memory()` as a pre-write safety net, catching duplicates the LLM misses.
