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

## Processed Email Tracking

| File | Format | Purpose |
|------|--------|---------|
| `vault/_processed_emails.json` | JSON array of Gmail message IDs | Prevents re-processing emails |

```json
["msg_id_1", "msg_id_2", "msg_id_3"]
```

Loaded into a Python `set` for O(1) lookup during filtering.

## Session Storage (Frontend)

Conversations are saved in `sessionStorage` (browser-only, cleared on tab close):

| Key | Format | Purpose |
|-----|--------|---------|
| `mv_conversations` | JSON array | All conversation metadata |
| `mv_messages_{id}` | JSON array | Messages for a specific conversation |
| `mv_activeConversation` | String (ID) | Currently active conversation |
