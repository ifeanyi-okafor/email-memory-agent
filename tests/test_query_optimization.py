# tests/test_query_optimization.py
"""Tests for QueryAgent context window optimization."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
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


class TestQueryAgentAcceptsIndex:
    def test_query_agent_has_ask_with_index_method(self):
        """QueryAgent should expose an `ask_with_index(question)` method."""
        from agents.query_agent import QueryAgent
        agent = QueryAgent()
        assert hasattr(agent, 'ask_with_index')

    def test_ask_with_index_injects_knowledge_index(self, tmp_path, monkeypatch):
        """ask_with_index should pass the Knowledge Index to the prompt."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', {
            'name': 'Alice',
            'email': 'alice@acme.com',
            'category': 'people',
            'confidence': 'high',
        })

        from agents.query_agent import QueryAgent
        agent = QueryAgent()

        # Mock the underlying run() method to capture the prompt
        captured_prompts = []
        def fake_run(prompt, **kwargs):
            captured_prompts.append(prompt)
            return "mocked response"
        agent.run = fake_run

        agent.ask_with_index("Who is Alice?")

        # The prompt sent to the LLM should include the index
        assert len(captured_prompts) == 1
        assert 'alice@acme.com' in captured_prompts[0]
        assert 'Knowledge Index' in captured_prompts[0]


class TestQueryAgentPromptGuidance:
    def test_system_prompt_mentions_index_first_strategy(self):
        """System prompt should tell agent to check index before full reads."""
        from agents.query_agent import QueryAgent
        agent = QueryAgent()
        prompt = agent.system_prompt

        # The prompt should explicitly guide the agent to the index-first approach
        assert 'Knowledge Index' in prompt
        assert 'metadata' in prompt.lower() or 'before reading full' in prompt.lower()
