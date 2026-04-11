# tests/test_organizations.py
"""Tests for the Organizations entity type."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault with all memory type folders."""
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


class TestOrganizationsRegistered:
    def test_organizations_in_memory_types(self):
        """'organizations' should be a valid memory type."""
        from memory.vault import MEMORY_TYPES
        assert 'organizations' in MEMORY_TYPES

    def test_projects_in_memory_types(self):
        """'projects' should be a valid memory type."""
        from memory.vault import MEMORY_TYPES
        assert 'projects' in MEMORY_TYPES

    def test_organizations_folder_created_on_init(self, tmp_path, monkeypatch):
        """initialize_vault() should create an organizations/ folder."""
        import memory.vault
        vault = tmp_path / 'vault'
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        memory.vault.initialize_vault()
        assert (vault / 'organizations').exists()

    def test_projects_folder_created_on_init(self, tmp_path, monkeypatch):
        """initialize_vault() should create a projects/ folder."""
        import memory.vault
        vault = tmp_path / 'vault'
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        memory.vault.initialize_vault()
        assert (vault / 'projects').exists()

    def test_organizations_in_graph_categories(self):
        """'organizations' should be in the graph scan categories."""
        from memory.graph import MEMORY_CATEGORIES
        assert 'organizations' in MEMORY_CATEGORIES

    def test_projects_in_graph_categories(self):
        """'projects' should be in the graph scan categories."""
        from memory.graph import MEMORY_CATEGORIES
        assert 'projects' in MEMORY_CATEGORIES
