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

# Minimum length for a new section to be considered "substantive" enough to
# replace an existing section during merge.  Short stubs like "N/A" or
# "No information" should not overwrite richer existing content.
_MIN_SUBSTANTIVE_LENGTH = 30


# ============================================================================
# PERSON NAME CLEANING
# ============================================================================

# Separators that indicate "name — role/title/org" patterns.
# The LLM and email From fields often produce names like:
#   "Kate Lee - Editor in Chief at Every"
#   "Warner Godfrey — Principal Consultant, Engineering at DiUS"
#   "Me - Product Professional"
# We strip everything after these separators to get just the name.
_NAME_SEPARATORS = re.compile(r'\s*[-–—|/]\s*(?=[A-Z])')

# Common role/title keywords that should never be part of a person's name.
# Used as a fallback when no separator is found but the name looks like
# "John Smith Senior Engineer" or "John Smith at Acme Corp".
_ROLE_KEYWORDS = {
    'at', 'of', 'for',  # prepositions before org names
    'ceo', 'cto', 'cfo', 'coo', 'cio', 'vp',
    'president', 'director', 'manager', 'lead', 'head',
    'engineer', 'developer', 'designer', 'consultant',
    'analyst', 'specialist', 'coordinator', 'associate',
    'writer', 'editor', 'author', 'reporter',
    'professor', 'teacher', 'coach', 'trainer',
    'founder', 'co-founder', 'partner', 'principal',
    'senior', 'junior', 'staff', 'chief',
    'organizer', 'speaker', 'evangelist', 'advocate',
}


def clean_person_name(raw_name: str) -> str:
    """
    Extract just the human name from a raw name string, stripping
    titles, roles, organizations, and other non-name content.

    Examples:
        "Kate Lee - Editor in Chief at Every"  →  "Kate Lee"
        "Warner Godfrey — Principal Consultant" →  "Warner Godfrey"
        "Me - Product Professional"            →  "Me"
        "Olubankole 'Banky W' Wellington - Speaker at YAIS IV"
                                               →  "Olubankole 'Banky W' Wellington"
        "John Smith"                           →  "John Smith"

    Args:
        raw_name: The raw name string, possibly containing role/title info.

    Returns:
        The cleaned name containing only the person's actual name.
    """
    if not raw_name or not raw_name.strip():
        return raw_name

    name = raw_name.strip()

    # Step 1: Split on separator characters ( - , — , – )
    # Take only the part before the first separator that's followed by
    # what looks like a title/role (starts with uppercase letter).
    match = _NAME_SEPARATORS.search(name)
    if match:
        name = name[:match.start()].strip()

    # Step 2: Check for "at Organization" pattern at the end
    # e.g., "John Smith at Acme Corp" → "John Smith"
    at_match = re.search(r'\s+at\s+[A-Z]', name)
    if at_match:
        name = name[:at_match.start()].strip()

    # Step 3: Check if remaining tokens contain role keywords
    # e.g., "John Smith Senior Engineer" → "John Smith"
    # Only trigger if we find a role keyword AND the name has 3+ words
    words = name.split()
    if len(words) >= 3:
        # Walk backwards through words — find the first role keyword
        # and truncate there
        for i in range(len(words) - 1, 0, -1):
            if words[i].lower().rstrip('.,;:') in _ROLE_KEYWORDS:
                # Don't truncate if it would leave only 1 word
                if i >= 2:
                    name = ' '.join(words[:i]).strip()
                break

    # Step 4: Clean up any trailing punctuation or whitespace
    name = name.strip(' ,;:-–—')

    return name if name else raw_name


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
    Find a duplicate people file by matching cleaned person names.

    Cleans both the incoming name and existing names to strip roles/titles,
    then matches on:
      1. Exact cleaned name match
      2. One cleaned name is a prefix of the other (handles partial names)

    The incoming name is derived from the `name` parameter if provided,
    otherwise extracted from the title before " — ".
    """
    # Determine the search name and clean it
    if name:
        raw_search = name.strip()
    elif ' — ' in title:
        raw_search = title.split(' — ')[0].strip()
    else:
        raw_search = title.strip()

    search_clean = clean_person_name(raw_search).lower()

    if not search_clean:
        return None

    # Special case: "Me" variants all route to me.md
    if search_clean == 'me' or raw_search.lower().startswith('me '):
        me_file = folder / 'me.md'
        if me_file.exists():
            return me_file

    for md_file in folder.glob('*.md'):
        fm = _parse_frontmatter(md_file)
        existing_raw = str(fm.get('name', '')).strip()
        existing_clean = clean_person_name(existing_raw).lower()

        if not existing_clean:
            continue

        # Exact match on cleaned names
        if existing_clean == search_clean:
            return md_file

        # Prefix match: "Kate Lee" matches "Kate Lee - Editor in Chief"
        # (catches cases where existing file wasn't cleaned yet)
        if existing_clean.startswith(search_clean) or search_clean.startswith(existing_clean):
            # Guard: both must be at least 2 chars to avoid false positives
            if len(search_clean) >= 2 and len(existing_clean) >= 2:
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
# SECTION PARSING (for intelligent content merging)
# ============================================================================

def _parse_sections(body: str) -> list[tuple[str, str]]:
    """
    Parse a markdown body into an ordered list of (heading, content) tuples.

    The text before the first ## heading is stored under the key '_preamble'.
    Each ## heading becomes a key; its content runs until the next ## or EOF.

    Returns a list (not dict) to preserve section order and allow duplicate
    headings (though they shouldn't occur in well-formed files).

    Example:
        "Overview text\n\n## Contact\nemail\n\n## Notes\nstuff"
        → [('_preamble', 'Overview text'), ('## Contact', 'email'), ('## Notes', 'stuff')]
    """
    sections: list[tuple[str, str]] = []
    lines = body.split('\n')

    current_heading = '_preamble'
    current_lines: list[str] = []

    for line in lines:
        # Detect ## headings (but not # top-level — those are the file title)
        if line.startswith('## '):
            # Save the previous section
            sections.append((current_heading, '\n'.join(current_lines).strip()))
            current_heading = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save the last section
    sections.append((current_heading, '\n'.join(current_lines).strip()))

    return sections


def _sections_to_dict(sections: list[tuple[str, str]]) -> dict[str, str]:
    """Convert section list to dict for lookup. Last value wins on duplicates."""
    return {heading: content for heading, content in sections}


def _sections_to_text(sections: list[tuple[str, str]]) -> str:
    """Reassemble a section list back into markdown body text."""
    parts = []
    for heading, content in sections:
        if heading == '_preamble':
            if content:
                parts.append(content)
        else:
            if content:
                parts.append(f"{heading}\n\n{content}")
            else:
                parts.append(heading)
    return '\n\n'.join(parts)


def _extract_dated_entries(ki_content: str) -> dict[str, str]:
    """
    Extract dated sub-entries from Key Interactions content.

    Key Interactions sections contain ### YYYY-MM-DD sub-headings with
    bullet points underneath. Returns {date_string: full_entry_text}.
    """
    entries: dict[str, str] = {}
    current_date = None
    current_lines: list[str] = []

    for line in ki_content.split('\n'):
        if line.startswith('### '):
            # Save previous entry
            if current_date:
                entries[current_date] = '\n'.join(current_lines).strip()
            current_date = line.strip()
            current_lines = [line]
        elif current_date:
            current_lines.append(line)
        # Lines before any ### date are ignored (shouldn't exist in well-formed files)

    # Save last entry
    if current_date:
        entries[current_date] = '\n'.join(current_lines).strip()

    return entries


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

    # People-specific scalar fields that should be UPDATED (not just gap-filled)
    # when new data provides a non-empty value.  These represent current state
    # that can change (e.g., a promotion changes role/organization).
    _UPDATABLE_SCALARS = {'role', 'organization', 'email', 'phone', 'location', 'timezone'}

    for key, new_val in new_frontmatter.items():
        if key in ('tags', 'related_to', 'source_emails', 'source_memories'):
            # List fields: union as sets
            existing_list = merged_fm.get(key, []) or []
            new_list = new_val if isinstance(new_val, list) else []
            merged_fm[key] = sorted(set(existing_list) | set(new_list))
        elif key in _UPDATABLE_SCALARS and new_val:
            # Updatable scalars: always prefer the latest non-empty value
            merged_fm[key] = new_val
        elif not merged_fm.get(key) and new_val:
            # Other scalar fields: only fill if existing is empty/falsy
            merged_fm[key] = new_val

    # Always update the 'updated' timestamp
    merged_fm['updated'] = datetime.now().strftime('%Y-%m-%d')

    # ── Merge body content ────────────────────────────────────
    memory_type = merged_fm.get('category', merged_fm.get('memoryType', ''))

    # Strip the leading # heading from existing body before merging.
    # write_memory() adds its own # heading from frontmatter, so we must
    # not return one — otherwise the heading gets duplicated.
    existing_body_clean = re.sub(r'^#\s+[^\n]+\n*', '', existing_body.strip()).strip()

    # Also strip any leading # heading from new content (LLM sometimes
    # includes it even though write_memory adds one).
    new_content_clean = re.sub(r'^#\s+[^\n]+\n*', '', new_content.strip()).strip()

    if memory_type in ('people', 'person'):
        merged_body = _merge_people_content(existing_body_clean, new_content_clean)
    else:
        merged_body = _merge_generic_content(existing_body_clean, new_content_clean)

    return merged_fm, merged_body


def _merge_people_content(existing_body: str, new_body: str) -> str:
    """
    Merge people content section-by-section.

    Strategy:
    - Key Interactions: append only NEW dated entries (### YYYY-MM-DD)
    - Other sections: replace with new version if it's substantive
      (longer than _MIN_SUBSTANTIVE_LENGTH), otherwise keep existing
    - New sections not in existing: append at end
    - Existing sections not in new: preserve as-is
    """
    if not new_body.strip():
        return existing_body

    existing_sections = _parse_sections(existing_body)
    new_sections = _parse_sections(new_body)

    existing_dict = _sections_to_dict(existing_sections)
    new_dict = _sections_to_dict(new_sections)

    # Build merged section list, starting from existing order
    merged: list[tuple[str, str]] = []
    seen_headings: set[str] = set()

    for heading, existing_content in existing_sections:
        seen_headings.add(heading)

        if heading == '## Key Interactions':
            # Append only new dated entries
            new_ki = new_dict.get('## Key Interactions', '')
            merged_ki = _merge_key_interactions(existing_content, new_ki)
            merged.append((heading, merged_ki))

        elif heading in new_dict:
            new_content = new_dict[heading]
            # Replace if new content is substantive
            if len(new_content.strip()) >= _MIN_SUBSTANTIVE_LENGTH:
                merged.append((heading, new_content))
            else:
                merged.append((heading, existing_content))
        else:
            # Section only in existing — preserve
            merged.append((heading, existing_content))

    # Append sections from new that don't exist in existing
    for heading, new_content in new_sections:
        if heading not in seen_headings and new_content.strip():
            merged.append((heading, new_content))

    return _sections_to_text(merged)


def _merge_key_interactions(existing_ki: str, new_ki: str) -> str:
    """
    Merge Key Interactions by appending only new dated entries.

    Each entry is a ### YYYY-MM-DD sub-heading with bullets.
    If a date already exists in existing, skip it (no duplication).
    """
    if not new_ki.strip():
        return existing_ki

    existing_entries = _extract_dated_entries(existing_ki)
    new_entries = _extract_dated_entries(new_ki)

    # Start with existing content
    result = existing_ki.rstrip() if existing_ki.strip() else ''

    # Append only dates not already present
    for date_heading, entry_text in new_entries.items():
        if date_heading not in existing_entries:
            if result:
                result += '\n\n' + entry_text
            else:
                result = entry_text

    return result


def _merge_generic_content(existing_body: str, new_body: str) -> str:
    """
    Merge non-people content section-by-section.

    Strategy:
    - If both have ## sections: merge per-section (replace existing
      with new if substantive, preserve sections only in existing,
      append sections only in new)
    - If neither has sections (flat prose): keep existing if similar,
      otherwise replace with new (never append with ---)
    """
    if not new_body.strip():
        return existing_body

    existing_sections = _parse_sections(existing_body)
    new_sections = _parse_sections(new_body)

    existing_has_sections = any(h != '_preamble' for h, _ in existing_sections)
    new_has_sections = any(h != '_preamble' for h, _ in new_sections)

    # ── Both have sections: section-by-section merge ──────────
    if existing_has_sections or new_has_sections:
        existing_dict = _sections_to_dict(existing_sections)
        new_dict = _sections_to_dict(new_sections)

        merged: list[tuple[str, str]] = []
        seen_headings: set[str] = set()

        for heading, existing_content in existing_sections:
            seen_headings.add(heading)
            if heading in new_dict:
                new_content = new_dict[heading]
                if len(new_content.strip()) >= _MIN_SUBSTANTIVE_LENGTH:
                    merged.append((heading, new_content))
                else:
                    merged.append((heading, existing_content))
            else:
                merged.append((heading, existing_content))

        for heading, new_content in new_sections:
            if heading not in seen_headings and new_content.strip():
                merged.append((heading, new_content))

        return _sections_to_text(merged)

    # ── Flat prose (no sections): keep existing if similar ────
    # Strip leading # heading for fair comparison
    existing_stripped = re.sub(r'^#\s+[^\n]+\n*', '', existing_body.strip()).strip()
    new_stripped = new_body.strip()

    ratio = SequenceMatcher(None, existing_stripped, new_stripped).ratio()

    if ratio >= CONTENT_SIMILARITY_THRESHOLD:
        return existing_body

    # New content is substantially different — replace (not append)
    # Preserve the existing # heading if present
    heading_match = re.match(r'^(#\s+[^\n]+\n*)', existing_body.strip())
    if heading_match:
        return heading_match.group(1) + '\n' + new_stripped
    return new_body


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

            # Sort by date — oldest first (canonical).
            # Special case: me.md is ALWAYS canonical for "me" group,
            # regardless of date, because it's the singleton filename.
            group_files.sort(key=lambda f: _parse_frontmatter(f).get('date', '9999'))
            me_file = next((f for f in group_files if f.name == 'me.md'), None)
            if me_file:
                canonical = me_file
                duplicates = [f for f in group_files if f != me_file]
            else:
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
    """Group people files by cleaned, normalized name.

    Special handling: any file whose cleaned name is "me" OR whose
    filename is "me.md" gets grouped under the "me" key, so all
    "Me" variants merge into the canonical me.md file.
    """
    groups = {}
    for f in files:
        fm = _parse_frontmatter(f)
        raw_name = str(fm.get('name', '')).strip()
        name = clean_person_name(raw_name).lower() if raw_name else f.stem

        # Route me.md and all "Me - ..." variants to the same group
        if f.name == 'me.md' or name == 'me':
            name = 'me'

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
    # Clean person names before rewriting (skip me.md — it stores the real name)
    if filepath.name != 'me.md':
        if frontmatter.get('category') in ('people', 'person') or frontmatter.get('memoryType') in ('people', 'person'):
            raw_name = frontmatter.get('name', '')
            if raw_name:
                frontmatter['name'] = clean_person_name(raw_name)

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
