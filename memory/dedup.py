# memory/dedup.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Programmatic deduplication for the memory vault. Catches duplicate files
# that the LLM misses when it generates slightly different titles for the
# same entity across processing batches.
#
# Two matching strategies:
#   - People: exact match on the `name` frontmatter field (case-insensitive)
#   - Non-people: normalized title containment + fuzzy matching (SequenceMatcher)
#
# Also provides merge logic and a one-time cleanup function for existing dupes.
# ============================================================================

import re
import yaml
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

# Vault root — same as vault.py
VAULT_ROOT = Path('vault')

# Words stripped during title normalization (common email prefixes + articles)
FILLER_WORDS = {'the', 'a', 'an', 're', 'fw', 'fwd'}

# Fuzzy match threshold — titles with SequenceMatcher ratio >= this are dupes
FUZZY_THRESHOLD = 0.70

# Content similarity threshold — below this, new content is appended during merge
CONTENT_SIMILARITY_THRESHOLD = 0.85


# ============================================================================
# TITLE NORMALIZATION
# ============================================================================

def normalize_title(title: str) -> str:
    """
    Normalize a title for comparison: lowercase, strip punctuation,
    remove filler words, collapse whitespace.

    Examples:
        "Re: AI/TX February Meetup!"  →  "ai tx february meetup"
        "The Contract Review — Alice"  →  "contract review alice"
    """
    # Lowercase
    text = title.lower()

    # Replace punctuation and special chars with spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)

    # Split into words, remove filler words, rejoin
    words = [w for w in text.split() if w not in FILLER_WORDS]

    return ' '.join(words)


# ============================================================================
# FRONTMATTER PARSING (lightweight, no full vault.read_memory dependency)
# ============================================================================

def _parse_frontmatter(filepath: Path) -> dict:
    """
    Read a markdown file and return its YAML frontmatter as a dict.
    Returns empty dict on any error.
    """
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
    """
    Read a markdown file and return the body (everything after frontmatter).
    """
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''

    if not text.startswith('---'):
        return text

    parts = text.split('---', 2)
    if len(parts) < 3:
        return text

    return parts[2].strip()


# ============================================================================
# DUPLICATE FINDING
# ============================================================================

def find_duplicate(title: str, memory_type: str, name: str = None) -> Path | None:
    """
    Search the vault for an existing file that matches the given title/name.

    For people: match on the `name` frontmatter field (case-insensitive).
    For non-people: match on normalized title containment or fuzzy similarity.

    Args:
        title:       The title of the new memory being written.
        memory_type: The memory type folder to search in.
        name:        (People only) Explicit name override.

    Returns:
        Path to the existing duplicate file, or None if no duplicate found.
    """
    folder = VAULT_ROOT / memory_type

    if not folder.exists():
        return None

    if memory_type == 'people':
        return _find_people_duplicate(title, name, folder)
    else:
        return _find_non_people_duplicate(title, memory_type, folder)


def _find_people_duplicate(title: str, name: str | None, folder: Path) -> Path | None:
    """
    Find a duplicate people file by matching the `name` frontmatter field.

    The incoming name is derived from the `name` parameter if provided,
    otherwise extracted from the title before " — ".
    """
    # Determine the search name
    if name:
        search_name = name.strip().lower()
    elif ' — ' in title:
        search_name = title.split(' — ')[0].strip().lower()
    else:
        search_name = title.strip().lower()

    for md_file in folder.glob('*.md'):
        fm = _parse_frontmatter(md_file)
        existing_name = str(fm.get('name', '')).strip().lower()

        if existing_name and existing_name == search_name:
            return md_file

    return None


def _find_non_people_duplicate(title: str, memory_type: str, folder: Path) -> Path | None:
    """
    Find a duplicate non-people file by normalized title containment,
    word-set overlap, or fuzzy matching (SequenceMatcher >= FUZZY_THRESHOLD).

    Multiple strategies are used to handle:
    - Different word order: "AITX Meetup Feb" vs "Feb Meetup AITX"
    - Acronym splitting: "AITX" vs "AI/TX"
    - Extra/missing words: "AITX Meetup" vs "AITX February Meetup RSVP"
    """
    incoming_norm = normalize_title(title)

    if not incoming_norm:
        return None

    incoming_compact = incoming_norm.replace(' ', '')
    incoming_words = set(incoming_norm.split())

    for md_file in folder.glob('*.md'):
        fm = _parse_frontmatter(md_file)
        existing_title = fm.get('title', '')
        if not existing_title:
            continue

        existing_norm = normalize_title(existing_title)
        if not existing_norm:
            continue

        existing_compact = existing_norm.replace(' ', '')
        existing_words = set(existing_norm.split())

        # Check 1: normalized containment (either direction)
        # Try with spaces first, then without (handles AI/TX vs AITX)
        if (incoming_norm in existing_norm or existing_norm in incoming_norm or
                incoming_compact in existing_compact or existing_compact in incoming_compact):
            return md_file

        # Check 2: word-set overlap (handles different word order)
        # If the smaller set's words are mostly in the larger set, it's a dupe.
        smaller = incoming_words if len(incoming_words) <= len(existing_words) else existing_words
        larger = incoming_words if len(incoming_words) > len(existing_words) else existing_words
        if smaller and len(smaller & larger) / len(smaller) >= FUZZY_THRESHOLD:
            return md_file

        # Check 3: sorted-word fuzzy similarity (handles different word order
        # plus acronym variations — sorting removes order sensitivity,
        # SequenceMatcher handles partial matches like "aitx" ≈ "ai" + "tx")
        incoming_sorted = ' '.join(sorted(incoming_words))
        existing_sorted = ' '.join(sorted(existing_words))
        sorted_ratio = SequenceMatcher(None, incoming_sorted, existing_sorted).ratio()
        if sorted_ratio >= FUZZY_THRESHOLD:
            return md_file

        # Check 4: raw fuzzy similarity (with and without spaces)
        ratio = SequenceMatcher(None, incoming_norm, existing_norm).ratio()
        if ratio >= FUZZY_THRESHOLD:
            return md_file

        compact_ratio = SequenceMatcher(None, incoming_compact, existing_compact).ratio()
        if compact_ratio >= FUZZY_THRESHOLD:
            return md_file

    return None


# ============================================================================
# CONTENT MERGING
# ============================================================================

def merge_contents(
    existing_path: Path,
    new_content: str,
    new_frontmatter: dict,
) -> tuple[dict, str]:
    """
    Merge new data into an existing memory file.

    Frontmatter: union tags/related_to, fill empty fields, update timestamp.
    Content: for people files append Key Interactions; for others append if
    substantially different.

    Args:
        existing_path:    Path to the existing vault file.
        new_content:      The new markdown body content.
        new_frontmatter:  Dict of new frontmatter fields to merge.

    Returns:
        (merged_frontmatter, merged_body_content)
    """
    existing_fm = _parse_frontmatter(existing_path)
    existing_body = _parse_body(existing_path)

    # ── Merge frontmatter ─────────────────────────────────────
    merged_fm = dict(existing_fm)

    for key, new_val in new_frontmatter.items():
        if key in ('tags', 'related_to', 'source_emails', 'source_memories'):
            # List fields: union as sets
            existing_list = merged_fm.get(key, []) or []
            new_list = new_val if isinstance(new_val, list) else []
            merged_fm[key] = sorted(set(existing_list) | set(new_list))
        elif not merged_fm.get(key) and new_val:
            # Scalar fields: only fill if existing is empty/falsy
            merged_fm[key] = new_val

    # Always update the 'updated' timestamp
    merged_fm['updated'] = datetime.now().strftime('%Y-%m-%d')

    # ── Merge body content ────────────────────────────────────
    memory_type = merged_fm.get('category', merged_fm.get('memoryType', ''))

    if memory_type in ('people', 'person'):
        merged_body = _merge_people_content(existing_body, new_content)
    else:
        merged_body = _merge_generic_content(existing_body, new_content)

    return merged_fm, merged_body


def _merge_people_content(existing_body: str, new_body: str) -> str:
    """
    Merge people content: append new Key Interactions entries.
    """
    # Extract Key Interactions from new content
    new_interactions = _extract_section(new_body, '## Key Interactions')

    if not new_interactions.strip():
        return existing_body

    # If existing body already has Key Interactions, append to it
    if '## Key Interactions' in existing_body:
        # Find the end of the Key Interactions section (next ## or end of file)
        ki_start = existing_body.index('## Key Interactions')
        rest_after_ki = existing_body[ki_start + len('## Key Interactions'):]

        # Find next ## heading after Key Interactions
        next_section = re.search(r'\n## (?!Key Interactions)', rest_after_ki)
        if next_section:
            insert_point = ki_start + len('## Key Interactions') + next_section.start()
            merged = (
                existing_body[:insert_point].rstrip() + '\n\n' +
                new_interactions.strip() + '\n\n' +
                existing_body[insert_point:]
            )
        else:
            merged = existing_body.rstrip() + '\n\n' + new_interactions.strip()

        return merged
    else:
        # No existing Key Interactions — append the whole section
        return existing_body.rstrip() + '\n\n## Key Interactions\n\n' + new_interactions.strip()


def _merge_generic_content(existing_body: str, new_body: str) -> str:
    """
    Merge non-people content: append new body if substantially different.

    Strips the leading `# Heading` line from existing body before comparing,
    since existing_body includes it but new_body typically doesn't.
    """
    if not new_body.strip():
        return existing_body

    # Strip leading # heading from existing body for fair comparison
    existing_for_compare = re.sub(r'^#\s+[^\n]+\n*', '', existing_body.strip()).strip()
    new_for_compare = new_body.strip()

    # Check similarity
    ratio = SequenceMatcher(None, existing_for_compare, new_for_compare).ratio()

    if ratio >= CONTENT_SIMILARITY_THRESHOLD:
        # Content is too similar — keep existing
        return existing_body

    # Append new content under a separator
    return existing_body.rstrip() + '\n\n---\n\n' + new_body.strip()


def _extract_section(text: str, heading: str) -> str:
    """
    Extract the content under a specific markdown ## heading.
    Returns everything between the heading and the next ## heading (or end of text).
    """
    if heading not in text:
        return ''

    start = text.index(heading) + len(heading)
    rest = text[start:]

    # Find the next ## heading
    next_heading = re.search(r'\n## ', rest)
    if next_heading:
        return rest[:next_heading.start()].strip()

    return rest.strip()


# ============================================================================
# ONE-TIME VAULT CLEANUP
# ============================================================================

def cleanup_duplicates() -> dict:
    """
    Scan the entire vault and merge duplicate files.

    For each memory type:
    - People: group by normalized `name` frontmatter field
    - Non-people: cluster by fuzzy title matching

    Within each group of duplicates, the oldest file (by `date`) is kept
    as canonical. All newer duplicates are merged into it, then deleted.

    Returns:
        Stats dict: {"merged": int, "deleted": int, "by_type": {...}}
    """
    from memory.vault import MEMORY_TYPES

    stats = {'merged': 0, 'deleted': 0, 'by_type': {}}

    for memory_type in MEMORY_TYPES:
        folder = VAULT_ROOT / memory_type
        if not folder.exists():
            continue

        files = sorted(folder.glob('*.md'))
        if len(files) < 2:
            continue

        if memory_type == 'people':
            groups = _group_people_files(files)
        else:
            groups = _group_non_people_files(files)

        type_deleted = 0
        type_merged = 0

        for group_key, group_files in groups.items():
            if len(group_files) < 2:
                continue

            # Sort by date — oldest first (canonical)
            group_files.sort(key=lambda f: _parse_frontmatter(f).get('date', '9999'))
            canonical = group_files[0]
            duplicates = group_files[1:]

            # Merge each duplicate into canonical
            for dup_path in duplicates:
                dup_fm = _parse_frontmatter(dup_path)
                dup_body = _parse_body(dup_path)

                merged_fm, merged_body = merge_contents(canonical, dup_body, dup_fm)

                # Rewrite canonical with merged data
                _rewrite_file(canonical, merged_fm, merged_body)

                # Delete the duplicate
                dup_path.unlink()

                # Remove from _index.md
                _remove_from_index(dup_path)

                type_deleted += 1

            type_merged += 1

        if type_deleted > 0:
            stats['by_type'][memory_type] = type_deleted
            stats['merged'] += type_merged
            stats['deleted'] += type_deleted

    return stats


def _group_people_files(files: list[Path]) -> dict[str, list[Path]]:
    """Group people files by normalized name."""
    groups = {}
    for f in files:
        fm = _parse_frontmatter(f)
        name = str(fm.get('name', '')).strip().lower()
        if not name:
            name = f.stem  # fallback to filename
        if name not in groups:
            groups[name] = []
        groups[name].append(f)
    return groups


def _group_non_people_files(files: list[Path]) -> dict[str, list[Path]]:
    """
    Group non-people files by fuzzy title clustering.

    Uses a simple leader-based clustering: each file is compared to existing
    group leaders. If it matches any leader (containment or fuzzy >= threshold),
    it joins that group. Otherwise it becomes a new group leader.
    """
    groups = {}  # leader_norm_title -> [files]

    for f in files:
        fm = _parse_frontmatter(f)
        title = fm.get('title', '')
        if not title:
            continue

        norm = normalize_title(title)
        if not norm:
            continue

        matched_leader = None
        for leader_norm in groups:
            # Containment check
            if norm in leader_norm or leader_norm in norm:
                matched_leader = leader_norm
                break
            # Fuzzy check
            if SequenceMatcher(None, norm, leader_norm).ratio() >= FUZZY_THRESHOLD:
                matched_leader = leader_norm
                break

        if matched_leader:
            groups[matched_leader].append(f)
        else:
            groups[norm] = [f]

    return groups


def _rewrite_file(filepath: Path, frontmatter: dict, body: str):
    """Rewrite a vault file with updated frontmatter and body."""
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    # Determine the heading — people use name, others use title
    heading = frontmatter.get('name') or frontmatter.get('title', filepath.stem)

    content = f"""---
{yaml_str.strip()}
---

# {heading}

{body}
"""
    filepath.write_text(content, encoding='utf-8')


def _remove_from_index(deleted_path: Path):
    """Remove a deleted file's entry from _index.md."""
    index_path = VAULT_ROOT / '_index.md'
    if not index_path.exists():
        return

    relative = deleted_path.relative_to(VAULT_ROOT).as_posix()
    content = index_path.read_text(encoding='utf-8')

    lines = content.split('\n')
    filtered = [line for line in lines if relative not in line]
    index_path.write_text('\n'.join(filtered), encoding='utf-8')
