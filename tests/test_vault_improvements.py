# tests/test_vault_improvements.py
"""End-to-end integration tests for vault Priority 1 improvements."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index
from memory.changelog import read_changelog
from tools.email_filter import classify_email, filter_emails


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_full_vault(tmp_path, monkeypatch):
    """Create a fully patched temporary vault."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
        (vault / mtype).mkdir()
    (vault / '_index.md').write_text(
        '---\ntitle: "Vault Index"\n---\n\n| File | Type | Description | Date |\n|------|------|-------------|------|\n'
    )

    import memory.vault
    import memory.knowledge_index
    import memory.changelog
    import memory.dedup

    monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')
    monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)

    return vault


# ============================================================================
# FULL PIPELINE: write_memory → changelog + index reflects new state
# ============================================================================

class TestFullPipeline:
    def test_write_memory_then_index_reflects_new_entity(self, tmp_path, monkeypatch):
        """After write_memory, the Knowledge Index should include the new entity."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Alice Park — Designer",
                memory_type="people",
                content="## Overview\n\nDesigner at Acme.",
                name="Alice Park",
                role="Designer",
                organization="Acme",
                email="alice@acme.com",
            )

        index = build_knowledge_index()
        assert 'Alice Park' in index
        assert 'alice@acme.com' in index
        assert 'Acme' in index

    def test_write_memory_then_changelog_records_it(self, tmp_path, monkeypatch):
        """After write_memory, the changelog should have a CREATED entry."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Chose React for Frontend",
                memory_type="decisions",
                content="Team chose React.",
            )

        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'Chose React' in changelog

    def test_duplicate_write_shows_updated_in_changelog(self, tmp_path, monkeypatch):
        """Writing the same entity twice should show UPDATED in changelog."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Bob Smith — Engineer",
                memory_type="people",
                content="## Overview\n\nEngineer at Eng.io.",
                name="Bob Smith",
            )

            write_memory(
                title="Bob Smith — Senior Engineer",
                memory_type="people",
                content="## Overview\n\nPromoted to Senior Engineer at Eng.io.",
                name="Bob Smith",
            )

        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'UPDATED' in changelog


# ============================================================================
# NOISE FILTER + INDEX COHERENCE
# ============================================================================

class TestFilterAndIndex:
    def test_noise_emails_dont_pollute_vault(self):
        """Noise emails should be filtered before any vault writes happen."""
        emails = [
            {'from': 'alice@acme.com', 'subject': 'Project update', 'body': 'Meeting tomorrow.', 'labels': []},
            {'from': 'noreply@spam.com', 'subject': 'You won!', 'body': 'Click to unsubscribe.', 'labels': ['CATEGORY_PROMOTIONS']},
            {'from': 'newsletter@news.com', 'subject': 'Weekly digest', 'body': 'Unsubscribe from this list.', 'labels': []},
        ]

        signal, noise = filter_emails(emails)

        assert len(signal) == 1
        assert signal[0]['from'] == 'alice@acme.com'
        assert len(noise) == 2

    def test_index_and_changelog_consistent_after_multiple_writes(self, tmp_path, monkeypatch):
        """After several writes, the index and changelog should both reflect the same entities."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(title="Alice — PM", memory_type="people",
                        content="## Overview\n\nPM.", name="Alice")
            write_memory(title="Chose Vue", memory_type="decisions",
                        content="Team chose Vue.")
            write_memory(title="Sprint Demo — March 15", memory_type="commitments",
                        content="Demo on March 15.", commitment_status="confirmed")

        index = build_knowledge_index()
        changelog = read_changelog()

        # Index should have all three
        assert 'Alice' in index
        assert 'Chose Vue' in index
        assert 'Sprint Demo' in index

        # Changelog should have three CREATED entries
        created_count = changelog.count('CREATED')
        assert created_count == 3
