# tests/test_vault_preview.py
#
# Tests for the vault memory preview: API endpoint returns content,
# and the read_memory function parses YAML frontmatter + markdown body.

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault import read_memory, write_memory, initialize_vault, VAULT_ROOT, list_memories


# Use a temporary vault for tests to avoid polluting the real vault
TEST_VAULT = Path('test_vault_preview_tmp')


@pytest.fixture(autouse=True)
def setup_test_vault():
    """Create a temporary vault before each test, clean up after."""
    with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
        initialize_vault()
        yield
    # Cleanup
    if TEST_VAULT.exists():
        shutil.rmtree(TEST_VAULT)


class TestReadMemoryContent:
    """Test that read_memory correctly parses frontmatter and content."""

    def test_read_memory_returns_content(self):
        """read_memory should return the markdown body in 'content' field."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Test Decision — Choose React",
                memory_type="decisions",
                content="We decided to go with React because of its ecosystem.\n\n## Reasoning\n\n- Large community\n- Good tooling",
                tags=["tech", "frontend"]
            )

            # Read it back — use relative path
            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            assert result is not None
            assert 'content' in result
            assert 'frontmatter' in result
            assert 'filepath' in result

            # Content should contain the markdown body (not empty)
            assert len(result['content']) > 0
            assert "React" in result['content']
            assert "## Reasoning" in result['content']
            assert "- Large community" in result['content']

    def test_read_memory_frontmatter_parsed(self):
        """Frontmatter should be parsed into a dict, not raw YAML."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Test Decision",
                memory_type="decisions",
                content="Some content here.",
                tags=["test"],
                priority="🟡"
            )

            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            assert isinstance(result['frontmatter'], dict)
            assert result['frontmatter']['title'] == "Test Decision"
            assert result['frontmatter']['category'] == "decisions"
            assert 'test' in result['frontmatter']['tags']

    def test_read_people_memory(self):
        """People memories use 'name' in frontmatter instead of 'title'."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Sarah Chen — CTO",
                memory_type="people",
                content="## Overview\nSarah is the CTO.\n\n## Key Interactions\n- Met at conference\n- Discussed architecture",
                tags=["work"],
                role="CTO",
                organization="Acme Corp",
                email="sarah@acme.com",
            )

            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            assert result is not None
            assert result['frontmatter'].get('name') == "Sarah Chen"
            assert result['frontmatter'].get('role') == "CTO"
            # Content should have the markdown sections
            assert "## Overview" in result['content']
            assert "## Key Interactions" in result['content']

    def test_read_memory_preserves_markdown(self):
        """Content should preserve all markdown formatting."""
        markdown = (
            "## Section One\n\n"
            "Some **bold** and *italic* text.\n\n"
            "### Subsection\n\n"
            "- Item 1\n"
            "- Item 2\n"
            "- Item 3\n\n"
            "> A blockquote\n\n"
            "[[Related Person]] mentioned this."
        )

        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Markdown Test",
                memory_type="decisions",
                content=markdown,
                tags=["test"]
            )

            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            assert "## Section One" in result['content']
            assert "**bold**" in result['content']
            assert "*italic*" in result['content']
            assert "### Subsection" in result['content']
            assert "- Item 1" in result['content']
            assert "> A blockquote" in result['content']
            assert "[[Related Person]]" in result['content']

    def test_read_nonexistent_memory(self):
        """Reading a nonexistent file should return None."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            result = read_memory("decisions/nonexistent.md")
            assert result is None

    def test_list_memories_returns_filepath(self):
        """list_memories should return filepaths usable by the API."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            write_memory(
                title="Test List Decision",
                memory_type="decisions",
                content="Content here.",
                tags=["test"]
            )

            memories = list_memories()
            assert len(memories) > 0

            mem = memories[0]
            assert 'filepath' in mem
            assert 'type' in mem
            assert 'title' in mem

            # Filepath should be relative (e.g., "decisions/test-list-decision-xxxx.md")
            assert '/' in mem['filepath'] or '\\' in mem['filepath']
            assert not Path(mem['filepath']).is_absolute()

            # Should be readable via read_memory
            result = read_memory(mem['filepath'])
            assert result is not None
            assert len(result['content']) > 0


class TestAPIEndpointChain:
    """Test the full API chain using FastAPI's test client."""

    def test_memory_endpoint_returns_content(self):
        """GET /api/memory/{type}/{file} should return frontmatter + content."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            # Write a test memory
            filepath = write_memory(
                title="API Test Decision",
                memory_type="decisions",
                content="## Details\n\nThis is the API test content.\n\n- Point one\n- Point two",
                tags=["api-test"]
            )

            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            parts = rel_path.replace('\\', '/').split('/')
            memory_type = parts[0]
            filename = parts[1]

            # Import and test via FastAPI test client
            from fastapi.testclient import TestClient

            # Patch vault root in both vault module and the app's imported copy
            with patch('memory.vault.VAULT_ROOT', TEST_VAULT), \
                 patch('web.app.initialize_vault'), \
                 patch('web.app.Orchestrator'):
                from web.app import app
                client = TestClient(app)

                resp = client.get(f"/api/memory/{memory_type}/{filename}")

                assert resp.status_code == 200
                data = resp.json()

                assert 'frontmatter' in data
                assert 'content' in data
                assert 'filepath' in data

                # Content should NOT be empty
                assert len(data['content']) > 0
                assert "API test content" in data['content']
                assert "## Details" in data['content']

    def test_memory_endpoint_404_for_missing(self):
        """GET /api/memory/{type}/{file} should return 404 for missing files."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT), \
             patch('web.app.initialize_vault'), \
             patch('web.app.Orchestrator'):
            from web.app import app
            from fastapi.testclient import TestClient
            client = TestClient(app)

            resp = client.get("/api/memory/decisions/nonexistent.md")
            assert resp.status_code == 404

    def test_memories_list_then_read(self):
        """GET /api/memories then GET /api/memory/{path} — full chain."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            write_memory(
                title="Chain Test",
                memory_type="commitments",
                content="## Commitment\n\nI committed to review PRs weekly.",
                tags=["work"]
            )

            with patch('memory.vault.VAULT_ROOT', TEST_VAULT), \
                 patch('web.app.initialize_vault'), \
                 patch('web.app.Orchestrator'):
                from web.app import app
                from fastapi.testclient import TestClient
                client = TestClient(app)

                # Step 1: List memories
                list_resp = client.get("/api/memories")
                assert list_resp.status_code == 200
                memories = list_resp.json()['memories']
                assert len(memories) > 0

                # Step 2: Use filepath from list to read the memory
                mem = memories[0]
                filepath = mem['filepath'].replace('\\', '/')
                resp = client.get(f"/api/memory/{filepath}")

                assert resp.status_code == 200
                data = resp.json()
                assert len(data['content']) > 0
                assert "review PRs" in data['content']
