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


class TestWriteOrganization:
    def test_write_organization_creates_file(self, tmp_path, monkeypatch):
        """write_memory with memory_type='organizations' should create a file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Acme Corp",
                memory_type="organizations",
                content="## Overview\n\nEnterprise software company.",
                tags=["enterprise", "software"],
                org_domain="acme.com",
                org_industry="Technology",
                org_relationship="customer",
            )

        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])

        assert fm['title'] == 'Acme Corp'
        assert fm['category'] == 'organizations'
        assert fm['domain'] == 'acme.com'
        assert fm['industry'] == 'Technology'
        assert fm['relationship_type'] == 'customer'

    def test_organization_frontmatter_has_all_fields(self, tmp_path, monkeypatch):
        """Organization files should have domain, industry, relationship_type in frontmatter."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Stripe",
                memory_type="organizations",
                content="## Overview\n\nPayment processing.",
                org_domain="stripe.com",
                org_industry="Fintech",
                org_relationship="partner",
            )

        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert 'domain' in fm
        assert 'industry' in fm
        assert 'relationship_type' in fm
        assert fm['memoryType'] == 'organizations'

    def test_organization_with_empty_fields(self, tmp_path, monkeypatch):
        """Organization with no optional fields should still write successfully."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Unknown Corp",
                memory_type="organizations",
                content="## Overview\n\nLittle information available.",
            )

        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['domain'] == ''
        assert fm['industry'] == ''
        assert fm['relationship_type'] == ''

    def test_organization_dedup(self, tmp_path, monkeypatch):
        """Writing the same org twice should merge into one file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            path1 = write_memory(
                title="Acme Corp", memory_type="organizations",
                content="## Overview\n\nSoftware company.", tags=["software"],
                org_domain="acme.com",
            )
            path2 = write_memory(
                title="Acme Corp", memory_type="organizations",
                content="## Overview\n\nUpdated: enterprise software.", tags=["enterprise"],
                org_industry="Enterprise Software",
            )

        assert Path(path1).name == Path(path2).name
        files = list((vault / 'organizations').glob('*.md'))
        assert len(files) == 1
