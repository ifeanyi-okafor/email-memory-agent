"""Integration tests: Knowledge Index injection into MemoryWriter prompt."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.knowledge_index.VAULT_ROOT', vault)
    return vault


def _write_vault_file(vault_dir, memory_type, filename, frontmatter, body=''):
    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    heading = frontmatter.get('name') or frontmatter.get('title', filename)
    content = f"---\n{fm_str.strip()}\n---\n\n# {heading}\n\n{body}"
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


class TestIndexContentForAgent:
    """Verify the index contains what an agent needs for entity resolution."""

    def test_index_has_resolution_instructions(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        index = build_knowledge_index()
        assert 'resolve entities' in index.lower() or 'Knowledge Index' in index

    def test_index_enables_person_lookup_by_email(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-a1b2.md', {
            'name': 'Sarah Chen', 'category': 'people',
            'email': 'sarah@acme.com', 'organization': 'Acme Corp',
            'role': 'VP Engineering',
        })
        index = build_knowledge_index()
        assert 'sarah@acme.com' in index
        assert 'people/sarah-a1b2.md' in index

    def test_index_enables_commitment_status_check(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'AITX Meetup February', 'category': 'commitments',
            'commitment_status': 'confirmed',
        })
        index = build_knowledge_index()
        assert 'AITX Meetup February' in index
        assert 'confirmed' in index

    def test_index_fits_in_reasonable_token_budget(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        for i in range(20):
            _write_vault_file(vault, 'people', f'person-{i}.md', {
                'name': f'Person {i}', 'category': 'people', 'email': f'p{i}@example.com',
            })
        for i in range(10):
            _write_vault_file(vault, 'decisions', f'decision-{i}.md', {
                'title': f'Decision {i}', 'category': 'decisions', 'tags': ['test'],
            })
        for i in range(10):
            _write_vault_file(vault, 'commitments', f'commit-{i}.md', {
                'title': f'Commitment {i}', 'category': 'commitments', 'commitment_status': 'invited',
            })
        for i in range(10):
            _write_vault_file(vault, 'action_required', f'action-{i}.md', {
                'title': f'Action {i}', 'category': 'action_required',
                'status': 'active', 'quadrant': 'important-not-urgent',
            })
        index = build_knowledge_index()
        assert len(index) < 6000, f"Index too large: {len(index)} chars for 50 entities"


class TestIndexPromptFormat:
    def test_index_is_valid_markdown(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        index = build_knowledge_index()
        assert index.startswith('# Knowledge Index')

    def test_index_tables_have_header_rows(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'test.md', {
            'name': 'Test', 'category': 'people',
        })
        index = build_knowledge_index()
        assert '| File | Name | Email | Organization | Role |' in index
        assert '| File | Title | Date | Tags |' in index
        assert '| File | Title | Status | Date |' in index
        assert '| File | Title | Status | Quadrant |' in index
        assert '| File | Title | Type | Status |' in index
