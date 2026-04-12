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

from pathlib import Path

from memory.dedup import _parse_frontmatter
from memory.vault import MEMORY_TYPES


# Vault root — same as vault.py and dedup.py.
# Patched in tests via monkeypatch for isolation.
VAULT_ROOT = Path('vault')


# ============================================================================
# UTILITIES
# ============================================================================

def _safe(value: str) -> str:
    """Escape pipe characters so they don't break markdown table structure."""
    return str(value).replace('|', '\\|')


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
    lines.append('| File | Name | Email | Organization | Role | Confidence |')
    lines.append('|------|------|-------|--------------|------|------------|')
    rows = _build_people_rows()
    if rows:
        lines.extend(rows)
    else:
        lines.append('| (none) | | | | | |')
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
    lines.append('')

    # Organizations
    org_rows = _build_organizations_rows()
    sections = lines
    sections.append("## Organizations")
    sections.append("| File | Title | Domain | Industry | Relationship |")
    sections.append("|------|-------|--------|----------|--------------|")
    if org_rows:
        sections.extend(org_rows)
    else:
        sections.append("| (none) | | | | |")

    sections.append("")

    # Projects
    proj_rows = _build_projects_rows()
    sections.append("## Projects")
    sections.append("| File | Title | Status | Type |")
    sections.append("|------|-------|--------|------|")
    if proj_rows:
        sections.extend(proj_rows)
    else:
        sections.append("| (none) | | | |")

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
        name = _safe(fm.get('name', ''))
        email = _safe(fm.get('email', ''))
        org = _safe(fm.get('organization', ''))
        role = _safe(fm.get('role', ''))
        conf = _safe(fm.get('confidence', ''))
        rows.append(f'| {rel_path} | {name} | {email} | {org} | {role} | {conf} |')
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
        title = _safe(fm.get('title', ''))
        date = _safe(fm.get('date', ''))
        # Tags is a list in frontmatter — join into comma-separated string
        tags_list = fm.get('tags', [])
        tags = _safe(', '.join(str(t) for t in tags_list) if tags_list else '')
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
        title = _safe(fm.get('title', ''))
        status = _safe(fm.get('commitment_status', ''))
        date = _safe(fm.get('date', ''))
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
        title = _safe(fm.get('title', ''))
        status = _safe(fm.get('status', ''))
        quadrant = _safe(fm.get('quadrant', ''))
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
        title = _safe(fm.get('title', ''))
        insight_type = _safe(fm.get('insight_type', ''))
        status = _safe(fm.get('status', ''))
        rows.append(f'| {rel_path} | {title} | {insight_type} | {status} |')
    return rows


def _build_organizations_rows() -> list[str]:
    """Build table rows for organization files."""
    rows = []
    org_dir = VAULT_ROOT / 'organizations'
    if not org_dir.exists():
        return rows
    for md_file in sorted(org_dir.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = _safe(fm.get('title', md_file.stem))
        domain = _safe(fm.get('domain', ''))
        industry = _safe(fm.get('industry', ''))
        rel_type = _safe(fm.get('relationship_type', ''))
        rows.append(f"| {rel_path} | {title} | {domain} | {industry} | {rel_type} |")
    return rows


def _build_projects_rows() -> list[str]:
    """Build table rows for project files."""
    rows = []
    proj_dir = VAULT_ROOT / 'projects'
    if not proj_dir.exists():
        return rows
    for md_file in sorted(proj_dir.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = _safe(fm.get('title', md_file.stem))
        status = _safe(fm.get('project_status', ''))
        ptype = _safe(fm.get('project_type', ''))
        rows.append(f"| {rel_path} | {title} | {status} | {ptype} |")
    return rows
