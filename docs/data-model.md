# Data Model

## Memory Vault Files

Each memory is a markdown file with YAML frontmatter. Stored in `memory/vault/{type}/`.

### File Format

```yaml
---
title: "Memory Title"
type: "decisions|people|commitments|action_required"
date: "YYYY-MM-DD"
tags: ["tag1", "tag2"]
source: "email"
---

Markdown body with observations and context.

Related: [[other-memory-filename]]
```

### Memory Types

| Type | Folder | Example |
|------|--------|---------|
| `decisions` | `vault/decisions/` | "Chose React over Vue for frontend" |
| `people` | `vault/people/` | "Sarah Chen — CTO at Acme Corp" |
| `commitments` | `vault/commitments/` | "Review PRs by Friday" |
| `action_required` | `vault/action_required/` | "Follow up with Alice on contract review" |
| `insights` | `vault/insights/` | "Sarah and Mike both work on API platforms but aren't connected" |
| `organizations` | `vault/organizations/` | "Acme Corp — SaaS company, client relationship" |
| `projects` | `vault/projects/` | "Project Atlas — active internal product initiative" |

### Universal Fields

All memory types share a common set of fields in their YAML frontmatter:

| Field | Type | Values | Notes |
| ----- | ---- | ------ | ----- |
| `status` | string | type-specific (see below) | Current lifecycle state of the memory |
| `status_reason` | string | free text | Explanation for the most recent status change |
| `status_updated` | date | ISO date (`YYYY-MM-DD`) | Date of last status change |
| `confidence` | string | `high` / `medium` / `low` | Strength of evidence supporting this memory |
| `tags` | list | string list | Topic tags |
| `related_to` | list | name/title list | Entities this memory links to (drives knowledge graph edges) |
| `source_emails` | list | email subject strings | Source emails that generated or updated this memory |

`status` values by type:

| Type | Status values |
| ---- | ------------ |
| `people` | `active`, `left-org`, `inactive`, `unknown` |
| `decisions` | `active`, `reversed`, `superseded`, `archived` |
| `commitments` | `invited`, `confirmed`, `declined`, `tentative`, `completed`, `cancelled` |
| `action_required` | `active`, `closed`, `expired` |
| `insights` | `active`, `dismissed` |
| `organizations` | `active`, `inactive`, `dissolved` |
| `projects` | `active`, `paused`, `completed`, `cancelled` |

`confidence` is scored by the Email Reader based on corroboration, recency, and evidence type, then propagated by the Memory Writer into frontmatter. Insights had this field first; all other types share it as of Priority 4–5.

### Commitment Frontmatter

`commitments` files include a participation lifecycle field:

```yaml
---
title: "Austin Meetup Moderation — Feb 21"
type: "commitments"
date: "2026-02-24"
priority: "🔴"
commitment_status: "confirmed"
tags: ["meetup", "austin"]
related_to: ["Austin Coding Meetup"]
source_emails: ["Re: Meetup Moderation Invite"]
---
```

Commitment status values:

| Status | Meaning |
| ------ | ------- |
| `invited` | Received invitation/notification, no evidence of acceptance (default) |
| `confirmed` | User RSVP'd, registered, replied "yes", or explicitly accepted |
| `declined` | User explicitly declined, cancelled, or opted out |
| `tentative` | User expressed interest but hasn't confirmed |

### Organization Frontmatter

`organizations` files include type-specific fields for tracking company relationships:

```yaml
---
title: "Acme Corp"
type: "organizations"
date: "2026-04-11"
domain: "acme.com"
industry: "SaaS"
relationship_type: "client"
tags: ["saas", "client"]
related_to: ["Sarah Chen", "contract-review"]
source: "email"
---
```

`relationship_type` values: `client`, `vendor`, `partner`, `employer`, `investor`, or any free-form label.

### Project Frontmatter

`projects` files include type-specific fields for tracking initiatives:

```yaml
---
title: "Project Atlas"
type: "projects"
date: "2026-04-11"
project_status: "active"
project_type: "internal"
tags: ["product", "q2-initiative"]
related_to: ["Sarah Chen", "Acme Corp"]
source: "email"
---
```

`project_status` values: `active`, `paused`, `completed`, `cancelled`

`project_type` values: `internal`, `client`, `open-source`, or any free-form label.

### Insights Frontmatter

`insights` files represent cross-correlation intelligence derived from vault analysis:

```yaml
---
title: "Sarah and Mike both work on API platforms"
date: "2026-03-07"
category: insights
memoryType: insights
priority: "🟡"
insight_type: "relationship"
confidence: "high"
status: "active"
source_memories:
  - people/sarah-chen-a1b2.md
  - people/mike-torres-c3d4.md
tags: ["api", "networking"]
related_to: ["Sarah Chen", "Mike Torres"]
---
```

Insight type values:

| Type | Meaning |
| ---- | ------- |
| `relationship` | Hidden connections between people, organizations, or topics |
| `execution_gap` | Commitments or action items that are stalled or overdue |
| `strategic_pattern` | Recurring themes, priority imbalances, or behavioral patterns |

Insight status values:

| Status | Meaning |
| ------ | ------- |
| `active` | Insight is current and relevant (default) |
| `dismissed` | User dismissed the insight via chat or UI |

Confidence values: `high`, `medium`, `low`

### Action Required Frontmatter

`action_required` files include additional Eisenhower classification fields:

```yaml
---
title: "Follow up with Alice on contract review"
type: "action_required"
date: "2026-02-23"
quadrant: "urgent-important"
priority_justification: "Contract deadline is next week and Alice is waiting"
deadline: "2026-03-01"
source_type: "commitment"
source_memories: ["commitments/contract-review-a1b2.md"]
source_emails: ["Re: Contract Review - Alice"]
tags: ["contract", "legal"]
related_to: ["Alice Johnson", "contract-review"]
---
```

Quadrant values: `urgent-important`, `important-not-urgent`, `urgent-not-important`, `neither`

### Action Required Status Fields

Status tracking fields are managed by the Reconciliation Agent:

```yaml
status: active              # active | closed | expired
status_reason: ""           # e.g., "Sent email to Jake about timeline on 2026-02-22"
status_updated: 2026-02-23  # ISO date of last status change
```

- **active** — default when field is absent (backward-compatible)
- **closed** — sent email matched via heuristic or LLM analysis
- **expired** — deadline passed with no matching sent email

### File Naming

Files are named with a slug derived from the title plus a short hash:
`sarah-chen-a1b2.md`

## Knowledge Graph (`_graph.json`)

Bidirectional adjacency map rebuilt on every `write_memory()` call. Stored at `vault/_graph.json`.

```json
{
  "nodes": {
    "people/alice-johnson-a1b2.md": {
      "title": "Alice Johnson — Legal Counsel",
      "type": "people",
      "tags": ["legal", "contracts"]
    }
  },
  "edges": {
    "people/alice-johnson-a1b2.md": [
      {"target": "commitments/contract-review-c3d4.md", "relation": "related_to"},
      {"target": "action_required/follow-up-alice-e5f6.md", "relation": "referenced_by"}
    ]
  }
}
```

Edge types: `related_to` (from frontmatter), `backlink` / `referenced_by` (auto-generated inverse), `source_memory` (provenance from action items).

Graph logic lives in `memory/graph.py`. Backlinks are auto-injected into file frontmatter `related_to` arrays.

## Vault Git History

The vault directory is its own standalone git repository, giving every vault state a recoverable snapshot. Logic lives in `memory/git_history.py` (subprocess wrapper — no GitPython dependency).

Auto-commit points in the build pipeline:

| Stage | Commit message |
| ----- | -------------- |
| After Memory Writer writes vault files | `chore: memory write — <timestamp>` |
| After graph rebuild | `chore: graph rebuild — <timestamp>` |
| After Action Agent | `chore: action agent — <timestamp>` |
| After Reconciliation Agent | `chore: reconciliation — <timestamp>` |
| After Insights Agent | `chore: insights — <timestamp>` |

On first run, `git_history.py` initialises the vault as a git repo (`git init`) if one does not already exist. Each auto-commit stages all vault files (`git add -A`) and creates a commit with a timestamped message. The commit history provides a full audit trail of vault evolution across pipeline runs.

## Processed Email Tracking

| File | Format | Purpose |
|------|--------|---------|
| `vault/_processed_emails.json` | JSON array of Gmail message IDs | Prevents re-processing emails |

```json
["msg_id_1", "msg_id_2", "msg_id_3"]
```

Loaded into a Python `set` for O(1) lookup during filtering.

## Vault Changelog (`_changelog.md`)

Append-only audit log of all vault mutations. Every `write_memory()` call appends a timestamped row. Logic in `memory/changelog.py`.

| File | Format | Purpose |
|------|--------|---------|
| `vault/_changelog.md` | Markdown table | Records every vault create/update/merge |

```markdown
| Timestamp | Action | File | Description |
|-----------|--------|------|-------------|
| 2026-04-11 14:30:00 | CREATED | people/sarah-chen-a1b2.md | Sarah Chen |
| 2026-04-11 14:30:01 | UPDATED | people/sarah-chen-a1b2.md | Sarah Chen |
| 2026-04-11 14:30:02 | MERGED | people/sarah-chen-a1b2.md | Sarah Chen |
```

Action values: `CREATED`, `UPDATED`, `MERGED`

## Knowledge Index (runtime, not persisted)

Built by `memory/knowledge_index.py` before each MemoryWriter run. Not stored on disk — generated on demand and injected into the agent's prompt.

Produces a markdown string with one table per memory type:

```markdown
# Knowledge Index

## People
| File | Name | Email | Organization | Role | Confidence |
|------|------|-------|--------------|------|------------|
| people/me.md | John Doe | john@example.com | TechCorp | PM | high |
| people/sarah-chen-a1b2.md | Sarah Chen | sarah@acme.com | Acme Corp | VP Engineering | medium |

## Decisions
| File | Title | Date | Tags |
|------|-------|------|------|
| decisions/chose-react-a1b2.md | Chose React for Frontend | 2026-02-20 | engineering, frontend |

## Commitments
| File | Title | Status | Date |
...
```

Purpose: gives the MemoryWriter a compact view of all existing entities so it can resolve names/titles against what already exists instead of creating duplicates.

## Change Detection (`_file_state.json`)

Tracks SHA-256 hashes of vault files to detect changes between runs. Logic in `memory/change_detection.py`.

| File                      | Format                        | Purpose                                        |
|---------------------------|-------------------------------|------------------------------------------------|
| `vault/_file_state.json`  | JSON object (filepath → hash) | Records last-known hash for every vault file   |

```json
{
  "people/sarah-chen-a1b2.md": "e3b0c44298fc1c149afb...",
  "decisions/chose-react-a1b2.md": "a87ff679a2f3e71d9181..."
}
```

On each run, `change_detection.py` computes fresh hashes, compares against the stored state, and returns a set of changed/added/removed file paths. The state file is updated after processing.

## Scheduler Config and State

The background task scheduler (`memory/scheduler.py`) is driven by a JSON config file and persists run state separately.

| File                                 | Format                                    | Purpose                                                           |
|--------------------------------------|-------------------------------------------|-------------------------------------------------------------------|
| `config/scheduled_tasks.json`        | JSON array of task definitions            | User-defined schedule (copy from `scheduled_tasks.example.json`)  |
| `config/scheduled_tasks_state.json`  | JSON object (task id → last run timestamp)| Persists last-run time across process restarts                    |

Example config (`config/scheduled_tasks.example.json`):

```json
[
  {
    "id": "daily-build",
    "task": "build",
    "schedule": "0 8 * * *",
    "enabled": true
  }
]
```

Tasks are executed by running `python main.py --run-scheduled`. The scheduler checks each enabled task against the current time and its last-run state, then fires any that are due.

## Session Storage (Frontend)

Conversations are saved in `sessionStorage` (browser-only, cleared on tab close):

| Key | Format | Purpose |
|-----|--------|---------|
| `mv_conversations` | JSON array | All conversation metadata |
| `mv_messages_{id}` | JSON array | Messages for a specific conversation |
| `mv_activeConversation` | String (ID) | Currently active conversation |
