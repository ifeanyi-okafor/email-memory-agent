# tests/test_projects.py
"""Tests for the Projects entity type."""

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


class TestProjectsRegistered:
    def test_projects_in_memory_types(self):
        from memory.vault import MEMORY_TYPES
        assert 'projects' in MEMORY_TYPES

    def test_projects_folder_created_on_init(self, tmp_path, monkeypatch):
        import memory.vault
        vault = tmp_path / 'vault'
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        memory.vault.initialize_vault()
        assert (vault / 'projects').exists()


class TestWriteProject:
    def test_write_project_creates_file(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Series A Fundraising",
                memory_type="projects",
                content="## Overview\n\nRaising seed round.",
                tags=["fundraising"],
                project_status="active",
                project_type="deal",
            )
        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['title'] == 'Series A Fundraising'
        assert fm['category'] == 'projects'
        assert fm['project_status'] == 'active'
        assert fm['project_type'] == 'deal'

    def test_project_frontmatter_has_all_fields(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Product Launch Q2",
                memory_type="projects",
                content="## Overview\n\nQ2 launch prep.",
                project_status="planning",
                project_type="product",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert 'project_status' in fm
        assert 'project_type' in fm
        assert fm['memoryType'] == 'projects'

    def test_project_default_status(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Unnamed Project",
                memory_type="projects",
                content="## Overview\n\nSomething.",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['project_status'] == 'active'
        assert fm['project_type'] == ''

    def test_project_dedup(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            path1 = write_memory(
                title="Series A Fundraising", memory_type="projects",
                content="## Overview\n\nRaising seed.",
                project_status="active", tags=["fundraising"],
            )
            path2 = write_memory(
                title="Series A Fundraising", memory_type="projects",
                content="## Overview\n\nRound in progress.",
                project_status="active", tags=["investor"],
            )
        assert Path(path1).name == Path(path2).name
        files = list((vault / 'projects').glob('*.md'))
        assert len(files) == 1


class TestProjectInKnowledgeIndex:
    def test_project_appears_in_index(self, tmp_path, monkeypatch):
        """After writing a project, it should appear in the Knowledge Index."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.knowledge_index
        monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Q2 Launch", memory_type="projects",
                content="## Overview\n\nLaunch.", project_status="planning",
            )

        from memory.knowledge_index import build_knowledge_index
        index = build_knowledge_index()
        assert 'Q2 Launch' in index
        assert 'planning' in index


class TestProjectInChangelog:
    def test_project_write_logged(self, tmp_path, monkeypatch):
        """Writing a project should create a changelog entry."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Series A", memory_type="projects",
                content="## Overview\n\nFundraising.",
            )

        from memory.changelog import read_changelog
        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'Series A' in changelog
