# memory/vault.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "filing cabinet" of our system. It manages the memory vault —
# a set of folders and markdown files that store everything the AI learns
# about you from your emails.
#
# It handles:
#   - Creating the folder structure (decisions/, people/, commitments/)
#   - Writing new memory files with proper formatting (YAML + markdown)
#   - Reading existing memories back
#   - Searching through all memories by text
#   - Maintaining a master index (a table of contents for the whole vault)
#
# IMPORTANT: This file has NO artificial intelligence in it.
# It's pure file operations — creating files, reading files, searching text.
# The AI agents decide WHAT to store. This file handles HOW to store it.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "os" lets us interact with the operating system (not used much here but
# available for file checks)
import os
import json

# "re" stands for "regular expressions" — a powerful tool for searching
# and manipulating text patterns. We use it to create clean filenames
# and update the vault index.
import re

# "hashlib" provides hashing functions. A "hash" is like a fingerprint
# for data — it turns any text into a short, unique code. We use it
# to make sure filenames are unique.
import hashlib

# "datetime" lets us work with dates and times. We stamp every memory
# with the date it was created.
from datetime import datetime

# "Path" makes file path handling easy and cross-platform.
from pathlib import Path

# "yaml" lets us read and write YAML — a human-friendly data format.
# We use it for the "frontmatter" (metadata) at the top of each memory file.
# YAML looks like this:
#   title: "My Memory"
#   date: 2026-02-19
#   tags: [work, meetings]
import yaml

from memory.changelog import append_changelog


# ── CONSTANTS ──────────────────────────────────────────────────────────

# "VAULT_ROOT" is the folder where all memory files are stored.
# It's a folder called "vault" in the project root.
VAULT_ROOT = Path('vault')

# "MEMORY_TYPES" is the list of all valid memory categories.
# Each one gets its own subfolder inside the vault.
# This is the "taxonomy" — the classification system for memories.
MEMORY_TYPES = [
    'decisions',        # Choices: "chose React over Vue"
    'people',           # Contacts: "Sarah — CTO at Acme"
    'commitments',      # Promises: "review PRs by Friday"
    'action_required',  # Action items: prioritized by Eisenhower matrix
    'insights',         # Cross-correlation intelligence
    'organizations',    # Companies, teams, institutions the user interacts with
    'projects',         # Initiatives, deals, products the user is involved in
]


# ============================================================================
# VAULT INITIALIZATION
# ============================================================================

def initialize_vault():
    """
    Create the vault folder structure if it doesn't already exist.

    This is like setting up a new filing cabinet: we create a drawer
    (folder) for each category of memory, plus a master index file.

    After running, the vault looks like this:
        vault/
        ├── decisions/
        ├── people/
        ├── commitments/
        └── _index.md             ← Master table of contents

    Returns:
        str: The path to the vault root folder.
    """
    print("[*] Initializing memory vault...")

    # Loop through each memory type and create its folder
    for memory_type in MEMORY_TYPES:
        # Build the full path: vault/decisions, vault/people, etc.
        folder = VAULT_ROOT / memory_type

        # "mkdir" creates the folder.
        # "parents=True" means: also create parent folders if needed.
        # "exist_ok=True" means: don't crash if the folder already exists.
        folder.mkdir(parents=True, exist_ok=True)

    # Create the vault index file if it doesn't exist yet
    # The index is a markdown file that lists every memory — like a
    # table of contents for the whole vault.
    index_path = VAULT_ROOT / '_index.md'
    if not index_path.exists():
        _write_initial_index()

    print("[OK] Memory vault ready!")

    # Return the vault path as a string
    return str(VAULT_ROOT)


def _write_initial_index():
    """
    Create the initial (empty) vault index file.

    The index is a markdown file with a table. Each row in the table
    represents one memory file. When the vault is brand new, the table
    is empty — it fills up as we add memories.

    The underscore prefix "_" means this is a private helper function.
    """
    # Get today's date formatted as "2026-02-19"
    date = datetime.now().strftime('%Y-%m-%d')

    # Build the initial content of the index file.
    # It has YAML frontmatter (between --- markers) and a markdown table.
    content = f"""---
title: "Vault Index"
description: "Master index of all memories in this vault"
last_updated: "{date}"
---

# Memory Vault Index

This file is automatically maintained. It lists every memory in the vault
with a one-line description for fast lookup.

| File | Type | Description | Date |
|------|------|-------------|------|
"""
    # Write the content to the index file
    (VAULT_ROOT / '_index.md').write_text(content, encoding='utf-8')


# ============================================================================
# FILENAME GENERATION
# ============================================================================

def _slugify(text: str) -> str:
    """
    Convert a human-readable title into a safe filename.

    Example:
        "Prefers dark mode in all IDEs" → "prefers-dark-mode-in-all-ides-a1b2"

    WHY do we need this?
    Filenames can't contain spaces, question marks, slashes, etc.
    This function strips all that out and produces a clean, lowercase,
    hyphen-separated name that works on every operating system.

    We also add a 4-character hash at the end for uniqueness — in the
    rare case that two different titles produce the same slug.

    Args:
        text: The human-readable title to convert.

    Returns:
        A filename-safe string like "prefers-morning-meetings-a1b2"
    """
    # Step 1: Convert to lowercase and replace any non-letter/non-number
    # characters with hyphens.
    # "re.sub" means "substitute" — it finds all matches of a pattern
    # and replaces them. "[^a-z0-9]+" means "one or more characters that
    # are NOT lowercase letters or digits."
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower())

    # Step 2: Remove leading/trailing hyphens (cleanup)
    slug = slug.strip('-')

    # Step 3: Truncate to 60 characters max (filenames shouldn't be too long)
    slug = slug[:60]

    # Step 4: Add a short hash for uniqueness.
    # "md5" creates a fingerprint of the original text, and we take the
    # first 4 characters. This means even if two titles produce the same
    # slug, the hash will make them different.
    short_hash = hashlib.md5(text.encode()).hexdigest()[:4]

    # Combine slug + hash: "prefers-morning-meetings" + "-" + "a1b2"
    return f"{slug}-{short_hash}"


# ============================================================================
# WRITING MEMORIES
# ============================================================================

def write_memory(
    title: str,
    memory_type: str,
    content: str,
    priority: str = '🟡',
    tags: list[str] = None,
    related_to: list[str] = None,
    source_emails: list[str] = None,
    # Action Required-specific fields (optional, only used when memory_type == 'action_required')
    quadrant: str = None,
    priority_justification: str = None,
    deadline: str = None,
    source_type: str = None,
    source_memories: list[str] = None,
    # Status tracking fields (for action_required reconciliation and insights)
    status: str = None,
    status_reason: str = None,
    status_updated: str = None,
    # Commitment-specific fields (optional, only used when memory_type == 'commitments')
    commitment_status: str = None,
    # Insights-specific fields (optional, only used when memory_type == 'insights')
    insight_type: str = None,
    confidence: str = None,
    # People-specific fields (optional, only used when memory_type == 'people')
    name: str = None,
    role: str = None,
    organization: str = None,
    email: str = None,
    phone: str = None,
    location: str = None,
    timezone: str = None,
    # Organization-specific fields (optional, only used when memory_type == 'organizations')
    org_domain: str = None,
    org_industry: str = None,
    org_relationship: str = None,
    # Project-specific fields (optional, only used when memory_type == 'projects')
    project_status: str = None,
    project_type: str = None,
) -> str:
    """
    Create or update a memory file in the vault.

    For most memory types, this creates a markdown file with YAML frontmatter,
    a title heading, wiki-links, and content.

    For "people" memories, a richer frontmatter is used with contact/professional
    fields. If a person file already exists, the original creation date is
    preserved and an "updated" timestamp is set.

    Args:
        title:         A clear, descriptive title for this memory.
                       For people: "FirstName LastName — Role".
        memory_type:   Which category this belongs to (must be one of MEMORY_TYPES).
        content:       The markdown text content of the memory.
        priority:      Importance level — 🔴 Critical, 🟡 Notable, 🟢 Reflection.
        tags:          Keyword tags for searching (e.g., ["scheduling", "work"]).
        related_to:    Names of related entities — these become [[wiki-links]].
        source_emails: Subject lines of emails this memory came from.
        name:          (People only) Override the display name in frontmatter.
                       If not provided, name is derived from the title.
                       Useful for "Me" files where the title is "Me — Role" but
                       the frontmatter should show the person's actual name.
        role:          (People only) Person's job title/role.
        organization:  (People only) Person's company or organization.
        email:         (People only) Person's email address.
        phone:         (People only) Person's phone number.
        location:      (People only) Person's city/region.
        timezone:      (People only) Person's timezone.

    Returns:
        str: The file path where the memory was saved.

    Raises:
        ValueError: If memory_type is not one of the valid types.
    """

    # ── Validate the memory type ───────────────────────────────
    if memory_type not in MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory type '{memory_type}'. "
            f"Must be one of: {MEMORY_TYPES}"
        )

    # ── Check for existing duplicate ─────────────────────────────
    # Programmatic safety net: catch duplicates the LLM missed.
    # If a matching file already exists, redirect the write there
    # instead of creating a new file with a different slug.
    from memory.dedup import find_duplicate, merge_contents as dedup_merge, clean_person_name

    duplicate_path = find_duplicate(title, memory_type, name=name)

    if duplicate_path and duplicate_path.exists():
        # Build the new frontmatter dict for merging
        new_fm = {'tags': tags or [], 'related_to': related_to or []}
        if source_emails:
            new_fm['source_emails'] = source_emails
        if memory_type == 'commitments' and commitment_status:
            new_fm['commitment_status'] = commitment_status
        if memory_type == 'people':
            # Include people-specific scalar fields so merge can fill gaps
            for field_name, field_val in [
                ('role', role), ('organization', organization),
                ('email', email), ('phone', phone),
                ('location', location), ('timezone', timezone),
            ]:
                if field_val:
                    new_fm[field_name] = field_val

        merged_fm, merged_body = dedup_merge(duplicate_path, content, new_fm)

        # Preserve merged values for the write below
        tags = merged_fm.get('tags', tags)
        related_to = merged_fm.get('related_to', related_to)
        if not source_emails and merged_fm.get('source_emails'):
            source_emails = merged_fm['source_emails']
        content = merged_body

        # For people, also pull back merged scalar fields
        if memory_type == 'people':
            role = merged_fm.get('role') or role
            organization = merged_fm.get('organization') or organization
            email = merged_fm.get('email') or email
            phone = merged_fm.get('phone') or phone
            location = merged_fm.get('location') or location
            timezone = merged_fm.get('timezone') or timezone

        filepath = duplicate_path
        print(f"   [DEDUP] Found existing file, updating: {filepath}")
    else:
        # ── Generate the filename ──────────────────────────────────
        # For "people" memories, use just the person's name (before the " — ")
        # so files are named like "sarah-chen-a1b2.md" instead of
        # "sarah-chen-cto-at-acme-a1b2.md"
        if memory_type == 'people' and ' — ' in title:
            name_part = title.split(' — ')[0].strip()
            # "Me" is a singleton (the primary user) — use a clean filename
            # without the hash suffix, producing "me.md" instead of "me-ab86.md"
            if name_part.lower() == 'me':
                slug = 'me'
            else:
                slug = _slugify(name_part)
        else:
            slug = _slugify(title)
        filename = f"{slug}.md"
        filepath = VAULT_ROOT / memory_type / filename

    # ── Build the YAML frontmatter ─────────────────────────────
    today = datetime.now().strftime('%Y-%m-%d')

    if memory_type == 'people':
        # ── People-specific frontmatter ────────────────────────
        # Use the explicit name parameter if provided (e.g., "John Doe" for "Me" files).
        # Otherwise, extract from "FirstName LastName — Role" format.
        if not name:
            name = title.split(' — ')[0].strip() if ' — ' in title else title

        # Clean the name: strip titles, roles, organizations.
        # "Kate Lee - Editor in Chief at Every" → "Kate Lee"
        # The role/org info belongs in the `role` and `organization` fields, not in the name.
        name = clean_person_name(name)

        # If file already exists, preserve the original creation date
        # so we can track when we first learned about this person.
        original_date = today
        if filepath.exists():
            try:
                text = filepath.read_text(encoding='utf-8')
                if text.startswith('---'):
                    parts = text.split('---', 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1]) or {}
                        original_date = fm.get('date', today)
            except Exception:
                pass

        frontmatter = {
            'name': name,
            'date': original_date,
            'updated': today,
            'category': 'people',
            'memoryType': 'person',
            'priority': priority,
            'role': role or '',
            'organization': organization or '',
            'email': email or '',
            'phone': phone or '',
            'location': location or '',
            'timezone': timezone or '',
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

        # People files use the name as heading, and the content
        # contains the full structured template (## Overview, etc.)
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        file_content = f"""---
{yaml_str.strip()}
---

# {name}

{content}
"""

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
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
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

    elif memory_type == 'insights':
        # ── Insights-specific frontmatter ─────────────────────
        # Insights are cross-correlation intelligence derived from the vault.
        # They have an insight_type (relationship/execution_gap/strategic_pattern),
        # a confidence level (high/medium), and a status (active/dismissed).
        frontmatter = {
            'title': title,
            'date': today,
            'category': 'insights',
            'memoryType': 'insights',
            'priority': priority,
            'insight_type': insight_type or 'strategic_pattern',
            'confidence': confidence or 'medium',
            'status': status or 'active',
            'source_memories': source_memories or [],
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

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

    elif memory_type == 'organizations':
        # ── Organization-specific frontmatter ─────────────────
        # Organizations are companies, teams, or institutions the user
        # interacts with. They have a domain, industry, and relationship type.
        frontmatter = {
            'title': title,
            'date': today,
            'updated': today,
            'category': 'organizations',
            'memoryType': 'organizations',
            'priority': priority,
            'domain': org_domain or '',
            'industry': org_industry or '',
            'relationship_type': org_relationship or '',
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

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

    elif memory_type == 'projects':
        # ── Project-specific frontmatter ──────────────────────
        # Projects are initiatives, deals, or products the user tracks.
        # They have a status lifecycle and a type classification.
        frontmatter = {
            'title': title,
            'date': today,
            'updated': today,
            'category': 'projects',
            'memoryType': 'projects',
            'priority': priority,
            'project_status': project_status or 'active',
            'project_type': project_type or '',
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

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

    elif memory_type == 'commitments':
        # ── Commitment-specific frontmatter ─────────────────────
        # Includes commitment_status to track participation lifecycle:
        # invited → confirmed → declined/tentative
        frontmatter = {
            'title': title,
            'date': today,
            'category': 'commitments',
            'memoryType': 'commitments',
            'priority': priority,
            'commitment_status': commitment_status or 'invited',
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

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

    else:
        # ── Standard frontmatter for other memory types (decisions, etc.) ──
        frontmatter = {
            'title': title,
            'date': today,
            'category': memory_type,
            'memoryType': memory_type,
            'priority': priority,
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

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

    # ── Write to disk ──────────────────────────────────────────
    filepath.write_text(file_content, encoding='utf-8')

    # ── Update the master index ────────────────────────────────
    update_index(
        filepath=str(filepath.relative_to(VAULT_ROOT)),
        memory_type=memory_type,
        description=title,
    )

    # ── Rebuild the knowledge graph ─────────────────────────────
    # This keeps the graph index up-to-date with every write,
    # including injecting backlinks into related files.
    from memory.graph import rebuild_graph
    rebuild_graph()

    # ── Log to changelog ───────────────────────────────────────
    # Determine if this was a create or update.
    # A write is an UPDATE if:
    #   - We found a duplicate and redirected to an existing file, OR
    #   - For people files, the original_date differs from today (file existed)
    is_update = duplicate_path is not None if 'duplicate_path' in locals() else False
    if not is_update and memory_type == 'people':
        is_update = (original_date != today)
    action = "UPDATED" if is_update else "CREATED"

    rel_path = filepath.relative_to(VAULT_ROOT).as_posix()
    description = name if (memory_type == 'people' and name) else title
    append_changelog(action, rel_path, description)

    print(f"   [{action}] Written: {filepath}")

    return str(filepath)


# ============================================================================
# READING MEMORIES
# ============================================================================

def read_memory(filepath: str) -> dict | None:
    """
    Read a memory file and return its metadata and content separately.

    This function opens a memory file, splits it into two parts:
    1. The YAML frontmatter (structured metadata)
    2. The markdown content (the actual memory text)

    Args:
        filepath: Path to the memory file. Can be:
                  - Relative to vault: "people/sarah-chen-a1b2.md"
                  - Absolute: "/home/user/project/vault/people/sarah-chen-a1b2.md"

    Returns:
        A dictionary with three keys:
        {
            'frontmatter': {...},  ← The YAML metadata as a Python dict
            'content': '...',      ← The markdown body as a string
            'filepath': '...'      ← The full file path
        }
        Returns None if the file doesn't exist.
    """
    # Convert the string path to a Path object for easier handling
    full_path = Path(filepath)

    # If the path isn't absolute, assume it's relative to the vault root
    if not full_path.is_absolute():
        full_path = VAULT_ROOT / filepath

    # Check if the file exists
    if not full_path.exists():
        return None

    # Read the entire file as text
    text = full_path.read_text(encoding='utf-8')

    # ── Parse the YAML frontmatter ─────────────────────────────
    # Frontmatter is the section between two "---" lines at the top.
    # We need to split it from the rest of the content.
    frontmatter = {}  # Default: empty metadata
    content = text     # Default: entire file is content

    # Check if the file starts with "---" (has frontmatter)
    if text.startswith('---'):
        # Split on "---" — this gives us: ['', 'yaml stuff', 'content stuff']
        parts = text.split('---', 2)  # Split into at most 3 parts

        if len(parts) >= 3:
            try:
                # Parse the YAML section (parts[1]) into a Python dictionary
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                # If the YAML is malformed, just skip it
                pass
            # The content is everything after the second "---"
            content = parts[2].strip()

    # Return the parsed result
    return {
        'frontmatter': frontmatter,
        'content': content,
        'filepath': str(full_path),
    }


def list_memories(memory_type: str = None) -> list[dict]:
    """
    List all memories in the vault, with basic info about each one.

    This is like looking at the spines of books on a shelf — you see
    the title and category without reading the full content.

    Args:
        memory_type: Optional filter. Pass "people" to only list people
                     memories. Pass None to list everything.

    Returns:
        A list of dictionaries, each with:
        {
            'filepath': 'people/sarah-chen-a1b2.md',
            'type': 'people',
            'title': 'Sarah Chen — CTO at Acme',
            'date': '2026-02-19',
            'priority': '🟡',
            'tags': ['contact', 'work']
        }
    """
    # "memories" will collect all the results
    memories = []

    # Decide which folders to scan: just one type, or all of them
    types_to_scan = [memory_type] if memory_type else MEMORY_TYPES

    # Loop through each memory type folder
    for mtype in types_to_scan:
        # Build the folder path: vault/people, vault/decisions, etc.
        folder = VAULT_ROOT / mtype

        # Skip if the folder doesn't exist
        if not folder.exists():
            continue

        # Find all .md files in the folder, sorted alphabetically
        # "glob('*.md')" means "find all files ending in .md"
        for md_file in sorted(folder.glob('*.md')):
            # Read the file to get its frontmatter.
            # Pass path relative to VAULT_ROOT ("people/file.md") so that
            # read_memory() doesn't double-prepend the vault prefix.
            mem = read_memory(str(md_file.relative_to(VAULT_ROOT)))

            if mem:
                # Add a summary entry (not the full content)
                memories.append({
                    'filepath': md_file.relative_to(VAULT_ROOT).as_posix(),
                    'type': mtype,
                    # People files use 'name' in frontmatter; others use 'title'
                    'title': mem['frontmatter'].get('title') or mem['frontmatter'].get('name', md_file.stem),
                    'date': mem['frontmatter'].get('date', ''),
                    'priority': mem['frontmatter'].get('priority', ''),
                    'tags': mem['frontmatter'].get('tags', []),
                    'status': mem['frontmatter'].get('status') if mtype in ('action_required', 'insights') else None,
                    'status_reason': mem['frontmatter'].get('status_reason') if mtype == 'action_required' else None,
                    'quadrant': mem['frontmatter'].get('quadrant') if mtype == 'action_required' else None,
                    'deadline': mem['frontmatter'].get('deadline') if mtype == 'action_required' else None,
                    'commitment_status': mem['frontmatter'].get('commitment_status') if mtype == 'commitments' else None,
                    'insight_type': mem['frontmatter'].get('insight_type') if mtype == 'insights' else None,
                    'confidence': mem['frontmatter'].get('confidence') if mtype == 'insights' else None,
                    'domain': mem['frontmatter'].get('domain') if mtype == 'organizations' else None,
                    'industry': mem['frontmatter'].get('industry') if mtype == 'organizations' else None,
                    'relationship_type': mem['frontmatter'].get('relationship_type') if mtype == 'organizations' else None,
                    'project_status': mem['frontmatter'].get('project_status') if mtype == 'projects' else None,
                    'project_type': mem['frontmatter'].get('project_type') if mtype == 'projects' else None,
                })

    return memories


# ============================================================================
# SEARCHING
# ============================================================================

def search_vault(query: str) -> list[dict]:
    """
    Search across all memories using simple text matching.

    This is the "grep" approach — surprisingly effective! The ClawVault
    research found that simple text search outperforms complex vector
    databases for LLM-based memory systems.

    HOW IT WORKS:
    1. Loop through every .md file in every memory folder
    2. Read the file's text
    3. Check if the search query appears anywhere in the text
    4. If yes, extract a snippet around the match and add it to results

    Args:
        query: The text to search for (case-insensitive).
               Example: "morning meetings"

    Returns:
        A list of matching memories with a relevant text snippet.
    """
    # Convert query to lowercase for case-insensitive matching
    query_lower = query.lower()

    # "results" will hold all matching memories
    results = []

    # Search through every memory type folder
    for memory_type in MEMORY_TYPES:
        folder = VAULT_ROOT / memory_type

        # Skip if folder doesn't exist
        if not folder.exists():
            continue

        # Check every .md file in this folder
        for md_file in folder.glob('*.md'):
            # Read the file's text
            text = md_file.read_text(encoding='utf-8')

            # Convert to lowercase for comparison
            text_lower = text.lower()

            # Check if our query appears in this file
            if query_lower in text_lower:
                # ── Extract a snippet around the match ─────────
                # Find where the match starts in the text
                idx = text_lower.find(query_lower)

                # Take 100 characters before and after the match for context
                start = max(0, idx - 100)
                end = min(len(text), idx + len(query) + 100)
                snippet = text[start:end].strip()

                # Read the file's frontmatter for metadata
                mem = read_memory(str(md_file.relative_to(VAULT_ROOT)))

                # Add to results with the snippet
                results.append({
                    'filepath': md_file.relative_to(VAULT_ROOT).as_posix(),
                    'type': memory_type,
                    # People files use 'name' in frontmatter; others use 'title'
                    'title': mem['frontmatter'].get('title') or mem['frontmatter'].get('name', md_file.stem),
                    'snippet': f"...{snippet}...",
                    'priority': mem['frontmatter'].get('priority', ''),
                })

    return results


# ============================================================================
# INDEX MANAGEMENT
# ============================================================================

def get_vault_index() -> str:
    """
    Read and return the full vault index file as a string.

    The index is the master table of contents listing every memory.
    """
    index_path = VAULT_ROOT / '_index.md'
    if index_path.exists():
        return index_path.read_text(encoding='utf-8')
    return "Vault index not found."


def update_index(filepath: str, memory_type: str, description: str):
    """
    Add or update an entry in the vault index table.

    Every time we write a new memory, we add a row to _index.md.
    If the memory already exists (by filepath), we update the existing row
    instead of creating a duplicate.

    Args:
        filepath:     Path of the memory file relative to vault root
        memory_type:  Which category (decisions, people, etc.)
        description:  One-line description (usually the memory's title)
    """
    # Read the current index content
    index_path = VAULT_ROOT / '_index.md'
    content = index_path.read_text(encoding='utf-8')

    # Build the new row for the markdown table
    date = datetime.now().strftime('%Y-%m-%d')
    new_row = f"| {filepath} | {memory_type} | {description} | {date} |"

    # Check if this file already has a row in the index
    if filepath in content:
        # UPDATE existing row: find the line with this filepath and replace it
        lines = content.split('\n')
        updated_lines = []
        for line in lines:
            if filepath in line:
                updated_lines.append(new_row)  # Replace old row
            else:
                updated_lines.append(line)      # Keep everything else
        content = '\n'.join(updated_lines)
    else:
        # ADD new row: append to the end of the file
        content = content.rstrip() + '\n' + new_row + '\n'

    # Update the "last_updated" date in the frontmatter
    content = re.sub(
        r'last_updated: ".*?"',           # Find the old date
        f'last_updated: "{date}"',         # Replace with today
        content
    )

    # Write the updated index back to disk
    index_path.write_text(content, encoding='utf-8')


# ============================================================================
# STATISTICS
# ============================================================================

def get_vault_stats() -> dict:
    """
    Count how many memories exist in each category.

    Returns:
        A dictionary like:
        {
            'total': 8,
            'decisions': 3,
            'people': 4,
            'commitments': 1,
        }
    """
    # Start with a total counter at zero
    stats = {'total': 0}

    # Count .md files in each memory type folder
    for mtype in MEMORY_TYPES:
        folder = VAULT_ROOT / mtype

        # Count files if folder exists, otherwise 0
        count = len(list(folder.glob('*.md'))) if folder.exists() else 0

        # Store the count for this type
        stats[mtype] = count

        # Add to the running total
        stats['total'] += count

    return stats


# ============================================================================
# PROCESSED EMAIL TRACKING
# ============================================================================

# This file tracks which Gmail message IDs have already been processed,
# so we can skip them on subsequent builds (incremental processing).
PROCESSED_EMAILS_FILE = VAULT_ROOT / "_processed_emails.json"


def get_processed_email_ids() -> set:
    """
    Load the set of already-processed Gmail message IDs.

    Returns an empty set if the tracking file doesn't exist yet
    (first run) or if there's any error reading it.
    """
    if not PROCESSED_EMAILS_FILE.exists():
        return set()
    try:
        with open(PROCESSED_EMAILS_FILE, 'r') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        return set()


def save_processed_email_ids(ids: set):
    """
    Save the set of processed Gmail message IDs to disk.

    Stores as a sorted JSON array so the file is human-readable
    and deterministic (same IDs always produce the same file).
    """
    PROCESSED_EMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_EMAILS_FILE, 'w') as f:
        json.dump(sorted(ids), f)
