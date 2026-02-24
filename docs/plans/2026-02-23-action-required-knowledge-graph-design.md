# Action Required Category + Knowledge Graph

**Date:** 2026-02-23
**Status:** Design Approved

---

## Overview

Add a 4th memory category ("Action Required") to the vault that surfaces items needing the user's attention, classified using the Eisenhower matrix with justification derived from full vault context. Upgrade the vault's WikiLink system into a full bidirectional knowledge graph with a computed relationship index and graph traversal tools.

---

## Requirements

1. **New "Action Required" vault category** — items that surface things requiring action
2. **Eisenhower matrix priority** — `urgent-important`, `important-not-urgent`, `urgent-not-important`, `neither` — with written justification based on vault context
3. **Full knowledge graph** — bidirectional WikiLinks, `_graph.json` adjacency index, graph traversal MCP tool, backlinks injected into file frontmatter
4. **Dual trigger** — Action items generated during build pipeline (auto) AND refreshable via standalone "refresh"/"prioritize" chat command
5. **Auto-refresh after build** — ActionAgent runs as final pipeline step after every build

---

## Architecture

### Updated Pipeline

```
BUILD:
  Fetch Emails → Email Reader (batched) → Memory Writer → Graph Rebuild → Action Agent

REFRESH (standalone):
  Action Agent (reads full vault + graph, regenerates action items)

QUERY (unchanged):
  Query Agent (now has graph traversal tools too)
```

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| ActionAgent | `agents/action_agent.py` | Reads full vault + graph, creates/updates action_required files |
| Graph module | `memory/graph.py` | Builds/queries `_graph.json`, handles backlink injection |
| Graph MCP tools | Added to `mcp_servers/memory_server.py` | `get_graph`, `traverse_graph` tools |

### Modified Components

| Component | Change |
|-----------|--------|
| `config/settings.py` | Add `action_required` to `MEMORY_TYPES` |
| `memory/vault.py` | Add `action_required/` folder init, call `rebuild_graph()` after writes |
| `orchestrator.py` | Add ActionAgent as build Step 4, add "refresh"/"prioritize" routing |
| `agents/query_agent.py` | Add `get_graph` and `traverse_graph` tools |
| `agents/memory_writer.py` | Add `source_memories` field support |
| `mcp_servers/memory_server.py` | Add `get_graph`, `traverse_graph` tool definitions |
| `web/app.py` | Add `/api/stream/refresh` endpoint (or reuse build streaming) |

---

## Design Details

### 1. Action Required File Format

```yaml
---
title: "Follow up with Jake O'Shea about Antler partnership"
date: '2026-02-23'
updated: '2026-02-23'
category: action_required
memoryType: action_required
quadrant: "urgent-important"
priority_justification: "Jake is a Principal at Antler (VC). You committed to a follow-up call on 2026-02-20. This aligns with your active job search decision (priority red). Time-sensitive commitment window."
deadline: '2026-02-28'
source_type: "commitment"
tags:
  - follow-up
  - venture-capital
related_to:
  - Jake O'Shea
  - Antler
  - active-job-search-for-senior-product-leadership-roles
source_emails:
  - "Moltathon ATX Followup - Antler"
source_memories:
  - "people/jake-o-shea-8340.md"
  - "commitments/follow-up-call-with-jake-oshea-1a2b.md"
  - "decisions/active-job-search-db8d.md"
---

# Follow up with Jake O'Shea about Antler partnership

**Quadrant:** Urgent + Important
**Deadline:** 2026-02-28

## Why This Matters

[[Jake O'Shea]] is a Principal at [[Antler]] who you met at the Moltathon ATX event...

## Priority Justification

Classified as **Urgent + Important** because:
1. Time-sensitive commitment
2. High-value relationship aligned with career goals
3. Connects to red-priority decision about job search
4. Relationship risk if not followed up

## Recommended Action

Schedule a 30-minute call with Jake O'Shea this week.

## Related

**Related:** [[Jake O'Shea]], [[Antler]], [[active-job-search-for-senior-product-leadership-roles]]
```

**Key fields:**
- `quadrant` — Eisenhower classification (enum of 4 values)
- `priority_justification` — compact one-liner for frontmatter; full justification in body
- `source_memories` — provenance chain: which vault files informed this action item
- `source_type` — which category surfaced this (commitment, decision, people, email)
- `deadline` — extracted or inferred date, null if unknown

### 2. Knowledge Graph (`_graph.json`)

Stored at `vault/_graph.json`. Rebuilt after every `write_memory()` call.

```json
{
  "nodes": {
    "people/jake-o-shea-8340.md": {
      "title": "Jake O'Shea",
      "type": "people",
      "priority": "yellow",
      "date": "2026-02-20"
    }
  },
  "edges": [
    {
      "from": "people/jake-o-shea-8340.md",
      "to": "commitments/follow-up-call-1a2b.md",
      "relation": "related_to"
    },
    {
      "from": "commitments/follow-up-call-1a2b.md",
      "to": "people/jake-o-shea-8340.md",
      "relation": "backlink"
    }
  ],
  "rebuilt_at": "2026-02-23T14:30:00Z"
}
```

**Build process (`memory/graph.py`):**
1. Scan all vault files, parse YAML frontmatter
2. Create node entry per file (filepath, title, type, priority, date)
3. For each `related_to` entry: create forward edge + reverse backlink edge
4. For each `source_memories` entry: create `source_memory` edge + reverse `referenced_by` edge
5. Write `_graph.json`
6. Inject missing backlinks into file frontmatter `related_to` arrays

**New MCP tools:**
- `get_graph()` — returns full `_graph.json` contents
- `traverse_graph(entity, max_depth=2)` — BFS from entity, returns all reachable nodes with paths

### 3. ActionAgent (Agent 4)

**System prompt strategy:**
- Reads full vault index + graph to understand the user's world
- Reads individual memories to build deep context
- For each potential action: cross-references people, decisions, commitments
- Classifies into Eisenhower quadrant with written justification
- Deduplicates against existing action items
- Can mark stale action items as resolved

**Tools (8 total):**
1. `get_vault_index()` — see all memories
2. `search_vault(query)` — find related items
3. `read_memory(filepath)` — read full content
4. `list_memories(memory_type)` — list by category
5. `get_graph()` — full relationship map
6. `traverse_graph(entity, max_depth)` — connected entities
7. `write_memory(...)` — create/update action_required files
8. `get_vault_stats()` — vault size context

**Eisenhower classification rules (in system prompt):**
- **Urgent + Important:** Time-sensitive AND aligned with user's high-priority decisions/commitments
- **Important + Not Urgent:** Aligned with user's goals but no immediate deadline
- **Urgent + Not Important:** Time-sensitive but tangential to user's core priorities
- **Neither:** Low-priority, informational, or already partially addressed

### 4. Orchestrator Changes

**New routing keywords:**
- "refresh", "prioritize", "actions", "action items", "what needs attention" → ActionAgent (standalone refresh)

**Updated build pipeline:**
```python
async def build_memory(self, ...):
    # Step 1: Fetch emails (existing)
    # Step 2: Email Reader batched analysis (existing)
    # Step 3: Memory Writer (existing)
    # Step 3.5: Rebuild graph (NEW)
    # Step 4: Action Agent refresh (NEW)
```

### 5. Backlink Injection

When `rebuild_graph()` runs, it:
1. Computes all bidirectional edges
2. For each file, checks if its `related_to` frontmatter includes all entities that reference it
3. If missing backlinks are found, rewrites the file's frontmatter to include them
4. Does NOT modify markdown body content — only YAML frontmatter `related_to` array

---

## Data Flow

```
                    ┌──────────────────────┐
                    │   Email Reader        │
                    │   (observations JSON) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Memory Writer       │
                    │   (writes vault files)│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Graph Rebuild       │
                    │   (scan all files,   │
                    │    build _graph.json, │
                    │    inject backlinks)  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Action Agent        │
                    │   (read vault+graph,  │
                    │    reason about       │
                    │    priorities,         │
                    │    write action items) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Graph Rebuild       │
                    │   (again, to capture  │
                    │    new action items)  │
                    └──────────────────────┘
```

Note: Graph rebuilds twice — once after MemoryWriter (so ActionAgent has a current graph) and once after ActionAgent (so action items are in the graph too).

---

## Non-Goals

- No UI changes to the chat interface (action items are queryable via existing QueryAgent)
- No deletion of action items (they can be marked stale but not auto-deleted)
- No notification system (action items are passive — you query them)
- No external calendar integration
