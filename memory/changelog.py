# memory/changelog.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "audit trail" of our memory vault. Every time a memory file is
# created, updated, or merged, a timestamped line is appended to a changelog
# file (`vault/_changelog.md`).
#
# WHY do we need this?
# When an AI system modifies your personal data, you want a clear record of
# what happened and when. This changelog is append-only — like a bank
# statement, entries are only ever added, never edited or removed. This makes
# it easy to answer questions like "what changed since yesterday?" or "why
# does this memory look different than I remember?"
#
# The changelog is a simple markdown table. Each row records one mutation:
#   | 2026-04-11 14:30:00 | CREATED | people/sarah-chen-a1b2.md | Sarah Chen |
#
# IMPORTANT: This file has NO artificial intelligence in it.
# It's pure file operations — appending lines to a markdown file.
# The agents and vault logic decide WHEN to log. This file handles HOW.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "datetime" lets us stamp each changelog entry with the exact time it
# happened — essential for an audit trail.
from datetime import datetime

# "Path" makes file path handling easy and cross-platform.
# We use it to check if the changelog file exists and to read/write it.
from pathlib import Path


# ── CONSTANTS ──────────────────────────────────────────────────────────

# "VAULT_ROOT" is the folder where all memory files are stored.
# Must match the same root used by vault.py so the changelog lives
# alongside the index and other vault metadata files.
VAULT_ROOT = Path('vault')

# "CHANGELOG_FILE" is the full path to the changelog markdown file.
# The underscore prefix signals it's a vault metadata file (like _index.md),
# not a memory file itself.
CHANGELOG_FILE = VAULT_ROOT / '_changelog.md'

# "_HEADER" is the initial content written when the changelog is first created.
# It includes a human-readable title, explanation, and the markdown table header.
# The table uses four columns: Timestamp, Action, File, and Description.
_HEADER = """# Vault Changelog

Append-only log of all vault mutations. Each row records one write operation.

| Timestamp | Action | File | Description |
|-----------|--------|------|-------------|
"""


# ============================================================================
# APPENDING ENTRIES
# ============================================================================

def append_changelog(action: str, filepath: str, description: str):
    """
    Record a vault mutation in the changelog.

    Every time a memory file is created, updated, or merged, call this
    function to append a timestamped row to `_changelog.md`.

    HOW IT WORKS:
    1. If the changelog file doesn't exist yet, create it with the header
    2. Build a markdown table row with the current timestamp
    3. Append the row to the end of the file

    Args:
        action:      What happened — one of: "CREATED", "UPDATED", "MERGED".
        filepath:    The affected file path, relative to the vault root.
                     Example: "people/sarah-chen-a1b2.md"
        description: A short description of the memory (usually the title).
                     Example: "Sarah Chen — CTO at Acme"
    """
    # ── Ensure the changelog file exists ────────────────────────
    # On the very first vault mutation, the file won't exist yet.
    # We create it with the header so it's a valid markdown table
    # from the start.
    if not CHANGELOG_FILE.exists():
        # Make sure the vault directory exists (it should, but be safe)
        CHANGELOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHANGELOG_FILE.write_text(_HEADER, encoding='utf-8')

    # ── Build the table row ────────────────────────────────────
    # Format: "| 2026-04-11 14:30:00 | CREATED | people/file.md | Title |"
    # We use "now()" to get the exact moment this mutation happened.
    # Sanitize pipe characters in filepath and description to prevent
    # breaking the markdown table structure.
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filepath = str(filepath).replace('|', '-')
    description = str(description).replace('|', '-')
    row = f"| {timestamp} | {action} | {filepath} | {description} |\n"

    # ── Append to the file ─────────────────────────────────────
    # Using mode 'a' (append) means we add to the end without
    # touching existing content. This is what makes the log
    # "append-only" — we never modify previous entries.
    with open(CHANGELOG_FILE, 'a', encoding='utf-8') as f:
        f.write(row)


# ============================================================================
# READING THE CHANGELOG
# ============================================================================

def read_changelog(last_n: int = None) -> str:
    """
    Read the changelog and return its content as a string.

    Can return the full changelog or just the most recent N entries.
    This is useful for showing users "what changed recently" without
    dumping the entire history.

    Args:
        last_n: If provided, return only the last N data rows (plus the
                header). If None, return the full changelog.
                Example: last_n=3 returns the header + the 3 most recent entries.

    Returns:
        The changelog content as a string.
        Returns an empty string if the changelog file doesn't exist yet
        (i.e., no mutations have happened).
    """
    # ── Handle missing file ────────────────────────────────────
    # If no mutations have happened yet, there's nothing to show.
    if not CHANGELOG_FILE.exists():
        return ""

    # ── Read the full content ──────────────────────────────────
    content = CHANGELOG_FILE.read_text(encoding='utf-8')

    # ── If no limit requested, return everything ───────────────
    if last_n is None:
        return content

    # ── Extract the header and data rows ───────────────────────
    # The changelog is a markdown file with a header section followed
    # by table rows. We need to separate the two so we can slice
    # just the data rows while preserving the header.
    #
    # Strategy: split into lines, find where data rows start
    # (lines beginning with "| " that are NOT the table header or
    # separator), then take the last N of those.
    lines = content.split('\n')

    header_lines = []
    data_rows = []

    # The table separator line looks like "|-----------|..."
    # Data rows start with "| " followed by a digit (the timestamp).
    for line in lines:
        if line.startswith('| ') and not line.startswith('| Timestamp') and not line.startswith('|---'):
            data_rows.append(line)
        else:
            header_lines.append(line)

    # ── Slice to the last N rows ───────────────────────────────
    # Python's list slicing makes this easy:
    # [-3:] gives us the last 3 elements of a list.
    # Guard against last_n=0: data_rows[-0:] returns ALL rows, not empty.
    if last_n <= 0:
        return '\n'.join(header_lines)
    limited_rows = data_rows[-last_n:]

    # ── Reassemble the output ──────────────────────────────────
    # Combine the header with the limited data rows.
    # We join the header lines back together, then append the rows.
    result = '\n'.join(header_lines)
    if limited_rows:
        result = result.rstrip('\n') + '\n' + '\n'.join(limited_rows) + '\n'

    return result
