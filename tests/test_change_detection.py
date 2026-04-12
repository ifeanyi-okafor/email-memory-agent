# tests/test_change_detection.py
"""Tests for vault file change detection (memory/change_detection.py)."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.change_detection import scan_vault_state, detect_changes, save_state, load_state


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.change_detection.VAULT_ROOT', vault)
    monkeypatch.setattr('memory.change_detection.STATE_FILE', vault / '_file_state.json')
    return vault


def _write_vault_file(vault_dir, memory_type, filename, content='test'):
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


class TestScanVaultState:
    def test_empty_vault_returns_empty(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        state = scan_vault_state()
        assert state == {}

    def test_scans_all_files(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md')
        _write_vault_file(vault, 'decisions', 'react.md')
        state = scan_vault_state()
        assert len(state) == 2
        assert 'people/alice.md' in state
        assert 'decisions/react.md' in state

    def test_state_includes_hash(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'hello world')
        state = scan_vault_state()
        entry = state['people/alice.md']
        assert 'hash' in entry
        assert isinstance(entry['hash'], str)
        assert len(entry['hash']) == 64  # SHA-256 hex digest


class TestDetectChanges:
    def test_new_file_detected(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md')
        changes = detect_changes({}, scan_vault_state())
        assert len(changes['added']) == 1
        assert 'people/alice.md' in changes['added']

    def test_modified_file_detected(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'version 1')
        old_state = scan_vault_state()
        _write_vault_file(vault, 'people', 'alice.md', 'version 2')
        new_state = scan_vault_state()
        changes = detect_changes(old_state, new_state)
        assert len(changes['modified']) == 1
        assert 'people/alice.md' in changes['modified']

    def test_deleted_file_detected(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        filepath = _write_vault_file(vault, 'people', 'alice.md')
        old_state = scan_vault_state()
        filepath.unlink()
        new_state = scan_vault_state()
        changes = detect_changes(old_state, new_state)
        assert len(changes['deleted']) == 1
        assert 'people/alice.md' in changes['deleted']

    def test_unchanged_file_not_reported(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'stable')
        state = scan_vault_state()
        changes = detect_changes(state, state)
        assert changes == {'added': [], 'modified': [], 'deleted': []}

    def test_no_changes_returns_empty_lists(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        changes = detect_changes({}, {})
        assert changes == {'added': [], 'modified': [], 'deleted': []}


class TestStatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'hello')
        state = scan_vault_state()
        save_state(state)
        loaded = load_state()
        assert loaded == state

    def test_load_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        loaded = load_state()
        assert loaded == {}
