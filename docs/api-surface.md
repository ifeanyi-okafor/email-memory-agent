# API Surface

## Internal Endpoints (web/app.py)

All endpoints served by FastAPI on `http://localhost:8000`.

### Auth

| Method | Path | Auth? | Description | Request | Response |
|--------|------|-------|-------------|---------|----------|
| GET | `/api/auth/status` | No | Check Gmail auth state | — | `{authenticated: bool, credentials_exist: bool}` |
| POST | `/api/auth/google` | No | Trigger OAuth flow | — | `{status, message}` |
| POST | `/api/auth/logout` | No | Delete OAuth token | — | `{status, message}` |
| GET | `/api/auth/user-info` | Yes | Get Gmail profile | — | `{email, authenticated}` |

### Build Pipeline

| Method | Path | Auth? | Description | Request | Response |
|--------|------|-------|-------------|---------|----------|
| GET | `/api/stream/build` | Yes | Run email→memory pipeline | Query: `days_back`, `max_emails`, `gmail_query` | SSE stream |
| GET | `/api/stream/refresh` | No | Run Action Agent (standalone) | — | SSE stream |

SSE event shape (build):
```json
{"stage": "fetching|email_reader|memory_writer|graph_rebuild|action_agent|reconciliation|complete|error", "status": "started|in_progress|complete|error", "message": "...", "stats": {...}}
```

SSE event shape (refresh):
```json
{"stage": "action_agent|complete|error", "status": "started|in_progress|complete|error", "message": "..."}
```

### Query

| Method | Path | Auth? | Description | Request | Response |
|--------|------|-------|-------------|---------|----------|
| POST | `/api/query` | No | Ask question about vault | `{question: string}` | `{answer: string}` |

### Orchestrator Keywords (via `/api/query`)

Certain keywords in the question trigger pipeline actions instead of Q&A:

| Keywords | Action |
|----------|--------|
| `build`, `scan`, `read email`, `fetch email`, `process email`, `analyze email`, `ingest` | Build pipeline |
| `refresh`, `prioritize`, `actions`, `action items`, `what needs attention`, `priorities` | Action Agent refresh |
| `reconcile`, `update actions`, `action status`, `check actions` | Reconciliation Agent |
| `deduplicate`, `dedup`, `clean vault`, `fix duplicates` | Vault deduplication cleanup |
| `stats`, `statistics`, `how many`, `vault info` | Vault statistics |

### Vault Browsing

| Method | Path | Auth? | Description | Request | Response |
|--------|------|-------|-------------|---------|----------|
| GET | `/api/stats` | No | Memory counts per type | — | `{total, by_type: {...}}` |
| GET | `/api/memories` | No | List all memories | Query: `memory_type` (opt) | `{memories: [...], count}` |
| GET | `/api/memory/{type}/{file}` | No | Read one memory file | — | `{frontmatter, content, filepath}` |
| GET | `/api/search` | No | Search memories by text | Query: `q` | `{results: [...], count}` |

### Static

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve index.html |
| GET | `/static/*` | Static files (CSS/JS/images) |

## External APIs Consumed

### Gmail API (via google-api-python-client)

| API | Scope | Rate Limit | Retry Policy |
|-----|-------|------------|--------------|
| `users().messages().list()` | `gmail.readonly` | 250 quota units/sec | Exponential backoff |
| `users().messages().get()` | `gmail.readonly` | 250 quota units/sec | Exponential backoff |
| `users().getProfile()` | `gmail.readonly` | 250 quota units/sec | None |

### Anthropic Claude API

| Model | Max Tokens | Retry Policy |
|-------|-----------|--------------|
| `claude-sonnet-4-20250514` | 4096 | 8 retries, base 2s exponential backoff |
