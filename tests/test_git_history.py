"""Tests for vault git history module (memory/git_history.py)."""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.git_history import (
    is_vault_repo,
    init_vault_repo,
    commit_vault_changes,
    get_vault_log,
)


def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault directory and patch VAULT_ROOT."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.git_history.VAULT_ROOT', vault)
    return vault


def _write_file(path: Path, content: str = 'test content'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


class TestIsVaultRepo:
    def test_returns_false_for_uninitialized_vault(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        assert is_vault_repo() is False

    def test_returns_true_after_init(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        assert is_vault_repo() is True


class TestInitVaultRepo:
    def test_creates_git_directory(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        assert (vault / '.git').is_dir()

    def test_creates_gitignore_with_excluded_files(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        gitignore = vault / '.gitignore'
        assert gitignore.exists()
        text = gitignore.read_text(encoding='utf-8')
        assert '_processed_emails.json' in text
        assert '_file_state.json' in text

    def test_init_is_idempotent(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        init_vault_repo()  # Should not crash or overwrite
        assert is_vault_repo() is True


class TestCommitVaultChanges:
    def test_commits_staged_files(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()

        _write_file(vault / 'people' / 'alice.md', '# Alice\n\nTest person.')

        result = commit_vault_changes("Add Alice")
        assert result is True

        # Verify commit exists via git log
        log_output = subprocess.run(
            ['git', '-C', str(vault), 'log', '--oneline'],
            capture_output=True, text=True,
        ).stdout
        assert 'Add Alice' in log_output

    def test_no_changes_returns_false(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()

        # Nothing changed since init — commit should be a no-op
        result = commit_vault_changes("Empty commit attempt")
        assert result is False

    def test_excluded_files_not_committed(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()

        # Create an excluded file
        _write_file(vault / '_processed_emails.json', '["msg1", "msg2"]')
        # Also create an included file
        _write_file(vault / 'people' / 'bob.md', '# Bob\n\nTest.')

        commit_vault_changes("Add Bob")

        # Check what's in the tree
        tree_output = subprocess.run(
            ['git', '-C', str(vault), 'ls-tree', '-r', 'HEAD', '--name-only'],
            capture_output=True, text=True,
        ).stdout
        assert 'people/bob.md' in tree_output
        assert '_processed_emails.json' not in tree_output


class TestGetVaultLog:
    def test_returns_empty_for_no_commits(self, tmp_path, monkeypatch):
        _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        log = get_vault_log()
        assert log == []

    def test_returns_commits_in_reverse_chronological(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()

        _write_file(vault / 'people' / 'alice.md', '# Alice')
        commit_vault_changes("First commit")

        _write_file(vault / 'people' / 'bob.md', '# Bob')
        commit_vault_changes("Second commit")

        log = get_vault_log()
        assert len(log) == 2
        # Most recent first
        assert log[0]['message'] == 'Second commit'
        assert log[1]['message'] == 'First commit'

    def test_log_entry_has_required_fields(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        init_vault_repo()
        _write_file(vault / 'people' / 'alice.md', '# Alice')
        commit_vault_changes("Test")

        log = get_vault_log()
        entry = log[0]
        assert 'sha' in entry
        assert 'message' in entry
        assert 'timestamp' in entry


class TestOrchestratorInit:
    def test_orchestrator_init_creates_git_repo(self, tmp_path, monkeypatch):
        """Creating an Orchestrator should initialize the vault git repo."""
        vault = _setup_vault(tmp_path, monkeypatch)
        # Patch all vault paths the Orchestrator uses
        import memory.vault
        import memory.dedup
        import memory.changelog
        import memory.knowledge_index
        import memory.graph
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')
        monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.graph, 'VAULT_ROOT', vault)
        monkeypatch.setattr(memory.graph, 'GRAPH_FILE', vault / '_graph.json')

        # Creating the Orchestrator should initialize the git repo
        from orchestrator import Orchestrator
        _ = Orchestrator()

        assert is_vault_repo() is True
