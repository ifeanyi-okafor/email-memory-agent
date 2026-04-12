# tests/test_universal_confidence.py
"""Tests for universal confidence field across all entity types."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_vault(tmp_path, monkeypatch):
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


class TestConfidenceDefaults:
    def test_person_default_confidence(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Alice — PM",
                memory_type="people",
                content="## Overview\n\nPM.",
                name="Alice",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'medium'

    def test_decision_default_confidence(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Chose Postgres",
                memory_type="decisions",
                content="Picked Postgres.",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'medium'


class TestConfidenceExplicit:
    def test_high_confidence_for_people(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Alice — PM",
                memory_type="people",
                content="## Overview\n\nPM.",
                name="Alice",
                confidence="high",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'high'

    def test_low_confidence_for_actions(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Maybe renew cert",
                memory_type="action_required",
                content="Uncertain if renewal needed.",
                quadrant="important-not-urgent",
                confidence="low",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'low'

    def test_org_has_confidence(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Stripe",
                memory_type="organizations",
                content="## Overview\n\nPayments company.",
                org_domain="stripe.com",
                confidence="high",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'high'

    def test_project_has_confidence(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Series A",
                memory_type="projects",
                content="## Overview\n\nFundraising.",
                confidence="medium",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'medium'

    def test_commitment_has_confidence(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Meeting Feb 20",
                memory_type="commitments",
                content="Attend.",
                commitment_status="confirmed",
                confidence="high",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'high'


class TestInsightConfidenceUnchanged:
    def test_insights_still_accept_confidence(self, tmp_path, monkeypatch):
        """Insights already had confidence — verify it still works."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Pattern detected",
                memory_type="insights",
                content="## Analysis\n\nPattern.",
                insight_type="strategic_pattern",
                confidence="high",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['confidence'] == 'high'
