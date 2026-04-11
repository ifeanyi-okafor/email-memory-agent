# memory/vault_lint.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Pure-function lint checks for the memory vault. Scans for common
# issues like stale data, orphaned files, and empty content.
#
# These are heuristic checks — no LLM calls. The results are formatted
# into a human-readable report by the Vault Lint Agent.
# ============================================================================

import json
import re
import yaml
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path('vault')

MEMORY_TYPES = [
    'decisions', 'people', 'commitments', 'action_required',
    'insights', 'organizations', 'projects',
]


def _parse_frontmatter(filepath: Path) -> dict:
    """Read YAML frontmatter from a markdown file."""
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith('---'):
        return {}
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _parse_body(filepath: Path) -> str:
    """Read the body content (after frontmatter) from a markdown file."""
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''
    if not text.startswith('---'):
        return text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return text
    body = parts[2].strip()
    body = re.sub(r'^#\s+[^\n]+\n*', '', body).strip()
    return body


def run_lint_checks() -> list[dict]:
    """
    Run all lint checks on the vault and return a list of issues.

    Each issue is a dict with:
        check:       str — which check found the issue
        severity:    str — 'error', 'warning', or 'info'
        filepath:    str — path to the affected file (relative to vault)
        description: str — human-readable description of the issue

    Returns an empty list if the vault is clean.
    """
    issues = []
    issues.extend(_check_stale_action_items())
    issues.extend(_check_orphaned_files())
    issues.extend(_check_empty_content())
    return issues


def _check_stale_action_items() -> list[dict]:
    """Find active action items whose deadline has passed."""
    issues = []
    action_dir = VAULT_ROOT / 'action_required'
    if not action_dir.exists():
        return issues

    today = datetime.now().strftime('%Y-%m-%d')

    for md_file in action_dir.glob('*.md'):
        fm = _parse_frontmatter(md_file)
        status = fm.get('status', 'active')
        deadline = str(fm.get('deadline', ''))
        title = fm.get('title', md_file.stem)

        if status == 'active' and deadline and deadline < today:
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            issues.append({
                'check': 'stale_action_item',
                'severity': 'warning',
                'filepath': rel_path,
                'description': f'Action item "{title}" is active but past deadline ({deadline})',
            })

    return issues


def _check_orphaned_files() -> list[dict]:
    """Find files with no graph connections (no edges in or out)."""
    issues = []
    graph_file = VAULT_ROOT / '_graph.json'

    if not graph_file.exists():
        return issues

    try:
        graph = json.loads(graph_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return issues

    edges = graph.get('edges', [])
    nodes = graph.get('nodes', {})

    connected = set()
    for edge in edges:
        connected.add(edge.get('from', ''))
        connected.add(edge.get('to', ''))

    for filepath, node_data in nodes.items():
        if filepath not in connected:
            title = node_data.get('title', filepath)
            issues.append({
                'check': 'orphaned_file',
                'severity': 'info',
                'filepath': filepath,
                'description': f'File "{title}" has no connections in the knowledge graph',
            })

    return issues


def _check_empty_content() -> list[dict]:
    """Find files with no meaningful body content."""
    issues = []

    for mtype in MEMORY_TYPES:
        folder = VAULT_ROOT / mtype
        if not folder.exists():
            continue

        for md_file in folder.glob('*.md'):
            body = _parse_body(md_file)
            fm = _parse_frontmatter(md_file)
            title = fm.get('title') or fm.get('name', md_file.stem)

            if not body.strip():
                rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
                issues.append({
                    'check': 'empty_content',
                    'severity': 'warning',
                    'filepath': rel_path,
                    'description': f'File "{title}" has no body content (only frontmatter)',
                })

    return issues
