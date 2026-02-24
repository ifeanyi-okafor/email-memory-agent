"""Tests for the deduplication module (memory/dedup.py)."""

import sys
import shutil
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.dedup import (
    normalize_title,
    find_duplicate,
    merge_contents,
    cleanup_duplicates,
    VAULT_ROOT,
)


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault directory and patch VAULT_ROOT."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required'):
        (vault / mtype).mkdir()
    # Write a minimal _index.md
    (vault / '_index.md').write_text(
        '---\ntitle: "Vault Index"\n---\n\n| File | Type | Description | Date |\n|------|------|-------------|------|\n'
    )
    monkeypatch.setattr('memory.dedup.VAULT_ROOT', vault)
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
# TITLE NORMALIZATION
# ============================================================================

class TestNormalizeTitle:
    """Test normalize_title()."""

    def test_basic_normalization(self):
        """Should lowercase, strip punctuation, collapse whitespace."""
        assert normalize_title("Hello World!") == "hello world"
        assert normalize_title("AI/TX — February") == "ai tx february"

    def test_filler_word_removal(self):
        """Should remove filler words like 're:', 'fwd:', 'the', 'a', 'an'."""
        assert normalize_title("Re: The Contract Review") == "contract review"
        assert normalize_title("Fwd: A New Proposal") == "new proposal"
        assert normalize_title("FW: An Important Update") == "important update"

    def test_empty_and_whitespace(self):
        """Edge case: empty or whitespace-only input."""
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""

    def test_preserves_meaningful_words(self):
        """Should keep all non-filler words."""
        assert normalize_title("AITX Meetup February 2026") == "aitx meetup february 2026"


# ============================================================================
# DUPLICATE FINDING — PEOPLE
# ============================================================================

class TestFindDuplicatePeople:
    """Test find_duplicate() for people memory type."""

    def test_exact_name_match(self, tmp_path, monkeypatch):
        """Should match existing person file by name (case-insensitive)."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-chen-a1b2.md', {
            'name': 'Sarah Chen',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = find_duplicate("Sarah Chen — VP Engineering", "people")
        assert result is not None
        assert result.name == 'sarah-chen-a1b2.md'

    def test_name_param_override(self, tmp_path, monkeypatch):
        """Should use the name param if provided instead of parsing title."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'me.md', {
            'name': 'John Doe',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = find_duplicate("Me — Product Manager", "people", name="John Doe")
        assert result is not None
        assert result.name == 'me.md'

    def test_no_match_different_person(self, tmp_path, monkeypatch):
        """Should return None when no person matches."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-chen-a1b2.md', {
            'name': 'Sarah Chen',
            'date': '2026-02-20',
            'category': 'people',
        })

        result = find_duplicate("Alice Johnson — Legal", "people")
        assert result is None

    def test_empty_vault(self, tmp_path, monkeypatch):
        """Should return None when vault folder is empty."""
        _setup_vault(tmp_path, monkeypatch)
        result = find_duplicate("Anyone — Role", "people")
        assert result is None


# ============================================================================
# DUPLICATE FINDING — NON-PEOPLE
# ============================================================================

class TestFindDuplicateNonPeople:
    """Test find_duplicate() for non-people memory types."""

    def test_containment_match(self, tmp_path, monkeypatch):
        """Should match when one normalized title contains the other."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'commitments', 'aitx-meetup-a1b2.md', {
            'title': 'AI/TX February Meetup',
            'date': '2026-02-20',
            'category': 'commitments',
        })

        # Shorter title contained in the existing one
        result = find_duplicate("AITX Meetup", "commitments")
        assert result is not None
        assert result.name == 'aitx-meetup-a1b2.md'

    def test_fuzzy_match_above_threshold(self, tmp_path, monkeypatch):
        """Should match when fuzzy ratio >= 0.70."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'chose-react-for-frontend-a1b2.md', {
            'title': 'Chose React for Frontend Project',
            'date': '2026-02-20',
            'category': 'decisions',
        })

        # Similar but not identical title
        result = find_duplicate("React chosen for frontend project", "decisions")
        assert result is not None

    def test_no_match_below_threshold(self, tmp_path, monkeypatch):
        """Should return None when titles are dissimilar."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'chose-react-a1b2.md', {
            'title': 'Chose React for Frontend',
            'date': '2026-02-20',
            'category': 'decisions',
        })

        result = find_duplicate("Quarterly budget review approved", "decisions")
        assert result is None

    def test_empty_vault(self, tmp_path, monkeypatch):
        """Should return None when vault folder is empty."""
        _setup_vault(tmp_path, monkeypatch)
        result = find_duplicate("Anything", "commitments")
        assert result is None


# ============================================================================
# CONTENT MERGING
# ============================================================================

class TestMergeContents:
    """Test merge_contents()."""

    def test_frontmatter_union_tags(self, tmp_path, monkeypatch):
        """Tags and related_to should be merged as set unions."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'commitments', 'meeting-a1b2.md', {
            'title': 'Weekly Meeting',
            'date': '2026-02-20',
            'category': 'commitments',
            'tags': ['work', 'meetings'],
            'related_to': ['Alice'],
        }, body='Existing content here.')

        merged_fm, merged_body = merge_contents(
            existing,
            'New content about meeting.',
            {'tags': ['meetings', 'schedule'], 'related_to': ['Bob']},
        )

        assert set(merged_fm['tags']) == {'work', 'meetings', 'schedule'}
        assert set(merged_fm['related_to']) == {'Alice', 'Bob'}

    def test_preserves_existing_nonempty_values(self, tmp_path, monkeypatch):
        """Should NOT overwrite existing non-empty scalar fields."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'commitments', 'meeting-a1b2.md', {
            'title': 'Weekly Meeting',
            'date': '2026-02-20',
            'category': 'commitments',
            'priority': '🔴',
        }, body='Existing.')

        merged_fm, _ = merge_contents(
            existing,
            'New.',
            {'title': 'Different Title', 'priority': '🟢'},
        )

        # Existing values should be preserved
        assert merged_fm['title'] == 'Weekly Meeting'
        assert merged_fm['priority'] == '🔴'

    def test_fills_empty_fields(self, tmp_path, monkeypatch):
        """Should fill fields that are empty/falsy in existing."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'commitments', 'meeting-a1b2.md', {
            'title': 'Meeting',
            'date': '2026-02-20',
            'category': 'commitments',
            'deadline': '',
        }, body='Content.')

        merged_fm, _ = merge_contents(
            existing,
            'New.',
            {'deadline': '2026-03-01'},
        )

        assert merged_fm['deadline'] == '2026-03-01'

    def test_people_appends_key_interactions(self, tmp_path, monkeypatch):
        """For people files, new Key Interactions should be appended."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-02-20',
            'category': 'people',
        }, body='## Overview\n\nAlice is a colleague.\n\n## Key Interactions\n\n### 2026-02-20\nFirst meeting.')

        new_body = '## Key Interactions\n\n### 2026-02-23\nSecond meeting about Q2 plans.'

        _, merged_body = merge_contents(existing, new_body, {})

        assert '2026-02-20' in merged_body
        assert 'First meeting' in merged_body
        assert '2026-02-23' in merged_body
        assert 'Second meeting' in merged_body

    def test_generic_appends_different_content(self, tmp_path, monkeypatch):
        """For non-people, substantially different content should be appended."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'decisions', 'react-a1b2.md', {
            'title': 'Chose React',
            'date': '2026-02-20',
            'category': 'decisions',
        }, body='We chose React because of its ecosystem.')

        _, merged_body = merge_contents(
            existing,
            'Additional context: team already had React experience from prior projects.',
            {},
        )

        assert 'ecosystem' in merged_body
        assert 'Additional context' in merged_body
        assert '---' in merged_body  # separator between old and new

    def test_generic_skips_similar_content(self, tmp_path, monkeypatch):
        """For non-people, nearly identical content should NOT be appended."""
        vault = _setup_vault(tmp_path, monkeypatch)
        existing = _write_vault_file(vault, 'decisions', 'react-a1b2.md', {
            'title': 'Chose React',
            'date': '2026-02-20',
            'category': 'decisions',
        }, body='We chose React because of its ecosystem.')

        _, merged_body = merge_contents(
            existing,
            'We chose React because of its ecosystem.',
            {},
        )

        # Should NOT have a --- separator (content is identical)
        assert merged_body.count('---') == 0


# ============================================================================
# CLEANUP DUPLICATES
# ============================================================================

class TestCleanupDuplicates:
    """Test cleanup_duplicates()."""

    def test_merges_people_duplicates(self, tmp_path, monkeypatch):
        """Should merge multiple files for the same person into the oldest."""
        vault = _setup_vault(tmp_path, monkeypatch)
        monkeypatch.setattr('memory.dedup.VAULT_ROOT', vault)
        # Also patch the import inside cleanup_duplicates
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-02-18',
            'category': 'people',
            'tags': ['team'],
        }, body='Original Alice file.')

        _write_vault_file(vault, 'people', 'alice-johnson-c3d4.md', {
            'name': 'Alice',
            'date': '2026-02-20',
            'category': 'people',
            'tags': ['legal'],
        }, body='Duplicate Alice file.')

        _write_vault_file(vault, 'people', 'alice-j-e5f6.md', {
            'name': 'Alice',
            'date': '2026-02-22',
            'category': 'people',
            'tags': ['contracts'],
        }, body='Third Alice file.')

        result = cleanup_duplicates()

        # Should have merged and deleted 2 duplicates
        assert result['deleted'] == 2
        assert result['merged'] >= 1

        # Only the oldest file should remain
        remaining = list((vault / 'people').glob('*.md'))
        assert len(remaining) == 1
        assert remaining[0].name == 'alice-a1b2.md'

        # Tags should be merged
        fm = yaml.safe_load(remaining[0].read_text().split('---')[1])
        assert set(fm['tags']) == {'team', 'legal', 'contracts'}

    def test_empty_vault_returns_zeros(self, tmp_path, monkeypatch):
        """Should return zero stats when vault has no duplicates."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        result = cleanup_duplicates()

        assert result['merged'] == 0
        assert result['deleted'] == 0

    def test_no_false_positives(self, tmp_path, monkeypatch):
        """Should NOT merge files for different people."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice Johnson',
            'date': '2026-02-18',
            'category': 'people',
        }, body='Alice.')

        _write_vault_file(vault, 'people', 'bob-c3d4.md', {
            'name': 'Bob Smith',
            'date': '2026-02-20',
            'category': 'people',
        }, body='Bob.')

        result = cleanup_duplicates()

        assert result['deleted'] == 0
        remaining = list((vault / 'people').glob('*.md'))
        assert len(remaining) == 2


# ============================================================================
# INTEGRATION TESTS — write_memory() with dedup
# ============================================================================

class TestWriteMemoryDedup:
    """Test that write_memory() integrates with dedup correctly."""

    def test_people_dedup_via_write_memory(self, tmp_path, monkeypatch):
        """Writing the same person twice should update the existing file, not create a new one."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        # Patch rebuild_graph to avoid scanning the real vault
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': {}}):
            from memory.vault import write_memory

            # First write
            path1 = write_memory(
                title="Sarah Chen — VP Engineering",
                memory_type="people",
                content="## Overview\n\nSarah leads the engineering team.",
                tags=["engineering"],
                name="Sarah Chen",
            )

            # Second write — same person, different title variation
            path2 = write_memory(
                title="Sarah Chen — CTO",
                memory_type="people",
                content="## Overview\n\nSarah was promoted to CTO.\n\n## Key Interactions\n\n### 2026-02-23\nDiscussed roadmap.",
                tags=["leadership"],
                name="Sarah Chen",
            )

        # Both writes should have gone to the same file
        assert Path(path1).name == Path(path2).name

        # Only one file should exist
        people_files = list((vault / 'people').glob('*.md'))
        assert len(people_files) == 1

    def test_commitment_dedup_via_write_memory(self, tmp_path, monkeypatch):
        """Writing similar commitments should merge into existing file."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': {}}):
            from memory.vault import write_memory

            # First write
            path1 = write_memory(
                title="AI/TX February Meetup RSVP",
                memory_type="commitments",
                content="RSVPed to the AI/TX meetup on Feb 25.",
                tags=["meetup", "ai"],
            )

            # Second write — similar title
            path2 = write_memory(
                title="AITX Meetup February",
                memory_type="commitments",
                content="Will attend the AITX meetup. Bring business cards.",
                tags=["networking"],
            )

        # Both should point to the same file
        assert Path(path1).name == Path(path2).name

        # Only one file should exist
        commitment_files = list((vault / 'commitments').glob('*.md'))
        assert len(commitment_files) == 1

        # Tags should be merged
        fm_text = commitment_files[0].read_text()
        fm = yaml.safe_load(fm_text.split('---')[1])
        assert 'meetup' in fm['tags']
        assert 'networking' in fm['tags']
        assert 'ai' in fm['tags']

    def test_dissimilar_memories_create_separate_files(self, tmp_path, monkeypatch):
        """Writing unrelated memories should create separate files."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.vault
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': {}}):
            from memory.vault import write_memory

            path1 = write_memory(
                title="Chose React for Frontend",
                memory_type="decisions",
                content="Team decided on React.",
            )

            path2 = write_memory(
                title="Quarterly Budget Approved",
                memory_type="decisions",
                content="Q2 budget was approved at $50k.",
            )

        # Should be different files
        assert Path(path1).name != Path(path2).name

        # Two files should exist
        decision_files = list((vault / 'decisions').glob('*.md'))
        assert len(decision_files) == 2
