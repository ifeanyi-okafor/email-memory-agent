# tests/test_changelog.py
#
# ============================================================================
# Tests for the append-only vault changelog (memory/changelog.py).
#
# We use pytest's `tmp_path` fixture to create a temporary directory for each
# test — this means tests never touch the real vault and can run in parallel
# without interfering with each other.
#
# We use `monkeypatch` to redirect the module's CHANGELOG_FILE constant to
# point at our temporary directory instead of the real vault.
# ============================================================================

import pytest
from datetime import datetime
from pathlib import Path

# Import the module under test
from memory import changelog
from memory.changelog import append_changelog, read_changelog


# ── TEST HELPER ────────────────────────────────────────────────────────

def _setup_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Create a temporary vault directory and patch the changelog module
    to use it instead of the real vault.

    This is called at the start of each test to ensure isolation.
    Every test gets its own fresh, empty vault directory.

    Args:
        tmp_path:    pytest-provided temporary directory (unique per test).
        monkeypatch: pytest fixture for safely patching module attributes.
    """
    # Create a "vault" subdirectory inside the temp dir
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Patch the CHANGELOG_FILE constant so the module writes to our
    # temporary directory instead of the real vault
    changelog_file = vault_dir / "_changelog.md"
    monkeypatch.setattr(changelog, "CHANGELOG_FILE", changelog_file)


# ============================================================================
# TEST: append_changelog
# ============================================================================

class TestAppendChangelog:
    """Tests for the append_changelog() function."""

    def test_creates_file_on_first_write(self, tmp_path, monkeypatch):
        """
        The very first append should create _changelog.md with the header
        and the first data row.

        Before any mutations happen, the changelog file doesn't exist.
        After the first append, it should exist and contain valid content.
        """
        _setup_vault(tmp_path, monkeypatch)

        # The file should not exist yet
        assert not changelog.CHANGELOG_FILE.exists()

        # Append the first entry
        append_changelog("CREATED", "people/sarah-chen-a1b2.md", "Sarah Chen")

        # Now the file should exist
        assert changelog.CHANGELOG_FILE.exists()

        # Read and verify content
        content = changelog.CHANGELOG_FILE.read_text(encoding='utf-8')

        # Should contain the header
        assert "# Vault Changelog" in content
        assert "| Timestamp | Action | File | Description |" in content

        # Should contain the data row
        assert "CREATED" in content
        assert "people/sarah-chen-a1b2.md" in content
        assert "Sarah Chen" in content

    def test_appends_to_existing_file(self, tmp_path, monkeypatch):
        """
        Multiple appends should produce multiple data rows, one per call.

        The changelog is append-only, so each call adds exactly one row
        without modifying previous entries.
        """
        _setup_vault(tmp_path, monkeypatch)

        # Append three entries
        append_changelog("CREATED", "people/alice.md", "Alice")
        append_changelog("UPDATED", "people/bob.md", "Bob")
        append_changelog("MERGED", "decisions/pick-react.md", "Pick React")

        # Read the full content
        content = changelog.CHANGELOG_FILE.read_text(encoding='utf-8')

        # Count data rows (lines starting with "| " that contain an action)
        data_rows = [
            line for line in content.split('\n')
            if line.startswith('| ') and any(
                action in line for action in ['CREATED', 'UPDATED', 'MERGED']
            )
        ]

        assert len(data_rows) == 3

        # Verify each entry is present
        assert "Alice" in content
        assert "Bob" in content
        assert "Pick React" in content

    def test_includes_timestamp(self, tmp_path, monkeypatch):
        """
        Each changelog entry should contain today's date in the timestamp.

        We check for today's date string (YYYY-MM-DD) to confirm the
        timestamp is being generated correctly.
        """
        _setup_vault(tmp_path, monkeypatch)

        append_changelog("CREATED", "decisions/test.md", "Test Decision")

        content = changelog.CHANGELOG_FILE.read_text(encoding='utf-8')

        # The timestamp should contain today's date
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in content

    def test_action_types(self, tmp_path, monkeypatch):
        """
        The changelog should correctly record all three action types:
        CREATED, UPDATED, and MERGED.

        Each action type represents a different kind of vault mutation:
        - CREATED: a brand new memory file was written
        - UPDATED: an existing memory file was modified
        - MERGED: two duplicate memories were combined into one
        """
        _setup_vault(tmp_path, monkeypatch)

        # Write one entry for each action type
        append_changelog("CREATED", "people/new.md", "New Person")
        append_changelog("UPDATED", "people/existing.md", "Updated Person")
        append_changelog("MERGED", "people/merged.md", "Merged Person")

        content = changelog.CHANGELOG_FILE.read_text(encoding='utf-8')

        # All three action types should appear in the content
        assert "| CREATED |" in content
        assert "| UPDATED |" in content
        assert "| MERGED |" in content


# ============================================================================
# TEST: read_changelog
# ============================================================================

class TestReadChangelog:
    """Tests for the read_changelog() function."""

    def test_read_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """
        Reading a changelog that doesn't exist should return an empty string.

        This happens when the vault is brand new and no mutations have
        occurred yet. The caller should handle this gracefully.
        """
        _setup_vault(tmp_path, monkeypatch)

        # The file doesn't exist yet
        assert not changelog.CHANGELOG_FILE.exists()

        # Should return empty string, not raise an error
        result = read_changelog()
        assert result == ""

    def test_read_returns_full_content(self, tmp_path, monkeypatch):
        """
        Reading without a limit should return the entire changelog,
        including the header and all data rows.
        """
        _setup_vault(tmp_path, monkeypatch)

        # Add some entries
        append_changelog("CREATED", "people/alice.md", "Alice")
        append_changelog("UPDATED", "decisions/test.md", "Test")

        # Read without limit
        result = read_changelog()

        # Should contain the header
        assert "# Vault Changelog" in result
        assert "| Timestamp | Action | File | Description |" in result

        # Should contain both entries
        assert "Alice" in result
        assert "Test" in result

    def test_read_with_limit(self, tmp_path, monkeypatch):
        """
        Reading with last_n should return only the N most recent entries
        plus the header.

        This is useful for showing "recent changes" without dumping the
        entire history. We add 10 entries and request only the last 3.
        """
        _setup_vault(tmp_path, monkeypatch)

        # Add 10 entries with numbered descriptions so we can tell them apart
        for i in range(1, 11):
            append_changelog("CREATED", f"decisions/item-{i}.md", f"Item {i}")

        # Read only the last 3
        result = read_changelog(last_n=3)

        # Should still contain the header
        assert "# Vault Changelog" in result
        assert "| Timestamp | Action | File | Description |" in result

        # Should contain the last 3 entries (items 8, 9, 10)
        assert "Item 8" in result
        assert "Item 9" in result
        assert "Item 10" in result

        # Should NOT contain the earlier entries
        # Note: we check for "Item 1 |" (with trailing pipe) to avoid
        # false matches like "Item 10" containing "Item 1".
        assert "Item 1 |" not in result
        assert "Item 7 |" not in result


# ============================================================================
# INTEGRATION — write_memory triggers changelog
# ============================================================================

class TestChangelogIntegration:
    def test_write_memory_appends_to_changelog(self, tmp_path, monkeypatch):
        """write_memory() should append an entry to the changelog."""
        vault = tmp_path / 'vault'
        vault.mkdir()
        for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
            (vault / mtype).mkdir()
        (vault / '_index.md').write_text(
            '---\ntitle: "Vault Index"\n---\n\n| File | Type | Description | Date |\n|------|------|-------------|------|\n'
        )

        import memory.vault
        import memory.changelog
        import memory.dedup
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')

        from unittest.mock import patch
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Test Decision",
                memory_type="decisions",
                content="We decided to test.",
            )

        changelog_path = vault / '_changelog.md'
        assert changelog_path.exists()
        content = changelog_path.read_text(encoding='utf-8')
        assert 'CREATED' in content
        assert 'Test Decision' in content

    def test_duplicate_write_shows_updated(self, tmp_path, monkeypatch):
        """Writing the same person twice should show UPDATED in changelog."""
        vault = tmp_path / 'vault'
        vault.mkdir()
        for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
            (vault / mtype).mkdir()
        (vault / '_index.md').write_text(
            '---\ntitle: "Vault Index"\n---\n\n| File | Type | Description | Date |\n|------|------|-------------|------|\n'
        )

        import memory.vault
        import memory.changelog
        import memory.dedup
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')

        from unittest.mock import patch
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Bob Smith — Engineer",
                memory_type="people",
                content="## Overview\n\nEngineer.",
                name="Bob Smith",
            )
            write_memory(
                title="Bob Smith — Senior Engineer",
                memory_type="people",
                content="## Overview\n\nPromoted to Senior Engineer.",
                name="Bob Smith",
            )

        content = (vault / '_changelog.md').read_text(encoding='utf-8')
        assert 'CREATED' in content
        assert 'UPDATED' in content
