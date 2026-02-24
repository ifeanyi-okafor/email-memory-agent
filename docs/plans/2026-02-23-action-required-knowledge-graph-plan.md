# Action Required + Knowledge Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 4th memory category ("action_required") with Eisenhower matrix prioritization, and upgrade the vault into a full bidirectional knowledge graph with a JSON adjacency index and graph traversal tools.

**Architecture:** New ActionAgent (Agent 4) reads the entire vault + graph to generate action items with Eisenhower classification and justification. A new `memory/graph.py` module builds and queries `_graph.json` — a bidirectional adjacency map rebuilt after every vault write. Backlinks are injected into file frontmatter to keep the graph visible in markdown files.

**Tech Stack:** Python, Anthropic SDK (existing), YAML/JSON (existing), pathlib (existing). No new dependencies.

---

### Task 1: Add `action_required` to MEMORY_TYPES

**Files:**
- Modify: `config/settings.py:108-112`
- Modify: `memory/vault.py:63-67`

**Step 1: Update config/settings.py**

In `config/settings.py`, change the `MEMORY_TYPES` list at line 108:

```python
MEMORY_TYPES = [
    'decisions',       # Choices you've made ("chose React over Vue")
    'people',          # People you interact with ("Sarah — CTO at Acme")
    'commitments',     # Promises and deadlines ("review PRs by Friday")
    'action_required', # Items that need your attention, prioritized by Eisenhower matrix
]
```

**Step 2: Update memory/vault.py**

In `memory/vault.py`, change the `MEMORY_TYPES` list at line 63:

```python
MEMORY_TYPES = [
    'decisions',       # Choices: "chose React over Vue"
    'people',          # Contacts: "Sarah — CTO at Acme" (also captures preferences, topics, comm style)
    'commitments',     # Promises: "review PRs by Friday"
    'action_required', # Action items: prioritized by Eisenhower matrix with justification
]
```

**Step 3: Run the vault initialization to verify the new folder is created**

Run: `python -c "from memory.vault import initialize_vault; initialize_vault()"`
Expected: `vault/action_required/` folder created

**Step 4: Commit**

```bash
git add config/settings.py memory/vault.py
git commit -m "feat: add action_required as 4th memory type"
```

---

### Task 2: Extend `write_memory()` for action_required fields

**Files:**
- Modify: `memory/vault.py:201-382` (the `write_memory` function)

**Step 1: Add new parameters to write_memory**

Add these parameters after `source_emails` in the function signature at line 208:

```python
    source_emails: list[str] = None,
    # Action Required-specific fields (optional, only used when memory_type == 'action_required')
    quadrant: str = None,
    priority_justification: str = None,
    deadline: str = None,
    source_type: str = None,
    source_memories: list[str] = None,
    # People-specific fields (optional, only used when memory_type == 'people')
```

**Step 2: Add action_required frontmatter branch**

After the `if memory_type == 'people':` block and before the `else:` block (around line 334), add a new branch:

```python
    elif memory_type == 'action_required':
        # ── Action Required-specific frontmatter ─────────────
        frontmatter = {
            'title': title,
            'date': today,
            'updated': today,
            'category': 'action_required',
            'memoryType': 'action_required',
            'quadrant': quadrant or 'important-not-urgent',
            'priority_justification': priority_justification or '',
            'deadline': deadline or '',
            'source_type': source_type or '',
            'tags': tags or [],
            'related_to': related_to or [],
            'source_emails': source_emails or [],
            'source_memories': source_memories or [],
        }

        # Build wiki-links section
        wiki_links_section = ''
        if related_to:
            links = ', '.join([f'[[{entity}]]' for entity in related_to])
            wiki_links_section = f'\n**Related:** {links}\n'

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        file_content = f"""---
{yaml_str.strip()}
---

# {title}

{wiki_links_section}
{content}
"""
```

Also update the `is_update` detection at the bottom of the function (line 378). Change:

```python
    is_update = (memory_type == 'people') and (original_date != today)
```

To:

```python
    is_update = (memory_type in ('people', 'action_required')) and filepath.exists()
```

Wait — actually, `original_date` is only defined in the people branch. The simpler fix is to initialize `is_update = False` at the top of the function (before the if/elif/else chain) and let each branch set it. Or just keep the current check since it only applies to people. The action_required branch sets `updated` but doesn't preserve original date (action items are regenerated, not merged). Leave the is_update check as-is; it won't affect action_required.

**Step 3: Verify write_memory works for action_required**

Run:
```python
python -c "
from memory.vault import write_memory, initialize_vault
initialize_vault()
path = write_memory(
    title='Test Action Item',
    memory_type='action_required',
    content='Test content',
    quadrant='urgent-important',
    priority_justification='Test justification',
    deadline='2026-03-01',
    source_type='commitment',
    source_memories=['commitments/test.md'],
    related_to=['Test Person'],
    tags=['test']
)
print(f'Written to: {path}')
"
```
Expected: File created at `vault/action_required/test-action-item-XXXX.md` with proper YAML frontmatter

**Step 4: Clean up test file and commit**

```bash
# Remove the test file
rm vault/action_required/test-action-item-*.md
git add memory/vault.py
git commit -m "feat: extend write_memory with action_required fields (quadrant, deadline, source_memories)"
```

---

### Task 3: Create the graph module (`memory/graph.py`)

**Files:**
- Create: `memory/graph.py`

**Step 1: Write the graph module**

Create `memory/graph.py` with these functions:

```python
# memory/graph.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This module builds and queries the knowledge graph — a bidirectional
# map of all relationships between memories in the vault.
#
# The graph is stored as `vault/_graph.json` and rebuilt after every
# vault write. It enables:
#   - Bidirectional links: if A references B, B knows about A
#   - Graph traversal: find all entities connected within N hops
#   - Backlink injection: update file frontmatter with reverse links
# ============================================================================

import json
import yaml
from datetime import datetime
from pathlib import Path
from collections import deque

# Vault root — same as vault.py
VAULT_ROOT = Path('vault')

# The list of memory types to scan (imported at function call time
# to avoid circular imports, or just hardcode the folders to scan)
MEMORY_CATEGORIES = ['decisions', 'people', 'commitments', 'action_required']

GRAPH_FILE = VAULT_ROOT / '_graph.json'


def rebuild_graph() -> dict:
    """
    Scan all vault files, build a bidirectional adjacency map,
    and write it to vault/_graph.json.

    Process:
    1. Scan all .md files across all memory type folders
    2. Parse YAML frontmatter from each file
    3. Build nodes (one per file) and edges (from related_to + source_memories)
    4. Add reverse edges (backlinks) for every forward edge
    5. Write _graph.json
    6. Inject missing backlinks into file frontmatter

    Returns:
        The graph dict (also written to disk).
    """
    nodes = {}
    forward_edges = []  # (from_path, to_entity_or_path, relation)

    # ── Step 1-2: Scan files and parse frontmatter ──────────
    for category in MEMORY_CATEGORIES:
        folder = VAULT_ROOT / category
        if not folder.exists():
            continue

        for md_file in folder.glob('*.md'):
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            text = md_file.read_text(encoding='utf-8')

            # Parse YAML frontmatter
            frontmatter = {}
            if text.startswith('---'):
                parts = text.split('---', 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                    except yaml.YAMLError:
                        pass

            # Build node
            title = frontmatter.get('title') or frontmatter.get('name', md_file.stem)
            node = {
                'title': title,
                'type': category,
                'date': str(frontmatter.get('date', '')),
            }
            # Add type-specific fields
            if category == 'action_required':
                node['quadrant'] = frontmatter.get('quadrant', '')
            else:
                node['priority'] = frontmatter.get('priority', '')

            nodes[rel_path] = node

            # Collect forward edges from related_to
            for entity in frontmatter.get('related_to', []):
                forward_edges.append((rel_path, entity, 'related_to'))

            # Collect forward edges from source_memories
            for mem_path in frontmatter.get('source_memories', []):
                forward_edges.append((rel_path, mem_path, 'source_memory'))

    # ── Step 3: Build a title-to-filepath lookup ─────────────
    # This lets us resolve entity names (like "Jake O'Shea") to
    # actual file paths (like "people/jake-o-shea-8340.md")
    title_to_path = {}
    for path, node in nodes.items():
        title_lower = node['title'].lower()
        title_to_path[title_lower] = path
        # Also index by name-only (before " — ") for people
        if ' — ' in node['title']:
            name_part = node['title'].split(' — ')[0].strip().lower()
            title_to_path[name_part] = path

    # ── Step 4: Resolve edges and build bidirectional list ────
    edges = []
    resolved_pairs = set()  # Track (from, to, relation) to avoid duplicates

    for from_path, target, relation in forward_edges:
        # Try to resolve target to a file path
        to_path = None
        if target in nodes:
            # Target is already a file path
            to_path = target
        else:
            # Try to match by title (case-insensitive)
            to_path = title_to_path.get(target.lower())

        if to_path and to_path != from_path:
            # Forward edge
            key = (from_path, to_path, relation)
            if key not in resolved_pairs:
                edges.append({'from': from_path, 'to': to_path, 'relation': relation})
                resolved_pairs.add(key)

            # Reverse edge (backlink)
            reverse_relation = 'backlink' if relation == 'related_to' else 'referenced_by'
            rev_key = (to_path, from_path, reverse_relation)
            if rev_key not in resolved_pairs:
                edges.append({'from': to_path, 'to': from_path, 'relation': reverse_relation})
                resolved_pairs.add(rev_key)

    # ── Step 5: Write _graph.json ─────────────────────────────
    graph = {
        'nodes': nodes,
        'edges': edges,
        'rebuilt_at': datetime.now().isoformat()
    }

    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_FILE.write_text(json.dumps(graph, indent=2), encoding='utf-8')

    # ── Step 6: Inject backlinks into file frontmatter ────────
    _inject_backlinks(nodes, edges)

    return graph


def _inject_backlinks(nodes: dict, edges: list):
    """
    For each file in the vault, ensure its related_to frontmatter
    includes all entities that reference it (backlinks).

    Only modifies frontmatter — never touches the markdown body.
    """
    # Build a map: filepath → set of entity titles that should be in related_to
    backlink_map = {}  # filepath → set of titles to add
    for edge in edges:
        if edge['relation'] in ('backlink', 'referenced_by'):
            target_file = edge['from']  # The file that should get the backlink
            source_file = edge['to']    # The file that references it
            if source_file in nodes:
                source_title = nodes[source_file]['title']
                backlink_map.setdefault(target_file, set()).add(source_title)

    # For each file, check if backlinks are missing from related_to
    for filepath, titles_to_add in backlink_map.items():
        full_path = VAULT_ROOT / filepath
        if not full_path.exists():
            continue

        text = full_path.read_text(encoding='utf-8')
        if not text.startswith('---'):
            continue

        parts = text.split('---', 2)
        if len(parts) < 3:
            continue

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            continue

        existing_related = set(frontmatter.get('related_to', []))
        new_entries = titles_to_add - existing_related

        if not new_entries:
            continue  # No new backlinks needed

        # Add new backlinks to related_to
        updated_related = list(existing_related | new_entries)
        frontmatter['related_to'] = sorted(updated_related)

        # Rebuild the file with updated frontmatter
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        body = parts[2]  # Preserve the markdown body exactly as-is
        updated_text = f"---\n{yaml_str.strip()}\n---{body}"
        full_path.write_text(updated_text, encoding='utf-8')


def get_graph() -> dict:
    """
    Read and return the graph from _graph.json.

    Returns an empty graph structure if the file doesn't exist yet.
    """
    if not GRAPH_FILE.exists():
        return {'nodes': {}, 'edges': [], 'rebuilt_at': None}

    return json.loads(GRAPH_FILE.read_text(encoding='utf-8'))


def traverse_graph(entity: str, max_depth: int = 2) -> dict:
    """
    BFS traversal from a starting entity, returning all reachable
    nodes within max_depth hops.

    Args:
        entity:    Starting point — can be a filepath ("people/me.md")
                   or an entity title ("Jake O'Shea").
        max_depth: Maximum number of hops to traverse (default 2).

    Returns:
        {
            "start": "people/me.md",
            "nodes": { "filepath": {node_data, "depth": N}, ... },
            "edges": [ {from, to, relation}, ... ],
            "depth_searched": 2
        }
    """
    graph = get_graph()
    nodes = graph.get('nodes', {})
    edges = graph.get('edges', [])

    # Resolve entity to filepath
    start_path = None
    if entity in nodes:
        start_path = entity
    else:
        # Search by title (case-insensitive)
        entity_lower = entity.lower()
        for path, node in nodes.items():
            title = node.get('title', '').lower()
            if entity_lower == title or entity_lower in title:
                start_path = path
                break

    if not start_path:
        return {
            'start': entity,
            'nodes': {},
            'edges': [],
            'depth_searched': max_depth,
            'error': f'Entity "{entity}" not found in graph'
        }

    # Build adjacency list for BFS
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge['from'], []).append(edge)

    # BFS
    visited = {start_path: 0}
    queue = deque([(start_path, 0)])
    reachable_edges = []

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for edge in adjacency.get(current, []):
            neighbor = edge['to']
            if neighbor not in visited:
                visited[neighbor] = depth + 1
                queue.append((neighbor, depth + 1))
            reachable_edges.append(edge)

    # Build result
    result_nodes = {}
    for path, depth in visited.items():
        node_data = dict(nodes.get(path, {'title': path, 'type': 'unknown'}))
        node_data['depth'] = depth
        result_nodes[path] = node_data

    return {
        'start': start_path,
        'nodes': result_nodes,
        'edges': reachable_edges,
        'depth_searched': max_depth
    }
```

**Step 2: Test the graph module**

Run:
```python
python -c "
from memory.graph import rebuild_graph, get_graph, traverse_graph
graph = rebuild_graph()
print(f'Nodes: {len(graph[\"nodes\"])}')
print(f'Edges: {len(graph[\"edges\"])}')
# Test traversal from me.md
result = traverse_graph('people/me.md', max_depth=2)
print(f'Traversal from me.md: {len(result[\"nodes\"])} nodes reachable')
"
```
Expected: Graph built with nodes for all existing vault files and edges from their `related_to` fields.

**Step 3: Commit**

```bash
git add memory/graph.py
git commit -m "feat: add knowledge graph module with rebuild, traversal, and backlink injection"
```

---

### Task 4: Hook graph rebuild into vault writes

**Files:**
- Modify: `memory/vault.py:365-382` (end of `write_memory`)

**Step 1: Add graph rebuild call after every write**

At the end of `write_memory()`, after `update_index(...)` and before the print statement, add:

```python
    # ── Rebuild the knowledge graph ─────────────────────────
    # This keeps the graph index up-to-date with every write,
    # including injecting backlinks into related files.
    from memory.graph import rebuild_graph
    rebuild_graph()
```

Place this after `update_index(...)` (line 373) and before the `is_update` check (line 378).

**Step 2: Verify graph rebuilds on write**

Run:
```python
python -c "
from memory.vault import write_memory, initialize_vault
from memory.graph import get_graph
initialize_vault()
write_memory(title='Test Graph', memory_type='decisions', content='Test', related_to=['Me'])
graph = get_graph()
print(f'Graph has {len(graph[\"nodes\"])} nodes, {len(graph[\"edges\"])} edges')
print(f'Rebuilt at: {graph[\"rebuilt_at\"]}')
"
```
Expected: Graph includes the new decision file, with edges to/from "Me".

**Step 3: Clean up test file and commit**

```bash
rm vault/decisions/test-graph-*.md
git add memory/vault.py
git commit -m "feat: rebuild knowledge graph after every vault write"
```

---

### Task 5: Add graph tools to MCP memory server

**Files:**
- Modify: `mcp_servers/memory_server.py`

**Step 1: Add imports**

At the top of `memory_server.py`, add to the imports (after line 41):

```python
from memory.graph import get_graph, traverse_graph, rebuild_graph
```

**Step 2: Add tool definitions**

In the `list_tools()` function, add two new tools after the `get_vault_stats` tool:

```python
        # Tool 7: Get the full knowledge graph
        Tool(
            name="get_graph",
            description="Get the full knowledge graph — a bidirectional map of all relationships between memories. Returns nodes (all memory files) and edges (related_to, backlink, source_memory, referenced_by connections).",
            inputSchema={"type": "object", "properties": {}}
        ),

        # Tool 8: Traverse the graph from a starting entity
        Tool(
            name="traverse_graph",
            description="Find all memories connected to a starting entity within N hops. Uses BFS traversal. Entity can be a filepath (e.g., 'people/me.md') or a title (e.g., 'Jake O\\'Shea').",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Starting entity — filepath or title"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum hops to traverse (default: 2)",
                        "default": 2
                    }
                },
                "required": ["entity"]
            }
        ),
```

**Step 3: Add tool execution handlers**

In the `call_tool()` function, add handlers before the `raise ValueError` line:

```python
    elif name == "get_graph":
        graph = get_graph()
        return [TextContent(type="text", text=json.dumps(graph, indent=2))]

    elif name == "traverse_graph":
        result = traverse_graph(
            entity=arguments['entity'],
            max_depth=arguments.get('max_depth', 2)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

**Step 4: Commit**

```bash
git add mcp_servers/memory_server.py
git commit -m "feat: add get_graph and traverse_graph MCP tools"
```

---

### Task 6: Add graph tools to QueryAgent

**Files:**
- Modify: `agents/query_agent.py`

**Step 1: Add graph imports**

Add to the imports at line 33:

```python
from memory.graph import get_graph, traverse_graph
```

**Step 2: Update system prompt**

In the system prompt (line 63), update the description of available memory types and add graph instructions. Replace the line:

```
Memories are organized by type: decisions, people, commitments.
```

With:

```
Memories are organized by type: decisions, people, commitments, action_required.
Action items are classified by Eisenhower matrix (urgent-important, important-not-urgent, urgent-not-important, neither).
The vault has a knowledge graph (_graph.json) that maps bidirectional relationships between all memories.
```

Add to the YOUR PROCESS section:

```
5. Use get_graph or traverse_graph to explore connections between memories
```

**Step 3: Add tool definitions**

Add two new tools to `self.tools` list (after the `get_vault_stats` tool):

```python
            {
                "name": "get_graph",
                "description": "Get the full knowledge graph showing all relationships between memories. Returns nodes (files) and edges (connections like related_to, backlink, source_memory).",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "traverse_graph",
                "description": "Find all memories connected to a starting entity within N hops. BFS traversal. Entity can be a filepath or title.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Starting entity — filepath (e.g., 'people/me.md') or title (e.g., 'Jake O\\'Shea')"
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Max hops (default: 2)",
                            "default": 2
                        }
                    },
                    "required": ["entity"]
                }
            },
```

**Step 4: Add tool execution handlers**

In `execute_tool()`, add before the `raise ValueError` line:

```python
        elif tool_name == "get_graph":
            graph = get_graph()
            return json.dumps(graph, indent=2)

        elif tool_name == "traverse_graph":
            result = traverse_graph(
                entity=tool_args['entity'],
                max_depth=tool_args.get('max_depth', 2)
            )
            return json.dumps(result, indent=2)
```

**Step 5: Commit**

```bash
git add agents/query_agent.py
git commit -m "feat: add graph tools to QueryAgent for relationship exploration"
```

---

### Task 7: Create the ActionAgent (`agents/action_agent.py`)

**Files:**
- Create: `agents/action_agent.py`

**Step 1: Write the ActionAgent**

Create `agents/action_agent.py`:

```python
# agents/action_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 4" — the Action Agent. It reads the ENTIRE vault and
# knowledge graph to identify items that need the user's attention.
#
# It creates "action_required" memory files with:
#   - Eisenhower matrix classification (urgent/important quadrant)
#   - Priority justification based on the full vault context
#   - Links back to the source memories that informed the action
#
# Think of it as a personal assistant who reviews all your notes,
# commitments, and contacts, then produces a prioritized action list.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from memory.vault import (
    write_memory, read_memory, search_vault, list_memories,
    get_vault_index, get_vault_stats, MEMORY_TYPES
)
from memory.graph import get_graph, traverse_graph


# ── THE ACTION AGENT CLASS ──────────────────────────────────────────

class ActionAgent(BaseAgent):
    """
    Agent 4: Reads the full vault and graph to generate prioritized action items.

    This agent reasons across ALL memory categories to determine what
    needs the user's attention, classifies items using the Eisenhower
    matrix, and writes action_required files with justification.
    """

    def __init__(self):
        """Set up the Action Agent with its analysis prompt and tools."""
        super().__init__()

        self.system_prompt = """You are the Action Agent in a multi-agent system.

YOUR ROLE: Read the entire memory vault and knowledge graph to identify items that require the user's attention. Create prioritized "action_required" memory files.

YOUR PROCESS:
1. Read the vault index (get_vault_index) to see all memories
2. Get the knowledge graph (get_graph) to understand relationships
3. List and read commitments, decisions, and people files for full context
4. For each potential action item:
   a. Use traverse_graph to find connected entities (people, decisions, other commitments)
   b. Read the connected memories to build full context
   c. Determine the Eisenhower quadrant based on urgency and importance
   d. Write a justification that references specific vault memories
5. Check for existing action items (search_vault) to avoid duplicates
6. Write new action_required files using write_memory

EISENHOWER MATRIX CLASSIFICATION:
- "urgent-important": Time-sensitive AND directly aligned with user's high-priority decisions or critical relationships. Examples: expiring deadlines on key commitments, follow-ups with high-value contacts, time-sensitive career decisions.
- "important-not-urgent": Aligned with user's goals/values but no immediate deadline. Examples: strengthening key relationships, pursuing strategic opportunities, skill development aligned with decisions.
- "urgent-not-important": Has a deadline or time pressure but tangential to user's core priorities. Examples: routine follow-ups, administrative tasks, low-stakes RSVPs.
- "neither": Low priority, informational, or already partially addressed. Examples: optional networking, minor updates, already-completed items.

CLASSIFICATION RULES:
- ALWAYS read the "Me" person file (people/me.md) first to understand the user's priorities, role, and goals
- Cross-reference with decisions to understand what the user has chosen to prioritize
- Cross-reference with people files to understand relationship importance
- Look at commitment deadlines relative to today's date
- Consider the priority level (🔴/🟡/🟢) of related memories as signals

WHEN WRITING ACTION ITEMS:
- Use write_memory with memory_type="action_required"
- Required fields: title, content, quadrant, priority_justification, source_type, source_memories, related_to, tags
- Optional fields: deadline (if known or inferable), source_emails
- The content MUST include these sections:
  * "## Why This Matters" — context from the vault about why this matters to the user
  * "## Priority Justification" — numbered list explaining the Eisenhower classification
  * "## Recommended Action" — specific, actionable next step
- The priority_justification field in frontmatter should be a concise 1-2 sentence summary
- source_memories must list the actual filepaths of vault files you consulted
- related_to must list entity names for wiki-links

DEDUPLICATION:
- Before writing, search for existing action items with similar titles
- If a similar action item exists, read it and decide:
  * If still relevant: update it (rewrite with current information)
  * If no longer relevant: note this in your summary but don't delete it

SOURCE TYPES:
- "commitment" — action derived from a commitment/promise
- "decision" — action derived from a decision that needs follow-through
- "people" — action derived from a relationship that needs attention
- "email" — action derived directly from email content

When done, return a summary of:
- How many action items were created/updated
- The Eisenhower breakdown (how many in each quadrant)
- Top 3 most urgent items
"""

        # ── Tool Definitions ───────────────────────────────────
        self.tools = [
            {
                "name": "get_vault_index",
                "description": "Read the master vault index — table of all memories.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "search_vault",
                "description": "Search across all memories using text matching.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_memory",
                "description": "Read a specific memory file in full.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string", "description": "Path relative to vault root"}
                    },
                    "required": ["filepath"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all memories, optionally filtered by type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": MEMORY_TYPES,
                            "description": "Filter by category (optional)"
                        }
                    }
                }
            },
            {
                "name": "get_graph",
                "description": "Get the full knowledge graph showing all bidirectional relationships between memories.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "traverse_graph",
                "description": "Find all memories connected to a starting entity within N hops.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Starting entity — filepath or title"
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Max hops (default: 2)",
                            "default": 2
                        }
                    },
                    "required": ["entity"]
                }
            },
            {
                "name": "write_memory",
                "description": (
                    "Write an action_required memory file to the vault. "
                    "Include quadrant, priority_justification, source_memories, "
                    "and other action-specific fields."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Clear, action-oriented title"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["action_required"],
                            "description": "Must be 'action_required'"
                        },
                        "content": {
                            "type": "string",
                            "description": "Markdown content with ## Why This Matters, ## Priority Justification, ## Recommended Action sections"
                        },
                        "quadrant": {
                            "type": "string",
                            "enum": ["urgent-important", "important-not-urgent", "urgent-not-important", "neither"],
                            "description": "Eisenhower matrix classification"
                        },
                        "priority_justification": {
                            "type": "string",
                            "description": "1-2 sentence summary of why this quadrant was chosen"
                        },
                        "deadline": {
                            "type": "string",
                            "description": "Deadline date if known (YYYY-MM-DD format)"
                        },
                        "source_type": {
                            "type": "string",
                            "enum": ["commitment", "decision", "people", "email"],
                            "description": "Which vault category surfaced this action"
                        },
                        "source_memories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filepaths of vault files consulted (e.g., 'people/jake-8340.md')"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keyword tags"
                        },
                        "related_to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Entity names for [[wiki-links]]"
                        },
                        "source_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Source email subjects (if applicable)"
                        }
                    },
                    "required": ["title", "memory_type", "content", "quadrant", "priority_justification", "source_type"]
                }
            },
            {
                "name": "get_vault_stats",
                "description": "Get summary counts of memories per category.",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Run the requested tool and return the result."""

        if tool_name == "get_vault_index":
            return get_vault_index()

        elif tool_name == "search_vault":
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "read_memory":
            result = read_memory(tool_args['filepath'])
            if result:
                return json.dumps(result, indent=2)
            return "Memory file not found."

        elif tool_name == "list_memories":
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "get_graph":
            graph = get_graph()
            return json.dumps(graph, indent=2)

        elif tool_name == "traverse_graph":
            result = traverse_graph(
                entity=tool_args['entity'],
                max_depth=tool_args.get('max_depth', 2)
            )
            return json.dumps(result, indent=2)

        elif tool_name == "write_memory":
            filepath = write_memory(**tool_args)
            return f"Action item written to: {filepath}"

        elif tool_name == "get_vault_stats":
            stats = get_vault_stats()
            return json.dumps(stats, indent=2)

        raise ValueError(f"Unknown tool: {tool_name}")
```

**Step 2: Commit**

```bash
git add agents/action_agent.py
git commit -m "feat: create ActionAgent (Agent 4) for Eisenhower-prioritized action items"
```

---

### Task 8: Update the Orchestrator

**Files:**
- Modify: `orchestrator.py`

**Step 1: Add ActionAgent import**

At line 44, add:

```python
from agents.action_agent import ActionAgent
```

Add graph import at line 51:

```python
from memory.graph import rebuild_graph
```

**Step 2: Initialize ActionAgent in __init__**

In `__init__()` at line 89, add after `self.query_agent`:

```python
        self.action_agent = ActionAgent()      # Agent 4: generates action items
```

**Step 3: Add "refresh" routing**

In the `route()` method, add a new routing block after the "build" check (after line 121) and before the "stats" check:

```python
        # ── Check for "refresh actions" intent ───────────────
        # If the user wants to refresh or view prioritized actions
        elif any(kw in user_lower for kw in [
            'refresh', 'prioritize', 'actions', 'action items',
            'what needs attention', 'what should i do', 'priorities'
        ]):
            return self.refresh_actions(user_input)
```

**Step 4: Add refresh_actions method**

Add a new method after `build_memory()`:

```python
    def refresh_actions(self, user_input: str, progress_callback=None) -> str:
        """
        Run the Action Agent to scan the full vault and generate/update
        action items with Eisenhower classification.

        This can be triggered standalone ("refresh actions") or as the
        final step of the build pipeline.

        Args:
            user_input:        The user's request.
            progress_callback: Optional function(dict) for SSE progress events.

        Returns:
            str: Summary of action items created/updated.
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Action Agent[/bold cyan] scanning vault for action items...\n")
        emit({
            "stage": "action_agent", "status": "started",
            "message": "Scanning vault and graph for action items..."
        })

        # Reset agent for fresh context
        self.action_agent.reset()

        # Set up retry callback
        def on_action_retry(attempt, max_retries, delay):
            emit({
                "stage": "action_agent", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.action_agent.on_retry = on_action_retry

        prompt = (
            "Scan the entire memory vault and knowledge graph. "
            "Identify all items that require the user's attention. "
            "Create action_required memory files with Eisenhower matrix "
            "classification and justification based on the full vault context. "
            f"Today's date is {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}."
        )

        result = self.action_agent.run(prompt, max_tool_rounds=15)

        console.print("[green]OK - Action Agent complete[/green]\n")
        emit({
            "stage": "action_agent", "status": "complete",
            "message": "Action items generated"
        })

        return result
```

**Step 5: Add Action Agent as Step 4 of build pipeline**

In `build_memory()`, after tracking processed email IDs (after line 332: `save_processed_email_ids(new_ids)`) and before the summary section, add:

```python
        # ── Step 3.5: Rebuild knowledge graph ──────────────────
        console.print("\n[bold cyan]Step 3.5/4: Rebuilding knowledge graph[/bold cyan]")
        emit({
            "stage": "graph_rebuild", "status": "started",
            "message": "Rebuilding knowledge graph with new memories..."
        })
        graph = rebuild_graph()
        console.print(f"[green]OK - Graph rebuilt: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges[/green]")
        emit({
            "stage": "graph_rebuild", "status": "complete",
            "message": f"Graph rebuilt: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges"
        })

        # ── Step 4: Action Agent ──────────────────────────────
        console.print("\n[bold cyan]Step 4/4: Action Agent[/bold cyan]")
        action_result = self.refresh_actions(
            "Generate action items from the newly updated vault.",
            progress_callback=progress_callback
        )
```

Also update the step count labels in the Panel display at the beginning of build_memory (around line 173):

```python
        console.print(Panel(
            "[bold]Starting memory build pipeline...[/bold]\n"
            f"   Step 1: Fetch up to {max_emails} emails from last {days_back} days\n"
            f"   Step 2: Analyze in batches of {EMAIL_BATCH_SIZE}\n"
            "   Step 3: Memory Writer -- Create memory files\n"
            "   Step 3.5: Rebuild knowledge graph\n"
            "   Step 4: Action Agent -- Generate prioritized action items",
            title="Pipeline",
            border_style="blue"
        ))
```

And update the step headers throughout:
- Line 182: `"Step 1/4: Fetching emails"` (was 1/3)
- Line 224: `"Step 2/4: Analyzing..."` (was 2/3)
- Line 298: `"Step 3/4: Memory Writer Agent"` (was 3/3)

**Step 6: Update show_stats to include action_required**

No code change needed — `show_stats()` already iterates `stats.items()` which will include `action_required` since it's now in `MEMORY_TYPES`.

**Step 7: Commit**

```bash
git add orchestrator.py
git commit -m "feat: add ActionAgent to orchestrator with build pipeline integration and refresh routing"
```

---

### Task 9: Add SSE streaming for refresh endpoint

**Files:**
- Modify: `web/app.py`

**Step 1: Add refresh streaming endpoint**

After the `stream_build` endpoint (after line 323), add:

```python
@app.get("/api/stream/refresh")
async def stream_refresh():
    """
    Run the Action Agent with live progress updates via SSE.

    Scans the full vault and knowledge graph to generate/update
    action items with Eisenhower classification.
    """
    event_queue = queue.Queue()

    def run_refresh():
        try:
            def on_progress(event):
                event_queue.put(event)

            orchestrator.refresh_actions(
                user_input="Refresh and prioritize action items",
                progress_callback=on_progress
            )
        except Exception as e:
            event_queue.put({"stage": "error", "status": "error", "message": str(e)})
        finally:
            event_queue.put(None)

    async def event_generator():
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()

        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: event_queue.get(timeout=0.5)
                )
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if event is None:
                break

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

**Step 2: Commit**

```bash
git add web/app.py
git commit -m "feat: add /api/stream/refresh endpoint for Action Agent SSE streaming"
```

---

### Task 10: Update MemoryWriter tool schema for source_memories

**Files:**
- Modify: `agents/memory_writer.py`

**Step 1: Add source_memories to write_memory tool schema**

In the `self.tools` list, in the `write_memory` tool definition, add a new property after `source_emails`:

```python
                        "source_memories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filepaths of related vault memories (for provenance tracking)"
                        },
```

**Step 2: Commit**

```bash
git add agents/memory_writer.py
git commit -m "feat: add source_memories field to MemoryWriter tool schema"
```

---

### Task 11: Update write_memory tool schema in MCP server

**Files:**
- Modify: `mcp_servers/memory_server.py`

**Step 1: Update write_memory tool schema and execution**

In the `list_tools()` function, update the `write_memory` tool to include the new action_required fields. Add these properties:

```python
                    "quadrant": {"type": "string", "enum": ["urgent-important", "important-not-urgent", "urgent-not-important", "neither"]},
                    "priority_justification": {"type": "string"},
                    "deadline": {"type": "string"},
                    "source_type": {"type": "string"},
                    "source_memories": {"type": "array", "items": {"type": "string"}},
```

Also update the `memory_type` enum to include `action_required`:

```python
                    "memory_type": {"type": "string", "enum": MEMORY_TYPES},
```

In the `call_tool()` function, update the `write_memory` handler to pass the new fields:

```python
    if name == "write_memory":
        filepath = write_memory(
            title=arguments['title'],
            memory_type=arguments['memory_type'],
            content=arguments['content'],
            priority=arguments.get('priority', '🟡'),
            tags=arguments.get('tags', []),
            related_to=arguments.get('related_to', []),
            source_emails=arguments.get('source_emails', []),
            quadrant=arguments.get('quadrant'),
            priority_justification=arguments.get('priority_justification'),
            deadline=arguments.get('deadline'),
            source_type=arguments.get('source_type'),
            source_memories=arguments.get('source_memories'),
        )
        return [TextContent(type="text", text=f"Memory written to: {filepath}")]
```

**Step 2: Commit**

```bash
git add mcp_servers/memory_server.py
git commit -m "feat: update MCP write_memory tool with action_required fields"
```

---

### Task 12: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update architecture, key files, and agent descriptions**

Update the Architecture section to include Action Agent and graph:

```
├── ActionAgent         → scans vault + graph, writes action_required files
│                            via MemoryMCPServer + graph tools
```

Add to Key Files table:

```
| `agents/action_agent.py` | Agent 4: generates Eisenhower-prioritized action items |
| `memory/graph.py` | Knowledge graph: build, traverse, backlink injection |
```

Update Memory Vault structure:

```
Memory Vault (memory/vault/)
  decisions/ people/ commitments/ action_required/
  _graph.json (knowledge graph adjacency map)
  Each file: YAML frontmatter + markdown body + [[wiki-links]]
```

Update Agent Descriptions table:

```
| `ActionAgent` | After build (auto) or "refresh"/"prioritize" | Reads full vault + graph, creates Eisenhower-classified action items |
```

Update Orchestrator routing description:

```
- **Orchestrator routing**: Keyword matching (`build`/`scan` → build pipeline, `refresh`/`prioritize`/`actions` → action refresh, `stats` → stats, else → query).
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Action Agent, graph module, and action_required category"
```

---

### Task 13: End-to-end verification

**Step 1: Run the full application**

```bash
python main.py
```

**Step 2: Verify vault initialization**

Check that `vault/action_required/` folder exists.

**Step 3: Test refresh flow (standalone)**

In the browser chat, type "refresh actions" or "what needs my attention". Verify:
- Orchestrator routes to ActionAgent
- ActionAgent reads vault index, graph, and individual memories
- Action items are created in `vault/action_required/` with proper format
- Each file has Eisenhower quadrant, justification, source_memories, and wiki-links

**Step 4: Test build flow (with auto-refresh)**

In the browser, trigger a build. Verify the pipeline runs 4 steps:
1. Fetch emails
2. Batch analyze
3. Memory Writer
4. Action Agent (auto-refresh)

**Step 5: Verify graph**

Check `vault/_graph.json` exists and contains:
- Nodes for all vault files
- Bidirectional edges
- Action items linked to source memories

**Step 6: Verify backlinks**

Check that files referenced by action items have been updated with backlinks in their `related_to` frontmatter.

**Step 7: Test query with graph tools**

Ask the QueryAgent: "What are my most urgent action items?" and "What is connected to Jake O'Shea?"

**Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete Action Required + Knowledge Graph implementation"
```

---

## Implementation Order Summary

| Task | Component | Depends On |
|------|-----------|-----------|
| 1 | MEMORY_TYPES config | — |
| 2 | write_memory action_required fields | Task 1 |
| 3 | memory/graph.py module | Task 1 |
| 4 | Hook graph rebuild into vault writes | Tasks 2, 3 |
| 5 | MCP server graph tools | Task 3 |
| 6 | QueryAgent graph tools | Task 3 |
| 7 | ActionAgent | Tasks 2, 3 |
| 8 | Orchestrator integration | Task 7 |
| 9 | SSE refresh endpoint | Task 8 |
| 10 | MemoryWriter source_memories | Task 2 |
| 11 | MCP server write_memory update | Task 2 |
| 12 | CLAUDE.md docs | All tasks |
| 13 | End-to-end verification | All tasks |

Tasks 1-3 can be done first (foundation). Tasks 4-7 can proceed in parallel after their dependencies. Tasks 8-11 follow. Task 12-13 are final.
