# Vault Priority 4 & 5: Git History, Universal Status, Confidence, Query Optimization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Priority 4 adds git auto-commits for vault history and universal status fields (status/status_reason/status_updated) to people, decisions, and commitments. Priority 5 adds a universal confidence field to all memory types and optimizes QueryAgent to use the Knowledge Index before reading full files.

**Architecture:** Priority 4 uses `subprocess` calls to git (no new dependencies) to auto-commit the vault after each pipeline stage — driven by the existing changelog. Status fields follow the exact pattern already proven by `action_required`. Priority 5 adds `confidence` as a simple parameter on `write_memory()` and updates frontmatter on all types. Query optimization injects the Knowledge Index into the QueryAgent's prompt on every run so the agent can answer from metadata alone for most questions.

**Tech Stack:** Python stdlib (`subprocess`, `pathlib`), pytest, yaml — no new dependencies

---

## File Structure

### Priority 4: Git History + Universal Status

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `memory/git_history.py` | Git operations wrapper (init, add, commit, log) using subprocess |
| Modify | `orchestrator.py` | Auto-commit after each build pipeline stage |
| Modify | `memory/vault.py` | Add `status`/`status_reason`/`status_updated` params + frontmatter for people, decisions, commitments |
| Modify | `agents/memory_writer.py` | Teach agents to set status on state-change events |
| Create | `tests/test_git_history.py` | Git wrapper tests |
| Create | `tests/test_universal_status.py` | Status field tests for all types |

### Priority 5: Confidence + Query Optimization

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `memory/vault.py` | Add universal `confidence` parameter + frontmatter on all types |
| Modify | `memory/knowledge_index.py` | Include confidence column in all index tables |
| Modify | `agents/email_reader.py` | Instruct agent to emit confidence scores |
| Modify | `agents/memory_writer.py` | Pass confidence through to write_memory |
| Modify | `agents/query_agent.py` | Inject Knowledge Index into prompt; prefer metadata over full reads |
| Create | `tests/test_universal_confidence.py` | Confidence field tests |
| Create | `tests/test_query_optimization.py` | Query agent context tests |

---

# PRIORITY 4: GIT HISTORY + UNIVERSAL STATUS

## Task 1: Git History Module

**Files:**
- Create: `memory/git_history.py`
- Test: `tests/test_git_history.py`

### Step 1.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_git_history.py
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
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_git_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memory.git_history'`

### Step 1.2: Implement the git history module

- [ ] **Create `memory/git_history.py`**

```python
# memory/git_history.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Manages a git repository inside the vault folder, enabling a full
# version history of every vault mutation. Uses subprocess calls to
# git (no GitPython dependency).
#
# The vault is its own standalone git repo — separate from the project
# git repo. This means every pipeline run can auto-commit the vault
# state without touching the project's main repo.
#
# Inspired by Rowboat's version_history.ts — commits after every batch
# so the user has a full timeline of vault evolution.
# ============================================================================

import subprocess
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path('vault')

# Files that should NEVER be committed — internal tracking and state
_GITIGNORE_ENTRIES = [
    "_processed_emails.json",
    "_file_state.json",
    "scheduler_state.json",
    ".DS_Store",
    "Thumbs.db",
]


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command inside the vault directory."""
    return subprocess.run(
        ['git', '-C', str(VAULT_ROOT)] + args,
        capture_output=True,
        text=True,
        check=check,
    )


def is_vault_repo() -> bool:
    """Check whether the vault has been initialized as a git repo."""
    return (VAULT_ROOT / '.git').is_dir()


def init_vault_repo():
    """
    Initialize the vault as a git repository if not already.

    Creates `.git/` and a `.gitignore` excluding internal tracking files.
    Idempotent — safe to call on an already-initialized vault.
    """
    if not VAULT_ROOT.exists():
        VAULT_ROOT.mkdir(parents=True)

    if not is_vault_repo():
        _run_git(['init', '-b', 'main'])

        # Configure a local user for commits (required by git)
        _run_git(['config', 'user.email', 'vault@email-memory-agent.local'])
        _run_git(['config', 'user.name', 'Vault Auto-Commit'])

    # Always (re)write .gitignore to keep excluded files up to date
    gitignore_path = VAULT_ROOT / '.gitignore'
    gitignore_path.write_text('\n'.join(_GITIGNORE_ENTRIES) + '\n', encoding='utf-8')


def _has_changes() -> bool:
    """Check whether there are any uncommitted changes in the vault."""
    result = _run_git(['status', '--porcelain'])
    return bool(result.stdout.strip())


def commit_vault_changes(message: str) -> bool:
    """
    Stage all vault changes and create a commit.

    Args:
        message: Commit message.

    Returns:
        True if a commit was created, False if there were no changes.
    """
    if not is_vault_repo():
        init_vault_repo()

    # Stage all changes (respects .gitignore)
    _run_git(['add', '-A'])

    if not _has_changes():
        return False

    _run_git(['commit', '-m', message])
    return True


def get_vault_log(limit: int = 50) -> list[dict]:
    """
    Get recent vault commits in reverse chronological order.

    Returns:
        List of dicts with sha, message, timestamp (ISO format).
    """
    if not is_vault_repo():
        return []

    # Use a format string that's easy to parse: sha<TAB>timestamp<TAB>message
    result = _run_git(
        ['log', f'-n{limit}', '--format=%H%x09%aI%x09%s'],
        check=False,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return []

    entries = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t', 2)
        if len(parts) == 3:
            entries.append({
                'sha': parts[0],
                'timestamp': parts[1],
                'message': parts[2],
            })

    return entries
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_git_history.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/git_history.py tests/test_git_history.py
git commit -m "feat: add vault git history module for auto-commits"
```

---

## Task 2: Wire Git History into Orchestrator

**Files:**
- Modify: `orchestrator.py` (build_memory pipeline — auto-commit after each stage)

### Step 2.1: Modify orchestrator to auto-commit after pipeline stages

- [ ] **Modify `orchestrator.py`**

**a)** Add import at the top (after existing memory imports):

```python
from memory.git_history import init_vault_repo, commit_vault_changes, is_vault_repo
```

**b)** In the `Orchestrator.__init__` method (right after `initialize_vault()`), add:

```python
        # Initialize the vault as a git repository if not already
        init_vault_repo()
```

**c)** In `build_memory()`, after "Step 3: Memory Writer" completes (find the `save_processed_email_ids(updated_ids)` line), add:

```python
        # ── Auto-commit after memory writer ─────────────────
        commit_vault_changes(f"Memory write: {len(emails)} emails processed")
```

**d)** After "Step 3.5: Rebuild knowledge graph" completes, add:

```python
        commit_vault_changes("Rebuild knowledge graph")
```

**e)** After "Step 4: Action Agent" completes (after the `action_result = ...` line), add:

```python
        commit_vault_changes("Generate action items")
```

**f)** After "Step 5: Reconciliation Agent", add:

```python
        commit_vault_changes("Reconcile action item statuses")
```

**g)** After "Step 6: Insights Agent", add:

```python
        commit_vault_changes("Generate insights")
```

### Step 2.2: Write integration test

- [ ] **Add to `tests/test_git_history.py`**

```python
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
```

- [ ] **Run tests**

Run: `python -m pytest tests/test_git_history.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add orchestrator.py tests/test_git_history.py
git commit -m "feat: auto-commit vault after each pipeline stage"
```

---

## Task 3: Universal Status Fields for People

**Files:**
- Modify: `memory/vault.py` (write_memory params + people frontmatter branch)
- Create: `tests/test_universal_status.py`

### Step 3.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_universal_status.py
"""Tests for universal status fields across all entity types."""

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


class TestPeopleStatus:
    def test_person_default_status_is_active(self, tmp_path, monkeypatch):
        """People without explicit status should default to 'active'."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Alice Park — Designer",
                memory_type="people",
                content="## Overview\n\nDesigner.",
                name="Alice Park",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'active'

    def test_person_with_explicit_status(self, tmp_path, monkeypatch):
        """People with explicit status should record it."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Bob — Engineer",
                memory_type="people",
                content="## Overview\n\nFormer engineer.",
                name="Bob",
                status="left-org",
                status_reason="Left Acme in March 2026 to join Stripe",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'left-org'
        assert 'Left Acme' in fm['status_reason']
        assert fm['status_updated']  # auto-populated

    def test_person_status_updated_autofills(self, tmp_path, monkeypatch):
        """status_updated should default to today when status is set."""
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Charlie — PM",
                memory_type="people",
                content="## Overview\n\nPM.",
                name="Charlie",
                status="inactive",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        assert fm['status_updated'] == today
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_universal_status.py::TestPeopleStatus -v`
Expected: FAIL — status field not in people frontmatter

### Step 3.2: Add status fields to people frontmatter

- [ ] **Modify `memory/vault.py` write_memory signature**

The function already has `status`, `status_reason`, `status_updated` parameters (used by action_required). No signature change needed — just use them in the people branch.

- [ ] **Modify the people frontmatter branch in `memory/vault.py`**

In the people frontmatter branch (the `if memory_type == 'people':` block), find the `frontmatter = {...}` dict. Add these three lines to the dict (before `'tags': tags or [],`):

```python
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_universal_status.py::TestPeopleStatus -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_universal_status.py
git commit -m "feat: add universal status fields to people memories"
```

---

## Task 4: Universal Status Fields for Decisions + Commitments

**Files:**
- Modify: `memory/vault.py` (decisions + commitments frontmatter branches)
- Test: `tests/test_universal_status.py` (add tests)

### Step 4.1: Write failing tests

- [ ] **Add tests to `tests/test_universal_status.py`**

```python
class TestDecisionsStatus:
    def test_decision_default_status_is_active(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Chose React for Frontend",
                memory_type="decisions",
                content="Team decided.",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'active'

    def test_decision_can_be_reversed(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Chose MongoDB",
                memory_type="decisions",
                content="Chose MongoDB initially.",
                status="reversed",
                status_reason="Switched to Postgres after performance issues",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'reversed'
        assert 'Postgres' in fm['status_reason']


class TestCommitmentsStatus:
    def test_commitment_default_status_is_active(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Q2 Review Meeting",
                memory_type="commitments",
                content="Attend Q2 review.",
                commitment_status="confirmed",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        # Both status fields present
        assert fm['commitment_status'] == 'confirmed'
        assert fm['status'] == 'active'  # general lifecycle status

    def test_commitment_completed_status(self, tmp_path, monkeypatch):
        vault = _setup_vault(tmp_path, monkeypatch)
        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Hyrox Race Feb 28",
                memory_type="commitments",
                content="Race completed.",
                commitment_status="confirmed",
                status="completed",
                status_reason="Event took place and user participated",
            )
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['status'] == 'completed'
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_universal_status.py::TestDecisionsStatus tests/test_universal_status.py::TestCommitmentsStatus -v`
Expected: FAIL — status field not in these types' frontmatter

### Step 4.2: Add status to decisions and commitments branches

- [ ] **Modify decisions frontmatter in `memory/vault.py`**

The decisions type currently falls through to the `else:` branch (standard frontmatter). Find the standard frontmatter dict and add status fields there:

```python
        frontmatter = {
            'title': title,
            'date': today,
            'category': memory_type,
            'memoryType': memory_type,
            'priority': priority,
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
            'tags': tags or [],
            'related_to': related_to or [],
        }
```

- [ ] **Modify commitments frontmatter in `memory/vault.py`**

In the `elif memory_type == 'commitments':` branch, find the frontmatter dict and add the three status fields before `'tags':`:

```python
        frontmatter = {
            'title': title,
            'date': today,
            'category': 'commitments',
            'memoryType': 'commitments',
            'priority': priority,
            'commitment_status': commitment_status or 'invited',
            'status': status or 'active',
            'status_reason': status_reason or '',
            'status_updated': status_updated or today,
            'tags': tags or [],
            'related_to': related_to or [],
        }
```

- [ ] **Run tests**

Run: `python -m pytest tests/test_universal_status.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_universal_status.py
git commit -m "feat: add universal status fields to decisions and commitments"
```

---

## Task 5: Teach Agents to Use Status Fields

**Files:**
- Modify: `agents/memory_writer.py` (system prompt)
- Modify: `agents/email_reader.py` (system prompt)

### Step 5.1: Update Memory Writer system prompt

- [ ] **Modify `agents/memory_writer.py`**

Find the MEMORY TYPE GUIDELINES section. Add this block at the end of the section (before the PRIORITY LEVELS section):

```
UNIVERSAL STATUS FIELDS:
All memory types now support three status fields that track lifecycle transitions:
- status: Current lifecycle state (default: "active")
- status_reason: Human-readable explanation of the current status
- status_updated: Date of last status change (auto-filled to today)

Status VALUES by type:
- people: active | inactive | left-org | unavailable
- decisions: active | reversed | superseded | on-hold
- commitments: active | completed | cancelled (in addition to commitment_status)
- action_required: active | closed | expired | dismissed

WHEN TO SET NON-DEFAULT STATUS:
- If an email explicitly says a person left their company → status="left-org"
- If a decision was reversed or replaced by a newer one → status="reversed"
- If a commitment was completed or cancelled → set status accordingly
- Always include a status_reason explaining the transition
- Otherwise, omit status to let it default to "active"
```

Also add `status`, `status_reason` properties to the write_memory tool's input_schema properties. Check if they already exist (they're already defined for action_required). If they are there as generic properties (not action_required-specific), no change needed. If they're described as action_required-only, broaden the descriptions.

### Step 5.2: Update Email Reader system prompt

- [ ] **Modify `agents/email_reader.py`**

In the system prompt, find the observation format section. After the existing `person_data` block, add a note:

```
STATUS SIGNALS:
When analyzing emails, watch for lifecycle events that should update an entity's status:
- Person left company: include in observation content, suggest status="left-org"
- Decision reversed: note the reversal, suggest status="reversed" on the original decision
- Commitment completed/cancelled: note it in the commitment observation

The Memory Writer will use these hints to set status fields.
```

### Step 5.3: Run existing tests to verify no regressions

- [ ] **Run tests**

Run: `python -m pytest tests/ -v --tb=line`
Expected: No new failures (pre-existing test_dedup failure is OK)

- [ ] **Commit**

```bash
git add agents/memory_writer.py agents/email_reader.py
git commit -m "feat: teach agents to use universal status fields"
```

---

# PRIORITY 5: CONFIDENCE + QUERY OPTIMIZATION

## Task 6: Universal Confidence Field

**Files:**
- Modify: `memory/vault.py` (confidence param + frontmatter on all types)
- Create: `tests/test_universal_confidence.py`

### Step 6.1: Write failing tests

- [ ] **Write tests**

```python
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
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_universal_confidence.py -v`
Expected: FAIL — confidence not in people/decisions/organizations/projects frontmatter

### Step 6.2: Add confidence to all frontmatter branches

- [ ] **Modify `memory/vault.py`**

The `confidence` parameter already exists on `write_memory` (used by insights). No signature change needed.

Add `'confidence': confidence or 'medium',` to EVERY frontmatter dict that doesn't already have it:

1. **People branch** — add after `'priority': priority,`:
   ```python
            'confidence': confidence or 'medium',
   ```

2. **Action Required branch** — add after `'quadrant': quadrant or 'important-not-urgent',`:
   ```python
            'confidence': confidence or 'medium',
   ```

3. **Commitments branch** — add after `'priority': priority,`:
   ```python
            'confidence': confidence or 'medium',
   ```

4. **Organizations branch** — add after `'priority': priority,`:
   ```python
            'confidence': confidence or 'medium',
   ```

5. **Projects branch** — add after `'priority': priority,`:
   ```python
            'confidence': confidence or 'medium',
   ```

6. **Standard/decisions branch** (the `else:` block) — add after `'priority': priority,`:
   ```python
            'confidence': confidence or 'medium',
   ```

**Insights branch — DO NOT change.** Insights already has `'confidence': confidence or 'medium',` — leave it alone to avoid duplicating.

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_universal_confidence.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_universal_confidence.py
git commit -m "feat: add universal confidence field to all memory types"
```

---

## Task 7: Confidence in Knowledge Index

**Files:**
- Modify: `memory/knowledge_index.py` (add confidence column)
- Modify: `tests/test_knowledge_index.py`

### Step 7.1: Write failing test

- [ ] **Add to `tests/test_knowledge_index.py`**

```python
class TestBuildKnowledgeIndexConfidence:
    def test_people_index_shows_confidence(self, tmp_path, monkeypatch):
        """People table should include a confidence column."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice',
            'date': '2026-04-12',
            'category': 'people',
            'confidence': 'high',
        })
        index = build_knowledge_index()
        assert 'high' in index
        # Verify the header includes Confidence column
        assert '| File | Name | Email | Organization | Role | Confidence |' in index
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_index.py::TestBuildKnowledgeIndexConfidence -v`
Expected: FAIL — no Confidence column

### Step 7.2: Add confidence column to Knowledge Index

- [ ] **Modify `memory/knowledge_index.py`**

Update `_build_people_rows()` to include confidence:

```python
def _build_people_rows() -> list[str]:
    """Build table rows for people files."""
    rows = []
    people_dir = VAULT_ROOT / 'people'
    if not people_dir.exists():
        return rows
    for md_file in sorted(people_dir.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        name = _safe(fm.get('name', md_file.stem))
        email = _safe(fm.get('email', ''))
        org = _safe(fm.get('organization', ''))
        role = _safe(fm.get('role', ''))
        conf = _safe(fm.get('confidence', ''))
        rows.append(f"| {rel_path} | {name} | {email} | {org} | {role} | {conf} |")
    return rows
```

Update the People section in `build_knowledge_index()`:

```python
    # People
    people_rows = _build_people_rows()
    sections.append("## People")
    sections.append("| File | Name | Email | Organization | Role | Confidence |")
    sections.append("|------|------|-------|--------------|------|------------|")
    if people_rows:
        sections.extend(people_rows)
    else:
        sections.append("| (none) | | | | | |")
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_knowledge_index.py -v`
Expected: ALL PASS (existing tests may need the new column count — update empty section assertion if needed)

- [ ] **Commit**

```bash
git add memory/knowledge_index.py tests/test_knowledge_index.py
git commit -m "feat: add confidence column to Knowledge Index people table"
```

---

## Task 8: Update Email Reader + Memory Writer to Emit Confidence

**Files:**
- Modify: `agents/email_reader.py` (system prompt)
- Modify: `agents/memory_writer.py` (system prompt + tool schema)

### Step 8.1: Update Email Reader prompt

- [ ] **Modify `agents/email_reader.py`**

In the system prompt, after the existing output format section, add:

```
CONFIDENCE SCORING (required for every observation):
Add a "confidence" field to every observation with one of:
- "high": Multiple corroborating emails (2+), explicit statement, recent (< 30 days)
- "medium": Single source but clear/unambiguous, OR inferred from reliable context, OR somewhat recent (< 90 days)
- "low": Single indirect mention, weakly inferred, stale (> 90 days), or contradictory evidence

Example observation with confidence:
{
    "type": "people",
    "title": "Alice Park — Designer",
    "content": "Lead designer at Acme.",
    "confidence": "high",
    "evidence_emails": ["Re: design review"],
    ...
}

GUIDELINES:
- Default to "medium" if uncertain
- Use "high" only when multiple emails corroborate the fact
- Use "low" when you're inferring rather than reading an explicit statement
- Confidence applies to the OVERALL observation, not individual fields
```

### Step 8.2: Update Memory Writer to pass confidence

- [ ] **Modify `agents/memory_writer.py`**

**a)** In the system prompt, after the MEMORY TYPE GUIDELINES section (or before PRIORITY LEVELS), add:

```
CONFIDENCE FIELD (required):
Every memory must include a confidence field (high | medium | low):
- Pass the confidence score from the Email Reader observation directly to write_memory
- If the observation lacks a confidence field, default to "medium"
- When merging new data into an existing memory, keep the HIGHER confidence value
  (unless the new data contradicts the old — then lower to "low")
```

**b)** In the write_memory tool schema, check if `confidence` is already in the properties. If it's only described as insight-specific, broaden it:

```python
"confidence": {
    "type": "string",
    "enum": ["high", "medium", "low"],
    "description": "Confidence score for this memory. Pass through from Email Reader observation."
},
```

Note: check if the existing schema has `enum: ["high", "medium"]` (insight-only). If so, update to include `"low"`.

### Step 8.3: Run existing tests to verify no regressions

- [ ] **Run tests**

Run: `python -m pytest tests/ --tb=line`
Expected: No new failures

- [ ] **Commit**

```bash
git add agents/email_reader.py agents/memory_writer.py
git commit -m "feat: teach agents to emit and propagate confidence scores"
```

---

## Task 9: QueryAgent Context Optimization

**Files:**
- Modify: `agents/query_agent.py` (inject Knowledge Index, update prompt)
- Modify: `orchestrator.py` (pass Knowledge Index to QueryAgent.run)
- Create: `tests/test_query_optimization.py`

### Step 9.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_query_optimization.py
"""Tests for QueryAgent context window optimization."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_query_optimization.py -v`
Expected: FAIL — `ask_with_index` method doesn't exist, prompt doesn't mention Knowledge Index

### Step 9.2: Add ask_with_index method + update system prompt

- [ ] **Modify `agents/query_agent.py`**

**a)** Update the system prompt to mention the index-first strategy. Find the existing system prompt text and add this block near the top:

```
CONTEXT OPTIMIZATION (IMPORTANT):
You will receive a "Knowledge Index" — a compact table of all vault entities
with their key metadata (name, email, org, role, status, confidence, etc).

STRATEGY:
1. For questions answerable from the index alone (e.g., "who works at Acme?",
   "what's Alice's email?"), answer directly from the index without reading files
2. For questions needing full context (e.g., "summarize my relationship with Alice"),
   use search_vault or read_memory to load specific files
3. Always prefer list_memories (metadata only) over read_memory (full content)
   unless full body content is genuinely needed

This saves tokens and speeds up responses.
```

**b)** Add the `ask_with_index` method to the QueryAgent class. Put it after the existing `execute_tool` method:

```python
    def ask_with_index(self, question: str) -> str:
        """
        Answer a query with the Knowledge Index injected into the prompt.

        Builds a compact entity catalog and includes it before the user's
        question, so the agent can answer metadata-level questions without
        reading full files.
        """
        from memory.knowledge_index import build_knowledge_index

        knowledge_index = build_knowledge_index()

        prompt = (
            f"Before answering, review this Knowledge Index showing all vault "
            f"entities. For simple metadata questions, answer directly from the "
            f"index. For deeper questions, use search_vault and read_memory.\n\n"
            f"{knowledge_index}\n\n"
            f"---\n\n"
            f"USER QUESTION: {question}"
        )

        return self.run(prompt)
```

### Step 9.3: Update orchestrator to use ask_with_index

- [ ] **Modify `orchestrator.py`**

In the `query_memory()` method, replace the `return self.query_agent.run(user_input)` call with:

```python
        return self.query_agent.ask_with_index(user_input)
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_query_optimization.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add agents/query_agent.py orchestrator.py tests/test_query_optimization.py
git commit -m "feat: inject Knowledge Index into QueryAgent for context optimization"
```

---

## Task 10: Final Verification + Documentation

### Step 10.1: Run the full test suite

- [ ] **Run all new and existing tests**

Run: `python -m pytest tests/test_git_history.py tests/test_universal_status.py tests/test_universal_confidence.py tests/test_query_optimization.py -v`
Expected: ALL PASS

- [ ] **Run the full suite for regressions**

Run: `python -m pytest tests/ -v --tb=line`
Expected: No new failures (pre-existing test_dedup failure unchanged)

### Step 10.2: Verify imports

- [ ] **Smoke test**

Run:
```bash
python -c "
from memory.git_history import init_vault_repo, commit_vault_changes, is_vault_repo, get_vault_log
from agents.query_agent import QueryAgent
agent = QueryAgent()
assert hasattr(agent, 'ask_with_index')
print('All new features importable — OK')
"
```
Expected: `All new features importable — OK`

### Step 10.3: Update documentation

- [ ] **Invoke `/documenter` skill** to update roadmap, architecture-overview, data-model, agentic-architecture

The documenter should cover:
- Add to Phase 3 roadmap: git history (3.27), universal status fields (3.28), universal confidence (3.29), QueryAgent optimization (3.30) — all marked complete
- Add `memory/git_history.py` to components table in architecture-overview
- Update data-model.md schemas for all types to show new status/confidence fields
- Update agentic-architecture.md to note QueryAgent's Knowledge Index usage

### Step 10.4: Final check

- [ ] **Verify no uncommitted changes**

Run: `git status`
Expected: `nothing to commit, working tree clean`
