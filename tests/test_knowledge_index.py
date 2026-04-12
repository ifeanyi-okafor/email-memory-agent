"""Tests for the knowledge index builder (memory/knowledge_index.py)."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault directory with all 5 type folders and patch VAULT_ROOT."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('people', 'decisions', 'commitments', 'action_required', 'insights'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.knowledge_index.VAULT_ROOT', vault)
    return vault


def _write_vault_file(vault_dir, memory_type, filename, frontmatter, body=''):
    """Write a vault file with given frontmatter and body."""
    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    heading = frontmatter.get('name') or frontmatter.get('title', filename)
    content = f"---\n{fm_str.strip()}\n---\n\n# {heading}\n\n{body}"
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


# ============================================================================
# EMPTY VAULT
# ============================================================================

class TestBuildKnowledgeIndexEmpty:
    """Test that an empty vault produces a well-formed index with (none) entries."""

    def test_has_knowledge_index_heading(self, tmp_path, monkeypatch):
        """The index should start with a # Knowledge Index heading."""
        _setup_vault(tmp_path, monkeypatch)
        result = build_knowledge_index()
        assert result.startswith('# Knowledge Index')

    def test_has_all_section_headers(self, tmp_path, monkeypatch):
        """All five memory type sections should be present."""
        _setup_vault(tmp_path, monkeypatch)
        result = build_knowledge_index()
        assert '## People' in result
        assert '## Decisions' in result
        assert '## Commitments' in result
        assert '## Action Items' in result
        assert '## Insights' in result

    def test_empty_sections_show_none(self, tmp_path, monkeypatch):
        """Empty sections should show a (none) placeholder row."""
        _setup_vault(tmp_path, monkeypatch)
        result = build_knowledge_index()
        # Each empty section gets a (none) row — 5 total
        assert result.count('(none)') == 5

    def test_has_entity_resolution_instructions(self, tmp_path, monkeypatch):
        """The index should include instructions about entity resolution."""
        _setup_vault(tmp_path, monkeypatch)
        result = build_knowledge_index()
        assert 'entity already exists' in result


# ============================================================================
# PEOPLE
# ============================================================================

class TestBuildKnowledgeIndexPeople:
    """Test people table generation."""

    def test_person_appears_with_all_fields(self, tmp_path, monkeypatch):
        """A person with all fields should appear in the table with correct values."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-chen-a1b2.md', {
            'name': 'Sarah Chen',
            'email': 'sarah@acme.com',
            'organization': 'Acme Corp',
            'role': 'CTO',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = build_knowledge_index()
        assert 'Sarah Chen' in result
        assert 'sarah@acme.com' in result
        assert 'Acme Corp' in result
        assert 'CTO' in result
        assert 'people/sarah-chen-a1b2.md' in result

    def test_me_md_included(self, tmp_path, monkeypatch):
        """The me.md file should appear in the people table."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'me.md', {
            'name': 'John Doe',
            'email': 'john@example.com',
            'organization': 'My Company',
            'role': 'Product Manager',
            'date': '2026-01-01',
            'category': 'people',
        })

        result = build_knowledge_index()
        assert 'people/me.md' in result
        assert 'John Doe' in result

    def test_multiple_people_each_get_rows(self, tmp_path, monkeypatch):
        """Multiple people should each get their own row."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice Johnson',
            'email': 'alice@example.com',
            'organization': 'Alpha Inc',
            'role': 'Engineer',
            'date': '2026-02-20',
            'category': 'people',
        })
        _write_vault_file(vault, 'people', 'bob-c3d4.md', {
            'name': 'Bob Smith',
            'email': 'bob@example.com',
            'organization': 'Beta LLC',
            'role': 'Designer',
            'date': '2026-02-21',
            'category': 'people',
        })

        result = build_knowledge_index()
        assert 'Alice Johnson' in result
        assert 'Bob Smith' in result
        # No (none) for people since we have entries
        # Find the People section and check it has no (none)
        people_section = result.split('## People')[1].split('## Decisions')[0]
        assert '(none)' not in people_section

    def test_missing_fields_default_to_empty(self, tmp_path, monkeypatch):
        """Missing frontmatter fields should not cause errors — they become empty."""
        vault = _setup_vault(tmp_path, monkeypatch)
        # Minimal person file — only name, no email/org/role
        _write_vault_file(vault, 'people', 'minimal-a1b2.md', {
            'name': 'Minimal Person',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = build_knowledge_index()
        assert 'Minimal Person' in result
        # The row should still be well-formed with pipe separators
        people_section = result.split('## People')[1].split('## Decisions')[0]
        assert '(none)' not in people_section


# ============================================================================
# NON-PEOPLE TYPES
# ============================================================================

class TestBuildKnowledgeIndexNonPeople:
    """Test decisions, commitments, action items, and insights tables."""

    def test_decision_with_title_date_tags(self, tmp_path, monkeypatch):
        """Decisions should show title, date, and comma-joined tags."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'chose-react-a1b2.md', {
            'title': 'Chose React for Frontend',
            'date': '2026-02-20',
            'tags': ['frontend', 'react', 'architecture'],
            'category': 'decisions',
        })

        result = build_knowledge_index()
        assert 'Chose React for Frontend' in result
        assert '2026-02-20' in result
        assert 'frontend, react, architecture' in result
        assert 'decisions/chose-react-a1b2.md' in result

    def test_decision_with_empty_tags(self, tmp_path, monkeypatch):
        """Decisions with no tags should show empty tags column."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'no-tags-a1b2.md', {
            'title': 'Some Decision',
            'date': '2026-03-01',
            'category': 'decisions',
        })

        result = build_knowledge_index()
        assert 'Some Decision' in result

    def test_commitment_with_status(self, tmp_path, monkeypatch):
        """Commitments should show title, commitment_status, and date."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'AI/TX February Meetup',
            'date': '2026-02-25',
            'commitment_status': 'confirmed',
            'category': 'commitments',
        })

        result = build_knowledge_index()
        assert 'AI/TX February Meetup' in result
        assert 'confirmed' in result
        assert 'commitments/meetup-a1b2.md' in result

    def test_action_item_with_quadrant(self, tmp_path, monkeypatch):
        """Action items should show title, status, and quadrant."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'action_required', 'review-pr-a1b2.md', {
            'title': 'Review PR #42',
            'status': 'active',
            'quadrant': 'urgent-important',
            'date': '2026-02-20',
            'category': 'action_required',
        })

        result = build_knowledge_index()
        assert 'Review PR #42' in result
        assert 'active' in result
        assert 'urgent-important' in result
        assert 'action_required/review-pr-a1b2.md' in result

    def test_insight_with_type(self, tmp_path, monkeypatch):
        """Insights should show title, insight_type, and status."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'insights', 'pattern-a1b2.md', {
            'title': 'Recurring Theme: AI Adoption',
            'insight_type': 'strategic_pattern',
            'status': 'active',
            'date': '2026-02-20',
            'category': 'insights',
        })

        result = build_knowledge_index()
        assert 'Recurring Theme: AI Adoption' in result
        assert 'strategic_pattern' in result
        assert 'insights/pattern-a1b2.md' in result


# ============================================================================
# MIXED / INTEGRATION
# ============================================================================

class TestBuildKnowledgeIndexMixed:
    """Test full vault scenarios with multiple types populated."""

    def test_full_vault_has_no_none_entries(self, tmp_path, monkeypatch):
        """When all types have files, no section should show (none)."""
        vault = _setup_vault(tmp_path, monkeypatch)

        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-02-20',
            'category': 'people',
        })
        _write_vault_file(vault, 'decisions', 'react-a1b2.md', {
            'title': 'Chose React',
            'date': '2026-02-20',
            'category': 'decisions',
        })
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'Meetup',
            'date': '2026-02-25',
            'commitment_status': 'confirmed',
            'category': 'commitments',
        })
        _write_vault_file(vault, 'action_required', 'review-a1b2.md', {
            'title': 'Review PR',
            'status': 'active',
            'quadrant': 'urgent-important',
            'date': '2026-02-20',
            'category': 'action_required',
        })
        _write_vault_file(vault, 'insights', 'pattern-a1b2.md', {
            'title': 'AI Pattern',
            'insight_type': 'strategic_pattern',
            'status': 'active',
            'date': '2026-02-20',
            'category': 'insights',
        })

        result = build_knowledge_index()
        assert '(none)' not in result

    def test_nonexistent_folders_gracefully_skipped(self, tmp_path, monkeypatch):
        """If some type folders don't exist, the index still builds with (none) rows."""
        vault = tmp_path / 'vault'
        vault.mkdir()
        # Only create people/ — skip all other folders
        (vault / 'people').mkdir()
        monkeypatch.setattr('memory.knowledge_index.VAULT_ROOT', vault)

        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = build_knowledge_index()
        # People section should have Alice, not (none)
        assert 'Alice' in result
        # Other sections should have (none) since their folders don't exist
        assert result.count('(none)') == 4

    def test_file_paths_are_posix_relative(self, tmp_path, monkeypatch):
        """File paths should use forward slashes and be relative to VAULT_ROOT."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = build_knowledge_index()
        # Should be "people/alice-a1b2.md" with forward slash, not backslash
        assert 'people/alice-a1b2.md' in result
        # Should NOT contain the full tmp_path
        assert str(tmp_path) not in result
