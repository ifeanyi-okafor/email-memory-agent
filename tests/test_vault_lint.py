# tests/test_vault_lint.py
"""Tests for vault lint checks (memory/vault_lint.py)."""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault_lint import run_lint_checks


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.vault_lint.VAULT_ROOT', vault)
    return vault


def _write_vault_file(vault_dir, memory_type, filename, frontmatter, body=''):
    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    heading = frontmatter.get('name') or frontmatter.get('title', filename)
    content = f"---\n{fm_str.strip()}\n---\n\n# {heading}\n\n{body}"
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


class TestLintStaleData:
    def test_detects_stale_action_items(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        _write_vault_file(vault, 'action_required', 'overdue-a1b2.md', {
            'title': 'Overdue Task',
            'category': 'action_required',
            'status': 'active',
            'deadline': yesterday,
            'quadrant': 'urgent-important',
        })
        results = run_lint_checks()
        stale = [r for r in results if r['check'] == 'stale_action_item']
        assert len(stale) == 1
        assert 'Overdue Task' in stale[0]['description']

    def test_ignores_closed_action_items(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        _write_vault_file(vault, 'action_required', 'closed-a1b2.md', {
            'title': 'Closed Task',
            'category': 'action_required',
            'status': 'closed',
            'deadline': yesterday,
            'quadrant': 'urgent-important',
        })
        results = run_lint_checks()
        stale = [r for r in results if r['check'] == 'stale_action_item']
        assert len(stale) == 0

    def test_future_deadline_not_stale(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        _write_vault_file(vault, 'action_required', 'future-a1b2.md', {
            'title': 'Future Task',
            'category': 'action_required',
            'status': 'active',
            'deadline': tomorrow,
            'quadrant': 'important-not-urgent',
        })
        results = run_lint_checks()
        stale = [r for r in results if r['check'] == 'stale_action_item']
        assert len(stale) == 0


class TestLintOrphanedFiles:
    def test_detects_orphaned_file(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'lonely-a1b2.md', {
            'title': 'Lonely Decision',
            'category': 'decisions',
            'related_to': [],
            'tags': [],
        })
        (vault / '_graph.json').write_text(json.dumps({
            'nodes': {'decisions/lonely-a1b2.md': {'title': 'Lonely Decision', 'type': 'decisions'}},
            'edges': [],
        }))
        results = run_lint_checks()
        orphaned = [r for r in results if r['check'] == 'orphaned_file']
        assert len(orphaned) == 1
        assert 'Lonely Decision' in orphaned[0]['description']

    def test_connected_file_not_orphaned(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'connected-a1b2.md', {
            'title': 'Connected Decision',
            'category': 'decisions',
            'related_to': ['Alice'],
        })
        (vault / '_graph.json').write_text(json.dumps({
            'nodes': {'decisions/connected-a1b2.md': {'title': 'Connected', 'type': 'decisions'}},
            'edges': [{'from': 'decisions/connected-a1b2.md', 'to': 'people/alice.md', 'relation': 'related_to'}],
        }))
        results = run_lint_checks()
        orphaned = [r for r in results if r['check'] == 'orphaned_file']
        assert len(orphaned) == 0


class TestLintEmptyFiles:
    def test_detects_empty_content(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'empty-a1b2.md', {
            'name': 'Empty Person',
            'category': 'people',
        }, body='')
        results = run_lint_checks()
        empty = [r for r in results if r['check'] == 'empty_content']
        assert len(empty) == 1


class TestLintCleanVault:
    def test_clean_vault_returns_empty(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        (vault / '_graph.json').write_text(json.dumps({'nodes': {}, 'edges': []}))
        results = run_lint_checks()
        assert results == []


class TestLintReturnFormat:
    def test_result_has_required_fields(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        _write_vault_file(vault, 'action_required', 'issue-a1b2.md', {
            'title': 'Issue Task',
            'category': 'action_required',
            'status': 'active',
            'deadline': yesterday,
            'quadrant': 'urgent-important',
        })
        results = run_lint_checks()
        assert len(results) >= 1
        result = results[0]
        assert 'check' in result
        assert 'severity' in result
        assert 'filepath' in result
        assert 'description' in result
        assert result['severity'] in ('error', 'warning', 'info')
