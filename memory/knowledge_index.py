# memory/knowledge_index.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Builds a compact markdown "catalog" of every entity in the vault. The
# MemoryWriterAgent gets this catalog injected into its prompt so the LLM
# can see what already exists BEFORE it decides to create a new file.
#
# This is a prevention-layer complement to dedup.py's detection-layer:
#   - knowledge_index.py: "Here's what exists — don't create duplicates"
#   - dedup.py:            "You created a duplicate anyway — let me merge it"
#
# The index is a lightweight scan — it only reads YAML frontmatter, never
# the full file body. This keeps it fast even with hundreds of vault files.
# ============================================================================

import yaml
from pathlib import Path


# Vault root — same as vault.py and dedup.py.
# Patched in tests via monkeypatch for isolation.
VAULT_ROOT = Path('vault')

# The five memory type folders in the vault, in display order.
# Each gets its own section in the knowledge index.
MEMORY_TYPES = [
    'people',
    'decisions',
    'commitments',
    'action_required',
    'insights',
]


# ============================================================================
# FRONTMATTER PARSING
# ============================================================================

def _parse_frontmatter(filepath: Path) -> dict:
    """
    Read a markdown file and return its YAML frontmatter as a dict.

    WHY a separate parser instead of importing vault.read_memory()?
    Because this module needs to be lightweight and self-contained —
    it's called during prompt construction, so we want minimal import
    overhead and no dependency on the full vault machinery.

    Returns empty dict on any error (missing file, bad encoding,
    malformed YAML) so callers never need to handle exceptions.
    """
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return {}

    # Frontmatter lives between two "---" markers at the top of the file.
    # Files without frontmatter are gracefully ignored.
    if not text.startswith('---'):
        return {}

    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


# ============================================================================
# INDEX BUILDER
# ============================================================================

def build_knowledge_index() -> str:
    """
    Scan the vault and build a compact markdown catalog of all entities.

    Returns a markdown string with one table per memory type. Each table
    lists the key identifying fields from frontmatter so the LLM can
    quickly check whether an entity already exists before writing.

    The tables are intentionally minimal — just enough info for entity
    resolution. The LLM doesn't need the full file content to decide
    "this person already has a file."

    Table schemas by type:
      - People:       File | Name | Email | Organization | Role
      - Decisions:    File | Title | Date | Tags
      - Commitments:  File | Title | Status | Date
      - Action Items: File | Title | Status | Quadrant
      - Insights:     File | Title | Type | Status
    """
    lines = [
        '# Knowledge Index',
        '',
        'Use this index to check if an entity already exists before creating',
        'a new memory file. Match on name (people) or title (other types).',
        '',
    ]

    # ── People ────────────────────────────────────────────────────
    lines.append('## People')
    lines.append('')
    lines.append('| File | Name | Email | Organization | Role |')
    lines.append('|------|------|-------|--------------|------|')
    rows = _build_people_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | | |')
    lines.append('')

    # ── Decisions ─────────────────────────────────────────────────
    lines.append('## Decisions')
    lines.append('')
    lines.append('| File | Title | Date | Tags |')
    lines.append('|------|-------|------|------|')
    rows = _build_decisions_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | |')
    lines.append('')

    # ── Commitments ───────────────────────────────────────────────
    lines.append('## Commitments')
    lines.append('')
    lines.append('| File | Title | Status | Date |')
    lines.append('|------|-------|--------|------|')
    rows = _build_commitments_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | |')
    lines.append('')

    # ── Action Items ──────────────────────────────────────────────
    lines.append('## Action Items')
    lines.append('')
    lines.append('| File | Title | Status | Quadrant |')
    lines.append('|------|-------|--------|----------|')
    rows = _build_action_items_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | |')
    lines.append('')

    # ── Insights ──────────────────────────────────────────────────
    lines.append('## Insights')
    lines.append('')
    lines.append('| File | Title | Type | Status |')
    lines.append('|------|-------|------|--------|')
    rows = _build_insights_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | |')

    return '\n'.join(lines)


# ============================================================================
# PER-TYPE ROW BUILDERS
# ============================================================================
# Each builder scans its folder and returns a list of markdown table row
# strings. Missing frontmatter fields default to empty string so the table
# columns always align.

def _build_people_rows() -> list[str]:
    """Build table rows for people/ folder."""
    folder = VAULT_ROOT / 'people'
    if not folder.exists():
        return []

    rows = []
    for md_file in sorted(folder.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        name = fm.get('name', '')
        email = fm.get('email', '')
        org = fm.get('organization', '')
        role = fm.get('role', '')
        rows.append(f'| {rel_path} | {name} | {email} | {org} | {role} |')
    return rows


def _build_decisions_rows() -> list[str]:
    """Build table rows for decisions/ folder."""
    folder = VAULT_ROOT / 'decisions'
    if not folder.exists():
        return []

    rows = []
    for md_file in sorted(folder.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = fm.get('title', '')
        date = fm.get('date', '')
        # Tags is a list in frontmatter — join into comma-separated string
        tags_list = fm.get('tags', [])
        tags = ', '.join(str(t) for t in tags_list) if tags_list else ''
        rows.append(f'| {rel_path} | {title} | {date} | {tags} |')
    return rows


def _build_commitments_rows() -> list[str]:
    """Build table rows for commitments/ folder."""
    folder = VAULT_ROOT / 'commitments'
    if not folder.exists():
        return []

    rows = []
    for md_file in sorted(folder.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = fm.get('title', '')
        status = fm.get('commitment_status', '')
        date = fm.get('date', '')
        rows.append(f'| {rel_path} | {title} | {status} | {date} |')
    return rows


def _build_action_items_rows() -> list[str]:
    """Build table rows for action_required/ folder."""
    folder = VAULT_ROOT / 'action_required'
    if not folder.exists():
        return []

    rows = []
    for md_file in sorted(folder.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = fm.get('title', '')
        status = fm.get('status', '')
        quadrant = fm.get('quadrant', '')
        rows.append(f'| {rel_path} | {title} | {status} | {quadrant} |')
    return rows


def _build_insights_rows() -> list[str]:
    """Build table rows for insights/ folder."""
    folder = VAULT_ROOT / 'insights'
    if not folder.exists():
        return []

    rows = []
    for md_file in sorted(folder.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = fm.get('title', '')
        insight_type = fm.get('insight_type', '')
        status = fm.get('status', '')
        rows.append(f'| {rel_path} | {title} | {insight_type} | {status} |')
    return rows
