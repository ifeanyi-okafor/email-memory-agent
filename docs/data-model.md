# Data Model

## Memory Vault Files

Each memory is a markdown file with YAML frontmatter. Stored in `memory/vault/{type}/`.

### File Format

```yaml
---
title: "Memory Title"
type: "decisions|people|commitments"
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

### File Naming

Files are named with a slug derived from the title plus a short hash:
`sarah-chen-a1b2.md`

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
