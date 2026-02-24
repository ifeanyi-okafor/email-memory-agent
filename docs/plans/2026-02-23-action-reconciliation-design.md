# Action Required Vault Tab + Status Reconciliation — Design

## Goal

Add the `action_required` memory type to the vault browser UI with status tracking (Active/Closed/Expired), and build a reconciliation system that compares open action items against sent Gmail messages to determine which actions have been addressed.

## Architecture

A new `ReconciliationAgent` performs hybrid matching: heuristic first (subject/recipient overlap), then LLM for ambiguous items. It runs automatically as the final build pipeline step and can be triggered manually via chat. Status updates are written back to action item frontmatter.

## Components

### 1. Vault UI — Action Required Tab

Add a 4th button to the vault type column in `index.html`:
- Icon: `fa-solid fa-bolt`
- Label: "Action Required"
- Wired to existing `selectVaultType('action_required', this)`

The existing `loadVaultData()`, `renderVaultItems()`, and `loadVaultContent()` work generically — no changes needed for basic display.

**Status badges** in item list (column 2):
- **Active** — green dot/badge (default when no status field)
- **Closed** — gray badge
- **Expired** — light orange badge

**Filter toggles** at top of column 2 (visible only for action_required type):
- `All | Active | Closed | Expired`
- Clicking one filters the item list
- Default: All

**Content viewer** (column 3) — display additional frontmatter fields:
- `quadrant` (Eisenhower matrix)
- `deadline`
- `status` + `status_reason`

### 2. Reconciliation Agent

New file: `agents/reconciliation_agent.py` — inherits from `BaseAgent`.

**Tools** (from existing MCP servers):
- `search_vault` — find action_required items with status=active
- `read_memory` — read full action item content
- `write_memory` — update status fields in frontmatter

**New Gmail MCP tool**: `fetch_sent_emails` — wraps existing `fetch_emails()` with `in:sent` query. Separate tool name for prompt clarity.

**Reconciliation flow (hybrid matching)**:
1. Load all action_required memories where status is active (or missing)
2. Fetch sent emails from the same time window
3. Heuristic pass: match by subject overlap with `source_emails` or recipient overlap with `related_to`
4. LLM pass: send remaining unresolved items + sent emails for analysis
5. Expiry check: if `deadline` is set and past → mark expired
6. Write updates: call `write_memory` for each changed item

### 3. Frontmatter Status Fields

Added to action_required memory files:
```yaml
status: active              # active | closed | expired
status_reason: ""           # e.g., "Replied to Jake on 2026-02-21"
status_updated: 2026-02-23  # ISO date of last status change
```

Default status is `active` when field is absent (backward-compatible).

### 4. Orchestrator Integration

- **Build pipeline**: New Step 5 after Action Agent (Step 4) — run reconciliation
- **Manual route**: Keywords `reconcile`, `update actions`, `action status` trigger reconciliation
- **SSE progress events**: Emit progress for reconciliation step

### 5. Gmail MCP — fetch_sent_emails Tool

Added to `mcp_servers/gmail_server.py`. Calls existing `fetch_emails()` from `tools/gmail_tools.py` with `query="in:sent"`. No scope change needed — `gmail.readonly` can already read sent mail.

## Testing

**Frontend tests** (JSDOM):
- action_required tab button exists with correct data-type
- Status badge rendering (green/gray/light orange)
- Filter toggles show/hide items by status
- Content viewer displays quadrant, deadline, status fields

**Reconciliation agent tests** (`tests/test_reconciliation.py`):
- Heuristic matching: subject overlap → closed
- Heuristic matching: recipient overlap → closed
- Expiry: past deadline → expired
- No change: no matching sent emails → stays active
- LLM fallback: unmatched items sent for analysis

**Integration tests**:
- Build pipeline runs reconciliation after action agent
- Manual "reconcile" command triggers reconciliation
- `write_memory` updates status fields without destroying content

## Files Changed

| File | Change |
|------|--------|
| `web/static/index.html` | 4th vault tab, status badges, filter toggles, content viewer fields |
| `agents/reconciliation_agent.py` | **New** — hybrid matching agent |
| `mcp_servers/gmail_server.py` | New `fetch_sent_emails` tool |
| `orchestrator.py` | Step 5 reconciliation, new keyword route |
| `memory/vault.py` | Support status/status_reason/status_updated in write_memory |
| `tests/test_reconciliation.py` | **New** — agent + heuristic tests |
| `tests/test_frontend.py` | New tests for action_required tab |
