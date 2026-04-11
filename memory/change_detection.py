# memory/change_detection.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Tracks the state of vault files using content hashes (SHA-256).
# Enables detecting which files were added, modified, or deleted
# between two points in time.
#
# Inspired by Rowboat's graph_state.ts — but uses hash-only (no mtime)
# since the vault is small enough that rehashing is fast, and it avoids
# false positives from mtime changes without content changes.
# ============================================================================

import json
import hashlib
from pathlib import Path

VAULT_ROOT = Path('vault')
STATE_FILE = VAULT_ROOT / '_file_state.json'

MEMORY_TYPES = [
    'decisions', 'people', 'commitments', 'action_required',
    'insights', 'organizations', 'projects',
]


def _hash_file(filepath: Path) -> str:
    """Compute SHA-256 hash of a file's content."""
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()


def scan_vault_state() -> dict:
    """
    Scan all vault .md files and return a state dict mapping
    relative paths to content hashes.

    Returns:
        Dict like: {'people/alice.md': {'hash': 'abc123...'}, ...}
    """
    state = {}
    for mtype in MEMORY_TYPES:
        folder = VAULT_ROOT / mtype
        if not folder.exists():
            continue
        for md_file in sorted(folder.glob('*.md')):
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            state[rel_path] = {'hash': _hash_file(md_file)}
    return state


def detect_changes(old_state: dict, new_state: dict) -> dict:
    """
    Compare two vault states and return differences.

    Returns:
        {'added': [...], 'modified': [...], 'deleted': [...]}
    """
    old_paths = set(old_state.keys())
    new_paths = set(new_state.keys())

    added = sorted(new_paths - old_paths)
    deleted = sorted(old_paths - new_paths)

    modified = []
    for path in sorted(old_paths & new_paths):
        if old_state[path]['hash'] != new_state[path]['hash']:
            modified.append(path)

    return {'added': added, 'modified': modified, 'deleted': deleted}


def save_state(state: dict):
    """Save vault state to disk for future comparison."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def load_state() -> dict:
    """Load previously saved vault state. Returns empty dict if no file."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}
