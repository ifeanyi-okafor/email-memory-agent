# tests/test_universal_status.py
"""Tests for universal status fields across all entity types."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
        (vault / mtype).mkdir()
    (vault / '_index.md').write_text(
        '---\ntitle: "Vault Index"\n---\n\n'
        '| File | Type | Description | Date |\n'
        '|------|------|-------------|------|\n'
    )
    import memory.vault
    import memory.dedup
    import memory.changelog
    monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')
    return vault


class TestPeopleStatus:
    def test_person_default_status_is_active(self, tmp_path, monkeypatch):
        """People without explicit status should default to 'active'."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Alice Park — Designer",
                memory_type="people",
                content="## Overview\n\nDesigner.",
                name="Alice Park",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'active'

    def test_person_with_explicit_status(self, tmp_path, monkeypatch):
        """People with explicit status should record it."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Bob — Engineer",
                memory_type="people",
                content="## Overview\n\nFormer engineer.",
                name="Bob",
                status="left-org",
                status_reason="Left Acme in March 2026 to join Stripe",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'left-org'
        assert 'Left Acme' in fm['status_reason']
        assert fm['status_updated']  # auto-populated

    def test_person_status_updated_autofills(self, tmp_path, monkeypatch):
        """status_updated should default to today when status is set."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Charlie — PM",
                memory_type="people",
                content="## Overview\n\nPM.",
                name="Charlie",
                status="inactive",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        assert fm['status_updated'] == today
