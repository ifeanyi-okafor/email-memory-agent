# tests/test_markdown_renderer.py
#
# Tests for the frontend markdown renderer by exercising the full
# vault preview chain: write memory → read via API → verify content
# is properly structured for rendering.
#
# We also test the full API chain end-to-end with realistic vault content.

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault import read_memory, write_memory, initialize_vault, VAULT_ROOT


TEST_VAULT = Path('test_markdown_tmp')


@pytest.fixture(autouse=True)
def setup_test_vault():
    """Create a temporary vault before each test, clean up after."""
    with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
        initialize_vault()
        yield
    if TEST_VAULT.exists():
        shutil.rmtree(TEST_VAULT)


class TestMarkdownContentPreservation:
    """Test that vault content preserves all markdown structures."""

    def test_headers_preserved(self):
        """All header levels (h1-h4) should be preserved in content."""
        md = "# Top Level\n\n## Section\n\n### Subsection\n\n#### Detail"
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="Header Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            # The content includes the # Title heading added by write_memory
            assert "## Section" in result['content']
            assert "### Subsection" in result['content']
            assert "#### Detail" in result['content']

    def test_bold_and_italic_preserved(self):
        """Bold and italic markers should be preserved."""
        md = "This is **bold** and this is *italic* and this is ***both***."
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="Format Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "**bold**" in result['content']
            assert "*italic*" in result['content']

    def test_lists_preserved(self):
        """Unordered and ordered lists should be preserved."""
        md = "- Item one\n- Item two\n- Item three\n\n1. First\n2. Second\n3. Third"
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="List Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "- Item one" in result['content']
            assert "- Item two" in result['content']
            assert "1. First" in result['content']

    def test_blockquote_preserved(self):
        """Blockquotes should be preserved."""
        md = "> This is a quote from an email."
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="Quote Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "> This is a quote" in result['content']

    def test_code_preserved(self):
        """Inline code should be preserved."""
        md = "Use the `fetch` function to call the API."
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="Code Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "`fetch`" in result['content']

    def test_wiki_links_preserved(self):
        """Wiki-links like [[Name]] should be preserved."""
        md = "Discussed this with [[Sarah Chen]] and [[Bob Smith]]."
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="Link Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "[[Sarah Chen]]" in result['content']
            assert "[[Bob Smith]]" in result['content']

    def test_horizontal_rule_preserved(self):
        """Horizontal rules should be preserved."""
        md = "Section one\n\n---\n\nSection two"
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(title="HR Test", memory_type="decisions", content=md)
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert "---" in result['content']

    def test_person_template_structure(self):
        """A realistic person memory should have all sections readable."""
        content = (
            "## Overview\n"
            "Senior engineer who leads the platform team.\n\n"
            "## Key Interactions\n"
            "- 2026-02-15: Discussed migration plan\n"
            "- 2026-02-10: Code review feedback\n\n"
            "## Topics of Interest\n"
            "- Distributed systems\n"
            "- Rust programming\n\n"
            "## Communication Style\n"
            "Direct and technical. Prefers Slack over email.\n\n"
            "## Preferences\n"
            "- Morning standup at 9am\n"
            "- Async communication\n"
        )
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Alex Johnson — Platform Lead",
                memory_type="people",
                content=content,
                role="Platform Lead",
                organization="TechCo",
                email="alex@techco.com",
            )
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))

            assert result is not None
            assert "## Overview" in result['content']
            assert "## Key Interactions" in result['content']
            assert "## Topics of Interest" in result['content']
            assert "## Communication Style" in result['content']
            assert "## Preferences" in result['content']
            assert "- Distributed systems" in result['content']
            assert "Morning standup" in result['content']

    def test_me_file_content(self):
        """The special me.md file should be readable with rich content."""
        content = (
            "## Overview\n"
            "Software engineer working on AI projects.\n\n"
            "## Communication Style\n"
            "Writes detailed emails. Responds quickly.\n\n"
            "## Topics of Interest\n"
            "- Machine learning\n"
            "- TypeScript\n"
            "- System design\n\n"
            "## Preferences\n"
            "- Dark mode everywhere\n"
            "- Morning deep work blocks\n"
        )
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Me — Software Engineer",
                memory_type="people",
                content=content,
            )
            # Verify the file is me.md (not me-xxxx.md)
            assert filepath.endswith('me.md')

            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert result is not None
            assert "## Overview" in result['content']
            assert "Machine learning" in result['content']
            assert "Dark mode" in result['content']

    def test_me_file_with_real_name(self):
        """When name param is provided, me.md frontmatter shows the real name."""
        content = "## Overview\nSoftware engineer at TechCo.\n"
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Me — Software Engineer",
                memory_type="people",
                content=content,
                name="John Doe",
            )
            # Filename should still be me.md (routed by title)
            assert filepath.endswith('me.md')

            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert result is not None
            # Frontmatter should show the real name, not "Me"
            assert result['frontmatter']['name'] == "John Doe"
            # The heading should use the real name too
            assert "# John Doe" in result['content']

    def test_me_file_without_name_shows_me(self):
        """Without name param, me.md frontmatter falls back to 'Me'."""
        content = "## Overview\nSoftware engineer.\n"
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Me — Software Engineer",
                memory_type="people",
                content=content,
            )
            result = read_memory(str(Path(filepath).relative_to(TEST_VAULT)))
            assert result['frontmatter']['name'] == "Me"


class TestFullAPIChainWithMarkdown:
    """Test the complete API chain with realistic markdown content."""

    def test_api_returns_renderable_markdown(self):
        """The API should return content that contains markdown formatting."""
        content = (
            "## Decision Context\n\n"
            "We needed to choose a **database** for the new service.\n\n"
            "## Options Considered\n\n"
            "1. PostgreSQL — *mature and reliable*\n"
            "2. MongoDB — flexible schema\n"
            "3. DynamoDB — managed service\n\n"
            "## Outcome\n\n"
            "Chose PostgreSQL because:\n"
            "- Strong ACID guarantees\n"
            "- Team experience with `SQL`\n"
            "- [[Alex Johnson]] recommended it\n\n"
            "> \"Always pick the boring technology\" — Dan McKinley\n"
        )
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Database Selection — PostgreSQL",
                memory_type="decisions",
                content=content,
                tags=["architecture", "database"],
                related_to=["Alex Johnson"],
            )

            with patch('memory.vault.VAULT_ROOT', TEST_VAULT), \
                 patch('web.app.initialize_vault'), \
                 patch('web.app.Orchestrator'):
                from web.app import app
                from fastapi.testclient import TestClient
                client = TestClient(app)

                rel_path = str(Path(filepath).relative_to(TEST_VAULT)).replace('\\', '/')
                resp = client.get(f"/api/memory/{rel_path}")
                assert resp.status_code == 200
                data = resp.json()

                c = data['content']
                # Verify markdown structures survive the full API chain
                assert "## Decision Context" in c
                assert "**database**" in c
                assert "## Options Considered" in c
                assert "1. PostgreSQL" in c
                assert "*mature and reliable*" in c
                assert "- Strong ACID" in c
                assert "`SQL`" in c
                assert "[[Alex Johnson]]" in c
                assert "> " in c  # Blockquote preserved

    def test_api_people_memory_with_all_sections(self):
        """People memory with full template should return all sections."""
        content = (
            "## Overview\nPlatform lead at TechCo.\n\n"
            "## Key Interactions\n"
            "- Discussed migration\n"
            "- Reviewed architecture doc\n\n"
            "## Topics of Interest\n- Kubernetes\n- Go\n\n"
            "## Communication Style\nConcise. Uses bullet points.\n\n"
            "## Preferences\n- Afternoon meetings\n"
        )
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Test Person — Platform Lead",
                memory_type="people",
                content=content,
                role="Platform Lead",
                organization="TechCo",
                email="test@techco.com",
            )

            with patch('memory.vault.VAULT_ROOT', TEST_VAULT), \
                 patch('web.app.initialize_vault'), \
                 patch('web.app.Orchestrator'):
                from web.app import app
                from fastapi.testclient import TestClient
                client = TestClient(app)

                rel_path = str(Path(filepath).relative_to(TEST_VAULT)).replace('\\', '/')
                resp = client.get(f"/api/memory/{rel_path}")
                assert resp.status_code == 200
                data = resp.json()

                c = data['content']
                assert "## Overview" in c
                assert "## Key Interactions" in c
                assert "## Topics of Interest" in c
                assert "## Communication Style" in c
                assert "## Preferences" in c
                assert "- Kubernetes" in c

                # Frontmatter should have people-specific fields
                fm = data['frontmatter']
                assert fm.get('name') == "Test Person"
                assert fm.get('role') == "Platform Lead"
                assert fm.get('email') == "test@techco.com"
