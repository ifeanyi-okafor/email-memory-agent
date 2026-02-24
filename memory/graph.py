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

# The memory type folders to scan for graph nodes
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
    resolved_pairs = set()

    for from_path, target, relation in forward_edges:
        # Try to resolve target to a file path
        to_path = None
        if target in nodes:
            to_path = target
        else:
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
    backlink_map = {}
    for edge in edges:
        if edge['relation'] in ('backlink', 'referenced_by'):
            target_file = edge['from']
            source_file = edge['to']
            if source_file in nodes:
                source_title = nodes[source_file]['title']
                backlink_map.setdefault(target_file, set()).add(source_title)

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
            continue

        updated_related = list(existing_related | new_entries)
        frontmatter['related_to'] = sorted(updated_related)

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        body = parts[2]
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
        entity:    Starting point — filepath or entity title.
        max_depth: Maximum hops (default 2).

    Returns:
        Dict with start, nodes, edges, depth_searched.
    """
    graph = get_graph()
    nodes = graph.get('nodes', {})
    edges = graph.get('edges', [])

    # Resolve entity to filepath
    start_path = None
    if entity in nodes:
        start_path = entity
    else:
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

    # Build adjacency list
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge['from'], []).append(edge)

    # BFS
    visited = {start_path: 0}
    bfs_queue = deque([(start_path, 0)])
    reachable_edges = []

    while bfs_queue:
        current, depth = bfs_queue.popleft()
        if depth >= max_depth:
            continue

        for edge in adjacency.get(current, []):
            neighbor = edge['to']
            if neighbor not in visited:
                visited[neighbor] = depth + 1
                bfs_queue.append((neighbor, depth + 1))
            reachable_edges.append(edge)

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
