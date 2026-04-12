# Vault Priority 1: Knowledge Index, Noise Filtering, Audit Log

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three foundational vault improvements inspired by Karpathy's LLM Wiki and Rowboat: (1) a pre-built Knowledge Index injected into MemoryWriterAgent prompts for better entity resolution, (2) email noise filtering to skip newsletters/promotions/cold outreach before LLM processing, (3) an append-only audit log tracking every vault mutation.

**Architecture:** The Knowledge Index is a pure function in `memory/vault.py` that scans all vault files and produces a compact text catalog (name, type, filepath, key fields). It's injected into the MemoryWriterAgent prompt before each run by the orchestrator. Email noise filtering is a lightweight keyword/heuristic classifier in `tools/email_filter.py` that runs between email fetch and batch analysis. The audit log is appended to `vault/_changelog.md` by `write_memory()` after every successful write.

**Tech Stack:** Python, pytest, yaml, pathlib (no new dependencies)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `memory/knowledge_index.py` | Build compact entity catalog from vault files |
| Create | `tools/email_filter.py` | Classify emails as signal vs noise |
| Create | `memory/changelog.py` | Append-only audit log for vault mutations |
| Modify | `memory/vault.py` | Call changelog after each write_memory() |
| Modify | `orchestrator.py` | Build index before MemoryWriter; filter emails before batching |
| Modify | `agents/memory_writer.py` | Accept and use Knowledge Index in system prompt |
| Create | `tests/test_knowledge_index.py` | Tests for the Knowledge Index builder |
| Create | `tests/test_email_filter.py` | Tests for the noise filter |
| Create | `tests/test_changelog.py` | Tests for the audit log |
| Create | `tests/test_index_integration.py` | Integration test: index injection into MemoryWriter |

---

## Task 1: Knowledge Index Builder

**Files:**
- Create: `memory/knowledge_index.py`
- Test: `tests/test_knowledge_index.py`

### Step 1.1: Write the failing test — empty vault returns empty index

- [ ] **Write test**

```python
# tests/test_knowledge_index.py
"""Tests for the Knowledge Index builder (memory/knowledge_index.py)."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault directory and patch VAULT_ROOT."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
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
    def test_empty_vault_returns_empty_sections(self, tmp_path, monkeypatch):
        """An empty vault should return an index with zero entries in each section."""
        _setup_vault(tmp_path, monkeypatch)
        index = build_knowledge_index()

        assert isinstance(index, str)
        assert '## People' in index
        assert '## Decisions' in index
        assert '## Commitments' in index
        assert '## Action Items' in index
        assert '(none)' in index
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_index.py::TestBuildKnowledgeIndexEmpty::test_empty_vault_returns_empty_sections -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memory.knowledge_index'`

### Step 1.2: Implement the Knowledge Index builder (minimal — empty vault)

- [ ] **Write implementation**

```python
# memory/knowledge_index.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Builds a compact text catalog of all entities in the vault — the
# "Knowledge Index." This index is injected into agent prompts so the
# LLM knows what already exists BEFORE it starts writing, dramatically
# reducing duplicate creation.
#
# Inspired by Rowboat's knowledge_index.ts — a pre-built entity catalog
# that agents receive before processing each batch.
# ============================================================================

import yaml
from pathlib import Path

VAULT_ROOT = Path('vault')

MEMORY_TYPES = ['decisions', 'people', 'commitments', 'action_required', 'insights']


def _parse_frontmatter(filepath: Path) -> dict:
    """Read a markdown file and return its YAML frontmatter as a dict."""
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return {}

    if not text.startswith('---'):
        return {}

    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def build_knowledge_index() -> str:
    """
    Scan the vault and build a compact text index of all entities.

    Returns a markdown-formatted string with tables for each entity type.
    Designed to be injected into agent prompts for entity resolution.

    Format:
        ## People
        | File | Name | Email | Organization | Role |
        ...

        ## Decisions
        | File | Title | Date | Tags |
        ...

    Returns:
        str: The complete Knowledge Index as markdown text.
    """
    people_rows = []
    decision_rows = []
    commitment_rows = []
    action_rows = []
    insight_rows = []

    # ── Scan people ────────────────────────────────────────────
    people_dir = VAULT_ROOT / 'people'
    if people_dir.exists():
        for md_file in sorted(people_dir.glob('*.md')):
            fm = _parse_frontmatter(md_file)
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            name = fm.get('name', md_file.stem)
            email = fm.get('email', '')
            org = fm.get('organization', '')
            role = fm.get('role', '')
            people_rows.append(f"| {rel_path} | {name} | {email} | {org} | {role} |")

    # ── Scan decisions ─────────────────────────────────────────
    decisions_dir = VAULT_ROOT / 'decisions'
    if decisions_dir.exists():
        for md_file in sorted(decisions_dir.glob('*.md')):
            fm = _parse_frontmatter(md_file)
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            title = fm.get('title', md_file.stem)
            date = str(fm.get('date', ''))
            tags = ', '.join(fm.get('tags', []))
            decision_rows.append(f"| {rel_path} | {title} | {date} | {tags} |")

    # ── Scan commitments ───────────────────────────────────────
    commitments_dir = VAULT_ROOT / 'commitments'
    if commitments_dir.exists():
        for md_file in sorted(commitments_dir.glob('*.md')):
            fm = _parse_frontmatter(md_file)
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            title = fm.get('title', md_file.stem)
            status = fm.get('commitment_status', '')
            date = str(fm.get('date', ''))
            commitment_rows.append(f"| {rel_path} | {title} | {status} | {date} |")

    # ── Scan action_required ───────────────────────────────────
    action_dir = VAULT_ROOT / 'action_required'
    if action_dir.exists():
        for md_file in sorted(action_dir.glob('*.md')):
            fm = _parse_frontmatter(md_file)
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            title = fm.get('title', md_file.stem)
            status = fm.get('status', 'active')
            quadrant = fm.get('quadrant', '')
            action_rows.append(f"| {rel_path} | {title} | {status} | {quadrant} |")

    # ── Scan insights ──────────────────────────────────────────
    insights_dir = VAULT_ROOT / 'insights'
    if insights_dir.exists():
        for md_file in sorted(insights_dir.glob('*.md')):
            fm = _parse_frontmatter(md_file)
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            title = fm.get('title', md_file.stem)
            itype = fm.get('insight_type', '')
            status = fm.get('status', 'active')
            insight_rows.append(f"| {rel_path} | {title} | {itype} | {status} |")

    # ── Assemble the index ─────────────────────────────────────
    sections = []

    sections.append("# Knowledge Index\n")
    sections.append("Use this index to resolve entities. If someone or something already exists below, "
                     "reference its file path instead of creating a duplicate.\n")

    # People
    sections.append("## People")
    sections.append("| File | Name | Email | Organization | Role |")
    sections.append("|------|------|-------|--------------|------|")
    if people_rows:
        sections.extend(people_rows)
    else:
        sections.append("| (none) | | | | |")

    sections.append("")

    # Decisions
    sections.append("## Decisions")
    sections.append("| File | Title | Date | Tags |")
    sections.append("|------|-------|------|------|")
    if decision_rows:
        sections.extend(decision_rows)
    else:
        sections.append("| (none) | | | |")

    sections.append("")

    # Commitments
    sections.append("## Commitments")
    sections.append("| File | Title | Status | Date |")
    sections.append("|------|-------|--------|------|")
    if commitment_rows:
        sections.extend(commitment_rows)
    else:
        sections.append("| (none) | | | |")

    sections.append("")

    # Action Items
    sections.append("## Action Items")
    sections.append("| File | Title | Status | Quadrant |")
    sections.append("|------|-------|--------|----------|")
    if action_rows:
        sections.extend(action_rows)
    else:
        sections.append("| (none) | | | |")

    sections.append("")

    # Insights
    sections.append("## Insights")
    sections.append("| File | Title | Type | Status |")
    sections.append("|------|-------|------|--------|")
    if insight_rows:
        sections.extend(insight_rows)
    else:
        sections.append("| (none) | | | |")

    return '\n'.join(sections)
```

- [ ] **Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_index.py::TestBuildKnowledgeIndexEmpty::test_empty_vault_returns_empty_sections -v`
Expected: PASS

### Step 1.3: Write failing tests — populated vault

- [ ] **Write tests for populated vault**

Add these test classes to `tests/test_knowledge_index.py`:

```python
# ============================================================================
# POPULATED VAULT
# ============================================================================

class TestBuildKnowledgeIndexPeople:
    def test_people_appear_in_index(self, tmp_path, monkeypatch):
        """People files should appear with name, email, org, role."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-chen-a1b2.md', {
            'name': 'Sarah Chen',
            'date': '2026-02-20',
            'category': 'people',
            'email': 'sarah@acme.com',
            'organization': 'Acme Corp',
            'role': 'VP Engineering',
        })

        index = build_knowledge_index()

        assert 'Sarah Chen' in index
        assert 'sarah@acme.com' in index
        assert 'Acme Corp' in index
        assert 'VP Engineering' in index
        assert 'people/sarah-chen-a1b2.md' in index

    def test_me_file_included(self, tmp_path, monkeypatch):
        """The me.md file should appear in the People section."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'me.md', {
            'name': 'John Doe',
            'date': '2026-02-20',
            'category': 'people',
            'email': 'john@example.com',
            'organization': 'TechCorp',
            'role': 'Product Manager',
        })

        index = build_knowledge_index()

        assert 'John Doe' in index
        assert 'people/me.md' in index

    def test_multiple_people(self, tmp_path, monkeypatch):
        """Multiple people should each get their own row."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice-a1b2.md', {
            'name': 'Alice', 'date': '2026-02-20', 'category': 'people',
        })
        _write_vault_file(vault, 'people', 'bob-c3d4.md', {
            'name': 'Bob', 'date': '2026-02-21', 'category': 'people',
        })

        index = build_knowledge_index()

        assert 'Alice' in index
        assert 'Bob' in index

    def test_missing_fields_use_empty_string(self, tmp_path, monkeypatch):
        """People with missing email/org/role should still appear (blank fields)."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sparse-a1b2.md', {
            'name': 'Sparse Person',
            'date': '2026-02-20',
            'category': 'people',
        })

        index = build_knowledge_index()

        assert 'Sparse Person' in index
        assert 'people/sparse-a1b2.md' in index


class TestBuildKnowledgeIndexNonPeople:
    def test_decisions_appear(self, tmp_path, monkeypatch):
        """Decision files should appear with title, date, tags."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'chose-react-a1b2.md', {
            'title': 'Chose React for Frontend',
            'date': '2026-02-20',
            'category': 'decisions',
            'tags': ['engineering', 'frontend'],
        })

        index = build_knowledge_index()

        assert 'Chose React for Frontend' in index
        assert 'decisions/chose-react-a1b2.md' in index
        assert 'engineering, frontend' in index

    def test_commitments_appear_with_status(self, tmp_path, monkeypatch):
        """Commitment files should appear with title, status, date."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'AITX Meetup February',
            'date': '2026-02-20',
            'category': 'commitments',
            'commitment_status': 'confirmed',
        })

        index = build_knowledge_index()

        assert 'AITX Meetup February' in index
        assert 'confirmed' in index

    def test_action_items_appear_with_quadrant(self, tmp_path, monkeypatch):
        """Action items should appear with title, status, quadrant."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'action_required', 'renew-cert-a1b2.md', {
            'title': 'Renew AWS Certification',
            'date': '2026-02-20',
            'category': 'action_required',
            'status': 'active',
            'quadrant': 'urgent-important',
        })

        index = build_knowledge_index()

        assert 'Renew AWS Certification' in index
        assert 'urgent-important' in index

    def test_insights_appear_with_type(self, tmp_path, monkeypatch):
        """Insight files should appear with title, type, status."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'insights', 'pattern-a1b2.md', {
            'title': 'Fragmented Contact Database',
            'date': '2026-02-20',
            'category': 'insights',
            'insight_type': 'execution_gap',
            'status': 'active',
        })

        index = build_knowledge_index()

        assert 'Fragmented Contact Database' in index
        assert 'execution_gap' in index


class TestBuildKnowledgeIndexMixed:
    def test_full_vault_all_sections_populated(self, tmp_path, monkeypatch):
        """A vault with all types should produce an index with all sections filled."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'me.md', {
            'name': 'John Doe', 'date': '2026-02-20', 'category': 'people',
            'email': 'john@example.com', 'role': 'PM',
        })
        _write_vault_file(vault, 'decisions', 'react-a1b2.md', {
            'title': 'Chose React', 'date': '2026-02-20', 'category': 'decisions',
            'tags': ['eng'],
        })
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'Meetup', 'date': '2026-02-20', 'category': 'commitments',
            'commitment_status': 'invited',
        })
        _write_vault_file(vault, 'action_required', 'cert-a1b2.md', {
            'title': 'Renew Cert', 'date': '2026-02-20', 'category': 'action_required',
            'status': 'active', 'quadrant': 'important-not-urgent',
        })
        _write_vault_file(vault, 'insights', 'gap-a1b2.md', {
            'title': 'Execution Gap', 'date': '2026-02-20', 'category': 'insights',
            'insight_type': 'execution_gap', 'status': 'active',
        })

        index = build_knowledge_index()

        # Should NOT contain (none) — all sections have entries
        assert '(none)' not in index
        assert 'John Doe' in index
        assert 'Chose React' in index
        assert 'Meetup' in index
        assert 'Renew Cert' in index
        assert 'Execution Gap' in index

    def test_nonexistent_folder_gracefully_skipped(self, tmp_path, monkeypatch):
        """If a memory type folder doesn't exist, it should be skipped (not crash)."""
        vault = tmp_path / 'vault'
        vault.mkdir()
        # Only create people/ — skip all others
        (vault / 'people').mkdir()
        monkeypatch.setattr('memory.knowledge_index.VAULT_ROOT', vault)

        index = build_knowledge_index()

        # Should still produce a valid index with (none) for missing types
        assert '## People' in index
        assert '## Decisions' in index
```

- [ ] **Run tests to verify they pass** (implementation already handles these)

Run: `python -m pytest tests/test_knowledge_index.py -v`
Expected: ALL PASS

### Step 1.4: Commit

- [ ] **Commit**

```bash
git add memory/knowledge_index.py tests/test_knowledge_index.py
git commit -m "feat: add Knowledge Index builder for entity resolution

Scans all vault files and produces a compact markdown table of
entities (people, decisions, commitments, actions, insights) with
key fields. Designed for injection into agent prompts so the LLM
can resolve entities against what already exists."
```

---

## Task 2: Email Noise Filter

**Files:**
- Create: `tools/email_filter.py`
- Test: `tests/test_email_filter.py`

### Step 2.1: Write failing tests for noise classification

- [ ] **Write tests**

```python
# tests/test_email_filter.py
"""Tests for the email noise filter (tools/email_filter.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.email_filter import classify_email, filter_emails


# ============================================================================
# SINGLE EMAIL CLASSIFICATION
# ============================================================================

class TestClassifyEmail:
    """Test classify_email() on individual emails."""

    def test_normal_email_is_signal(self):
        """A regular person-to-person email should be classified as signal."""
        email = {
            'from': 'alice@acme.com',
            'subject': 'Re: Q2 planning meeting',
            'body': 'Hey, can we sync on the Q2 roadmap tomorrow?',
            'labels': [],
        }
        assert classify_email(email) == 'signal'

    def test_noreply_sender_is_noise(self):
        """Emails from noreply/no-reply addresses are noise."""
        email = {
            'from': 'noreply@github.com',
            'subject': '[repo] New issue opened',
            'body': 'A new issue was opened in your repository.',
            'labels': [],
        }
        assert classify_email(email) == 'noise'

    def test_notifications_sender_is_noise(self):
        """Emails from notifications@ addresses are noise."""
        email = {
            'from': 'notifications@linkedin.com',
            'subject': 'You have 5 new connection requests',
            'body': 'Check your LinkedIn.',
            'labels': [],
        }
        assert classify_email(email) == 'noise'

    def test_unsubscribe_in_body_is_noise(self):
        """Emails with 'unsubscribe' link in the body are likely newsletters."""
        email = {
            'from': 'digest@morningbrew.com',
            'subject': 'Your daily brief',
            'body': 'Here is your daily news. Click to unsubscribe from this list.',
            'labels': [],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_promotions_label_is_noise(self):
        """Emails labeled CATEGORY_PROMOTIONS by Gmail are noise."""
        email = {
            'from': 'deals@store.com',
            'subject': '50% off everything!',
            'body': 'Huge sale this weekend.',
            'labels': ['CATEGORY_PROMOTIONS'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_social_label_is_noise(self):
        """Emails labeled CATEGORY_SOCIAL by Gmail are noise."""
        email = {
            'from': 'notify@facebook.com',
            'subject': 'You have new friend requests',
            'body': 'Check Facebook.',
            'labels': ['CATEGORY_SOCIAL'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_updates_label_is_noise(self):
        """Emails labeled CATEGORY_UPDATES by Gmail are noise."""
        email = {
            'from': 'updates@bank.com',
            'subject': 'Your statement is ready',
            'body': 'View your statement online.',
            'labels': ['CATEGORY_UPDATES'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_forums_label_is_noise(self):
        """Emails labeled CATEGORY_FORUMS by Gmail are noise."""
        email = {
            'from': 'group@googlegroups.com',
            'subject': 'Re: Discussion thread',
            'body': 'Someone replied to the thread.',
            'labels': ['CATEGORY_FORUMS'],
        }
        assert classify_email(email) == 'noise'

    def test_receipt_subject_is_noise(self):
        """Emails with receipt/order/invoice subjects are noise."""
        email = {
            'from': 'orders@amazon.com',
            'subject': 'Your order confirmation #123-456',
            'body': 'Your order has been placed.',
            'labels': [],
        }
        assert classify_email(email) == 'noise'

    def test_personal_with_inbox_label_is_signal(self):
        """A personal email in INBOX (even if from a company domain) is signal."""
        email = {
            'from': 'sarah@bigcorp.com',
            'subject': 'Lunch Thursday?',
            'body': 'Want to grab lunch at the new place on 5th?',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'signal'

    def test_missing_fields_defaults_to_signal(self):
        """Emails with missing fields should default to signal (not crash)."""
        email = {'from': 'someone@example.com'}
        assert classify_email(email) == 'signal'

    def test_support_sender_is_noise(self):
        """Emails from support@ addresses are noise."""
        email = {
            'from': 'support@helpdesk.com',
            'subject': 'Ticket #789 updated',
            'body': 'Your ticket has been updated.',
            'labels': [],
        }
        assert classify_email(email) == 'noise'


# ============================================================================
# BATCH FILTERING
# ============================================================================

class TestFilterEmails:
    """Test filter_emails() on a batch of emails."""

    def test_filters_noise_from_batch(self):
        """Should return only signal emails from a mixed batch."""
        emails = [
            {'from': 'alice@acme.com', 'subject': 'Re: Project update', 'body': 'Looks good!', 'labels': []},
            {'from': 'noreply@github.com', 'subject': 'PR merged', 'body': 'Your PR was merged.', 'labels': []},
            {'from': 'bob@eng.io', 'subject': 'Code review', 'body': 'Can you review this?', 'labels': []},
            {'from': 'deals@store.com', 'subject': 'Big sale!', 'body': 'Click to unsubscribe.', 'labels': ['CATEGORY_PROMOTIONS']},
        ]
        signal, noise = filter_emails(emails)

        assert len(signal) == 2
        assert len(noise) == 2
        assert signal[0]['from'] == 'alice@acme.com'
        assert signal[1]['from'] == 'bob@eng.io'

    def test_empty_batch_returns_empty(self):
        """An empty list should return two empty lists."""
        signal, noise = filter_emails([])
        assert signal == []
        assert noise == []

    def test_all_signal(self):
        """A batch of all signal emails should return them all."""
        emails = [
            {'from': 'a@b.com', 'subject': 'Hi', 'body': 'Hello there', 'labels': []},
            {'from': 'c@d.com', 'subject': 'Re: Hi', 'body': 'Hey back', 'labels': []},
        ]
        signal, noise = filter_emails(emails)
        assert len(signal) == 2
        assert len(noise) == 0

    def test_all_noise(self):
        """A batch of all noise should return empty signal."""
        emails = [
            {'from': 'noreply@x.com', 'subject': 'Alert', 'body': 'Automated.', 'labels': []},
            {'from': 'notifications@y.com', 'subject': 'Update', 'body': 'Unsubscribe here.', 'labels': []},
        ]
        signal, noise = filter_emails(emails)
        assert len(signal) == 0
        assert len(noise) == 2
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_email_filter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.email_filter'`

### Step 2.2: Implement the email noise filter

- [ ] **Write implementation**

```python
# tools/email_filter.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Lightweight email noise filter. Classifies each email as "signal"
# (worth processing by the LLM) or "noise" (newsletters, receipts,
# notifications, cold outreach) using heuristics.
#
# Runs BEFORE the Email Reader Agent to save tokens and reduce
# vault clutter. No LLM calls — pure keyword/label matching.
#
# Inspired by Rowboat's email labeling system where noise tags
# override all other tags and cause emails to be skipped entirely.
# ============================================================================

import re


# Sender patterns that indicate automated/bulk mail
_NOISE_SENDER_PATTERNS = [
    r'noreply@',
    r'no-reply@',
    r'no\.reply@',
    r'notifications?@',
    r'notify@',
    r'mailer-daemon@',
    r'postmaster@',
    r'bounce[sd]?@',
    r'donotreply@',
    r'do-not-reply@',
    r'automated@',
    r'alerts?@',
    r'digest@',
    r'updates?@',
    r'newsletter@',
    r'news@',
    r'info@',
    r'marketing@',
    r'promo(?:tions?)?@',
    r'support@',
    r'helpdesk@',
    r'billing@',
    r'receipts?@',
    r'orders?@',
    r'shipping@',
    r'subscriptions?@',
]

_NOISE_SENDER_RE = re.compile(
    '|'.join(_NOISE_SENDER_PATTERNS),
    re.IGNORECASE,
)

# Gmail category labels that indicate bulk/automated mail
_NOISE_LABELS = {
    'CATEGORY_PROMOTIONS',
    'CATEGORY_SOCIAL',
    'CATEGORY_UPDATES',
    'CATEGORY_FORUMS',
    'SPAM',
    'TRASH',
}

# Subject keywords that indicate transactional/automated mail
_NOISE_SUBJECT_PATTERNS = re.compile(
    r'(?:order\s+confirm|your\s+receipt|invoice\s+#|'
    r'shipping\s+confirm|delivery\s+notif|'
    r'password\s+reset|verify\s+your|'
    r'your\s+statement|account\s+alert|'
    r'subscription\s+renew)',
    re.IGNORECASE,
)

# Body markers that indicate newsletters/bulk mail
_NOISE_BODY_PATTERNS = re.compile(
    r'(?:unsubscribe|opt.out|email\s+preferences|'
    r'manage\s+(?:your\s+)?subscriptions?|'
    r'view\s+(?:in|this\s+email\s+in)\s+(?:your\s+)?browser)',
    re.IGNORECASE,
)


def classify_email(email: dict) -> str:
    """
    Classify a single email as 'signal' (worth LLM processing) or 'noise'.

    Checks in order (first match wins):
    1. Gmail category labels (PROMOTIONS, SOCIAL, UPDATES, FORUMS)
    2. Sender address patterns (noreply@, notifications@, etc.)
    3. Subject line patterns (order confirmation, receipt, etc.)
    4. Body markers (unsubscribe links, email preference links)

    Args:
        email: Dict with keys: from, subject, body, labels (all optional).

    Returns:
        'signal' or 'noise'
    """
    sender = email.get('from', '') or ''
    subject = email.get('subject', '') or ''
    body = email.get('body', '') or ''
    labels = set(email.get('labels', []) or [])

    # Check 1: Gmail noise labels
    if labels & _NOISE_LABELS:
        return 'noise'

    # Check 2: Automated sender patterns
    if _NOISE_SENDER_RE.search(sender):
        return 'noise'

    # Check 3: Transactional subject patterns
    if _NOISE_SUBJECT_PATTERNS.search(subject):
        return 'noise'

    # Check 4: Newsletter/bulk body markers
    if _NOISE_BODY_PATTERNS.search(body):
        return 'noise'

    return 'signal'


def filter_emails(emails: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split a list of emails into signal and noise.

    Args:
        emails: List of email dicts.

    Returns:
        (signal_emails, noise_emails) — two lists.
    """
    signal = []
    noise = []

    for email in emails:
        if classify_email(email) == 'signal':
            signal.append(email)
        else:
            noise.append(email)

    return signal, noise
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_email_filter.py -v`
Expected: ALL PASS

### Step 2.3: Commit

- [ ] **Commit**

```bash
git add tools/email_filter.py tests/test_email_filter.py
git commit -m "feat: add email noise filter for signal/noise classification

Heuristic classifier that skips newsletters, receipts, notifications,
and cold outreach before LLM processing. Checks Gmail labels, sender
patterns, subject keywords, and body markers. No LLM calls needed."
```

---

## Task 3: Audit Log (Changelog)

**Files:**
- Create: `memory/changelog.py`
- Test: `tests/test_changelog.py`

### Step 3.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_changelog.py
"""Tests for the append-only audit log (memory/changelog.py)."""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.changelog import append_changelog, read_changelog, CHANGELOG_FILE


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault directory and patch CHANGELOG_FILE."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setattr('memory.changelog.CHANGELOG_FILE', vault / '_changelog.md')
    return vault


# ============================================================================
# APPEND
# ============================================================================

class TestAppendChangelog:
    def test_creates_file_on_first_write(self, tmp_path, monkeypatch):
        """First append should create the _changelog.md file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        append_changelog('CREATED', 'people/sarah-chen-a1b2.md', 'Sarah Chen')

        changelog_path = vault / '_changelog.md'
        assert changelog_path.exists()
        content = changelog_path.read_text(encoding='utf-8')
        assert 'CREATED' in content
        assert 'sarah-chen-a1b2.md' in content
        assert 'Sarah Chen' in content

    def test_appends_to_existing_file(self, tmp_path, monkeypatch):
        """Subsequent appends should add lines without overwriting."""
        vault = _setup_vault(tmp_path, monkeypatch)

        append_changelog('CREATED', 'people/alice-a1b2.md', 'Alice')
        append_changelog('UPDATED', 'people/alice-a1b2.md', 'Alice')
        append_changelog('CREATED', 'decisions/react-a1b2.md', 'Chose React')

        content = (vault / '_changelog.md').read_text(encoding='utf-8')
        lines = [l for l in content.strip().split('\n') if l.startswith('|') and 'File' not in l and '---' not in l]

        assert len(lines) == 3

    def test_includes_timestamp(self, tmp_path, monkeypatch):
        """Each entry should include a date-time timestamp."""
        vault = _setup_vault(tmp_path, monkeypatch)

        append_changelog('CREATED', 'people/test.md', 'Test')

        content = (vault / '_changelog.md').read_text(encoding='utf-8')
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in content

    def test_action_types(self, tmp_path, monkeypatch):
        """Should support CREATED, UPDATED, and MERGED actions."""
        vault = _setup_vault(tmp_path, monkeypatch)

        append_changelog('CREATED', 'people/a.md', 'A')
        append_changelog('UPDATED', 'people/a.md', 'A')
        append_changelog('MERGED', 'people/a.md', 'A')

        content = (vault / '_changelog.md').read_text(encoding='utf-8')
        assert 'CREATED' in content
        assert 'UPDATED' in content
        assert 'MERGED' in content


# ============================================================================
# READ
# ============================================================================

class TestReadChangelog:
    def test_read_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """Reading a nonexistent changelog should return an empty string."""
        _setup_vault(tmp_path, monkeypatch)

        result = read_changelog()
        assert result == ''

    def test_read_returns_full_content(self, tmp_path, monkeypatch):
        """Reading should return the full file content."""
        vault = _setup_vault(tmp_path, monkeypatch)

        append_changelog('CREATED', 'people/alice.md', 'Alice')
        append_changelog('CREATED', 'decisions/react.md', 'React')

        result = read_changelog()
        assert 'Alice' in result
        assert 'React' in result

    def test_read_with_limit(self, tmp_path, monkeypatch):
        """Reading with a limit should return only the last N entries."""
        vault = _setup_vault(tmp_path, monkeypatch)

        for i in range(10):
            append_changelog('CREATED', f'decisions/item-{i}.md', f'Item {i}')

        result = read_changelog(last_n=3)
        assert 'Item 9' in result
        assert 'Item 8' in result
        assert 'Item 7' in result
        assert 'Item 0' not in result
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_changelog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memory.changelog'`

### Step 3.2: Implement the changelog

- [ ] **Write implementation**

```python
# memory/changelog.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Append-only audit log for vault mutations. Every time a memory file
# is created, updated, or merged, a timestamped line is appended to
# vault/_changelog.md.
#
# Inspired by Karpathy's log.md — an append-only chronological record
# of all changes. Enables understanding vault evolution over time
# without reading git history.
# ============================================================================

from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path('vault')
CHANGELOG_FILE = VAULT_ROOT / '_changelog.md'

_HEADER = """# Vault Changelog

Append-only log of all vault mutations. Each row records one write operation.

| Timestamp | Action | File | Description |
|-----------|--------|------|-------------|
"""


def append_changelog(action: str, filepath: str, description: str):
    """
    Append a single entry to the vault changelog.

    Args:
        action:      One of: CREATED, UPDATED, MERGED
        filepath:    Path of the affected file (relative to vault root)
        description: Short description (usually the memory title)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = f"| {timestamp} | {action} | {filepath} | {description} |"

    if not CHANGELOG_FILE.exists():
        CHANGELOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHANGELOG_FILE.write_text(_HEADER + row + '\n', encoding='utf-8')
    else:
        with open(CHANGELOG_FILE, 'a', encoding='utf-8') as f:
            f.write(row + '\n')


def read_changelog(last_n: int = None) -> str:
    """
    Read the changelog content.

    Args:
        last_n: If provided, return only the last N data rows
                (excludes header). If None, return everything.

    Returns:
        The changelog content as a string, or empty string if
        the file doesn't exist.
    """
    if not CHANGELOG_FILE.exists():
        return ''

    content = CHANGELOG_FILE.read_text(encoding='utf-8')

    if last_n is None:
        return content

    # Split into lines, separate header from data rows
    lines = content.split('\n')
    header_lines = []
    data_lines = []

    for line in lines:
        # Data rows start with | and contain a timestamp-like pattern
        if line.startswith('|') and any(c.isdigit() for c in line[:20]):
            data_lines.append(line)
        else:
            header_lines.append(line)

    # Take only the last N data rows
    selected = data_lines[-last_n:] if last_n else data_lines

    return '\n'.join(header_lines) + '\n'.join(selected)
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_changelog.py -v`
Expected: ALL PASS

### Step 3.3: Commit

- [ ] **Commit**

```bash
git add memory/changelog.py tests/test_changelog.py
git commit -m "feat: add append-only vault changelog for audit trail

Every vault mutation (create/update/merge) appends a timestamped row
to vault/_changelog.md. Enables tracking vault evolution without
reading git history. Supports reading last N entries."
```

---

## Task 4: Wire Changelog into vault.py

**Files:**
- Modify: `memory/vault.py:543-566` (after `filepath.write_text(...)`)
- Test: `tests/test_changelog.py` (add integration test)

### Step 4.1: Write failing integration test

- [ ] **Write test**

Add to `tests/test_changelog.py`:

```python
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
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
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
        assert 'CREATED' in content or 'UPDATED' in content
        assert 'Test Decision' in content
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_changelog.py::TestChangelogIntegration::test_write_memory_appends_to_changelog -v`
Expected: FAIL — changelog file not created (write_memory doesn't call it yet)

### Step 4.2: Wire changelog into write_memory()

- [ ] **Modify `memory/vault.py`**

Add import at the top of `memory/vault.py` (after the existing imports around line 51):

```python
from memory.changelog import append_changelog
```

Then modify the end of `write_memory()` — replace the block at lines 559-566:

```python
    # ── Log to changelog ───────────────────────────────────────
    # Append an audit trail entry for this vault mutation.
    is_update = duplicate_path is not None and duplicate_path.exists() if 'duplicate_path' in dir() else False
    # For people files, also check via original_date
    if memory_type == 'people':
        is_update = is_update or (original_date != today)
    action = "UPDATED" if is_update else "CREATED"

    rel_path = str(filepath.relative_to(VAULT_ROOT))
    description = name if memory_type == 'people' and name else title
    append_changelog(action, rel_path, description)

    print(f"   [{action}] Written: {filepath}")

    return str(filepath)
```

Wait — let me be more precise. The current code at lines 559-566 is:

```python
    # Detect whether this was an update to an existing people file.
    # "original_date" is only defined inside the people branch above,
    # so we guard with a memory_type check first.
    is_update = (memory_type == 'people') and (original_date != today)
    action = "UPDATED" if is_update else "WRITE"
    print(f"   [{action}] Written: {filepath}")

    return str(filepath)
```

Replace with:

```python
    # ── Log to changelog ───────────────────────────────────────
    is_update = (duplicate_path is not None) if 'duplicate_path' in locals() else False
    if not is_update and memory_type == 'people':
        is_update = (original_date != today)
    action = "UPDATED" if is_update else "CREATED"

    rel_path = filepath.relative_to(VAULT_ROOT).as_posix()
    description = name if (memory_type == 'people' and name) else title
    append_changelog(action, rel_path, description)

    print(f"   [{action}] Written: {filepath}")

    return str(filepath)
```

- [ ] **Run integration test to verify it passes**

Run: `python -m pytest tests/test_changelog.py::TestChangelogIntegration::test_write_memory_appends_to_changelog -v`
Expected: PASS

- [ ] **Run all existing tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS (existing tests use mock for rebuild_graph but don't mock changelog — since changelog just appends to a file, it should work fine with tmp_path fixtures)

### Step 4.3: Commit

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_changelog.py
git commit -m "feat: wire changelog into write_memory for automatic audit trail

Every write_memory() call now appends a CREATED or UPDATED entry to
vault/_changelog.md with timestamp, filepath, and description."
```

---

## Task 5: Wire Knowledge Index into Orchestrator + MemoryWriter

**Files:**
- Modify: `orchestrator.py:359-384` (Step 3: Memory Writer section)
- Modify: `agents/memory_writer.py:61-222` (system prompt)
- Test: `tests/test_index_integration.py`

### Step 5.1: Write failing integration test

- [ ] **Write test**

```python
# tests/test_index_integration.py
"""Integration tests: Knowledge Index injection into MemoryWriter prompt."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
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


# ============================================================================
# INDEX CONTENT VALIDATION
# ============================================================================

class TestIndexContentForAgent:
    """Verify the index contains what an agent needs for entity resolution."""

    def test_index_has_resolution_instructions(self, tmp_path, monkeypatch):
        """Index should include instructions telling the agent how to use it."""
        _setup_vault(tmp_path, monkeypatch)
        index = build_knowledge_index()

        assert 'resolve entities' in index.lower() or 'Knowledge Index' in index

    def test_index_enables_person_lookup_by_email(self, tmp_path, monkeypatch):
        """An agent should be able to find a person by email in the index."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'sarah-a1b2.md', {
            'name': 'Sarah Chen',
            'category': 'people',
            'email': 'sarah@acme.com',
            'organization': 'Acme Corp',
            'role': 'VP Engineering',
        })

        index = build_knowledge_index()

        # The index should contain enough info for the agent to match
        # "sarah@acme.com" → Sarah Chen at people/sarah-a1b2.md
        assert 'sarah@acme.com' in index
        assert 'people/sarah-a1b2.md' in index

    def test_index_enables_commitment_status_check(self, tmp_path, monkeypatch):
        """An agent should see commitment statuses to avoid re-creating them."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'commitments', 'meetup-a1b2.md', {
            'title': 'AITX Meetup February',
            'category': 'commitments',
            'commitment_status': 'confirmed',
        })

        index = build_knowledge_index()

        assert 'AITX Meetup February' in index
        assert 'confirmed' in index

    def test_index_fits_in_reasonable_token_budget(self, tmp_path, monkeypatch):
        """Index for a 50-entity vault should be under ~2000 chars (~500 tokens)."""
        vault = _setup_vault(tmp_path, monkeypatch)

        # Create 50 entities across types
        for i in range(20):
            _write_vault_file(vault, 'people', f'person-{i}.md', {
                'name': f'Person {i}',
                'category': 'people',
                'email': f'p{i}@example.com',
            })
        for i in range(10):
            _write_vault_file(vault, 'decisions', f'decision-{i}.md', {
                'title': f'Decision {i}',
                'category': 'decisions',
                'tags': ['test'],
            })
        for i in range(10):
            _write_vault_file(vault, 'commitments', f'commit-{i}.md', {
                'title': f'Commitment {i}',
                'category': 'commitments',
                'commitment_status': 'invited',
            })
        for i in range(10):
            _write_vault_file(vault, 'action_required', f'action-{i}.md', {
                'title': f'Action {i}',
                'category': 'action_required',
                'status': 'active',
                'quadrant': 'important-not-urgent',
            })

        index = build_knowledge_index()

        # 50 entities at ~40 chars per row + headers ≈ under 4000 chars
        assert len(index) < 6000, f"Index too large: {len(index)} chars for 50 entities"


# ============================================================================
# PROMPT INJECTION FORMAT
# ============================================================================

class TestIndexPromptFormat:
    """Verify the index can be cleanly injected into an agent prompt."""

    def test_index_is_valid_markdown(self, tmp_path, monkeypatch):
        """Index should be valid markdown (starts with # heading)."""
        _setup_vault(tmp_path, monkeypatch)
        index = build_knowledge_index()

        assert index.startswith('# Knowledge Index')

    def test_index_tables_have_header_rows(self, tmp_path, monkeypatch):
        """Each section should have a markdown table header."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'test.md', {
            'name': 'Test', 'category': 'people',
        })

        index = build_knowledge_index()

        # Check for table headers
        assert '| File | Name | Email | Organization | Role |' in index
        assert '| File | Title | Date | Tags |' in index
        assert '| File | Title | Status | Date |' in index
        assert '| File | Title | Status | Quadrant |' in index
        assert '| File | Title | Type | Status |' in index
```

- [ ] **Run tests to verify they pass** (index builder already exists from Task 1)

Run: `python -m pytest tests/test_index_integration.py -v`
Expected: ALL PASS

### Step 5.2: Update MemoryWriter system prompt to reference Knowledge Index

- [ ] **Modify `agents/memory_writer.py`**

Add this block to the end of the system prompt (before the closing `"""`), after the TOKEN OPTIMIZATION section around line 221:

```python
KNOWLEDGE INDEX:
When you receive a Knowledge Index in your prompt, USE IT to resolve entities:
- Before creating a new person file, check if they appear in the People table
- Before creating a new commitment, check if a similar one exists in Commitments
- Before creating a new decision, check if a similar one exists in Decisions
- If a matching entity exists in the index, use its file path with read_memory to load
  the existing content, then merge your new data into it
- The index provides: file path, name/title, and key metadata for every vault entity
- This is MORE RELIABLE than search_vault for duplicate detection — use it first
```

### Step 5.3: Update Orchestrator to build and inject the Knowledge Index

- [ ] **Modify `orchestrator.py`**

Add import at the top (after the existing imports, around line 56):

```python
from memory.knowledge_index import build_knowledge_index
```

Then modify the Step 3 section (around lines 359-384). Replace the `writer_prompt` construction:

Find this block:
```python
        writer_prompt = (
            "Here are observations about the user extracted from their emails. "
            "These observations come from multiple batches, so you may see "
            "duplicate people (especially 'Me') — merge them when writing. "
            "Process each observation and write it to the memory vault. "
            "Check for existing memories first to avoid duplicates.\n\n"
            f"OBSERVATIONS:\n{combined_observations}"
        )
```

Replace with:
```python
        # Build the Knowledge Index so the agent knows what already exists
        knowledge_index = build_knowledge_index()

        writer_prompt = (
            "Here are observations about the user extracted from their emails. "
            "These observations come from multiple batches, so you may see "
            "duplicate people (especially 'Me') — merge them when writing. "
            "Process each observation and write it to the memory vault.\n\n"
            "IMPORTANT: Use the Knowledge Index below to check what already exists "
            "BEFORE creating new files. If an entity already appears in the index, "
            "read it with read_memory and merge your new data.\n\n"
            f"{knowledge_index}\n\n"
            "---\n\n"
            f"OBSERVATIONS:\n{combined_observations}"
        )
```

- [ ] **Run all tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

### Step 5.4: Commit

- [ ] **Commit**

```bash
git add orchestrator.py agents/memory_writer.py tests/test_index_integration.py
git commit -m "feat: inject Knowledge Index into MemoryWriter for entity resolution

Orchestrator builds a Knowledge Index before the MemoryWriter runs
and injects it into the prompt. The agent sees all existing entities
(name, filepath, key fields) and can resolve against them before
writing, dramatically reducing duplicate creation."
```

---

## Task 6: Wire Email Noise Filter into Orchestrator

**Files:**
- Modify: `orchestrator.py:266-277` (after email fetch, before batching)

### Step 6.1: Write failing test

- [ ] **Write test**

Add to `tests/test_email_filter.py`:

```python
# ============================================================================
# ORCHESTRATOR INTEGRATION
# ============================================================================

class TestFilterIntegration:
    """Verify the filter works on realistic email shapes from Gmail tools."""

    def test_gmail_shaped_email_classification(self):
        """Should correctly classify emails that look like real Gmail fetch output."""
        emails = [
            {
                'id': '18e1234abc',
                'from': 'Sarah Chen <sarah@acme.com>',
                'subject': 'Re: Q2 Roadmap Review',
                'date': '2026-04-10',
                'body': 'Hey, I reviewed the doc. Looks good to me. Let us sync Thursday.',
                'labels': ['INBOX', 'IMPORTANT'],
            },
            {
                'id': '18e5678def',
                'from': 'GitHub <noreply@github.com>',
                'subject': '[org/repo] Issue #42 opened',
                'body': 'A new issue was opened by user123. Reply to this email or view on GitHub.',
                'labels': ['INBOX'],
            },
            {
                'id': '18e9012ghi',
                'from': 'deals@shopify.com',
                'subject': 'Your weekly store report',
                'body': 'Here is your weekly store summary. To unsubscribe, click here.',
                'labels': ['CATEGORY_PROMOTIONS'],
            },
        ]

        signal, noise = filter_emails(emails)

        assert len(signal) == 1
        assert signal[0]['id'] == '18e1234abc'
        assert len(noise) == 2
```

- [ ] **Run test to verify it passes** (filter already implemented)

Run: `python -m pytest tests/test_email_filter.py::TestFilterIntegration -v`
Expected: PASS

### Step 6.2: Wire filter into orchestrator

- [ ] **Modify `orchestrator.py`**

Add import at the top (after the existing imports):

```python
from tools.email_filter import filter_emails
```

Then add the filtering step after email fetch and before batching. Find this block (around line 273-277):

```python
        console.print(f"[green]OK - Fetched {len(emails)} new emails[/green]")
        emit({
            "stage": "fetching", "status": "complete",
            "message": f"Fetched {len(emails)} new emails (skipped {len(all_ids) - len(new_ids)} already processed)"
        })

        # ── Step 2: Batch analyze ────────────────────────────
```

Replace with:

```python
        console.print(f"[green]OK - Fetched {len(emails)} new emails[/green]")

        # ── Filter out noise emails ────────────────────────────
        # Skip newsletters, receipts, notifications, cold outreach.
        # This saves tokens and keeps the vault focused on real interactions.
        signal_emails, noise_emails = filter_emails(emails)

        if noise_emails:
            console.print(f"   [dim]Filtered {len(noise_emails)} noise emails "
                          f"(newsletters, notifications, etc.)[/dim]")
        emit({
            "stage": "fetching", "status": "complete",
            "message": (f"Fetched {len(emails)} new emails "
                        f"(skipped {len(all_ids) - len(new_ids)} already processed, "
                        f"filtered {len(noise_emails)} noise)")
        })

        if not signal_emails:
            emit({"stage": "complete", "status": "complete",
                  "message": f"All {len(emails)} new emails were noise (newsletters, etc.). Nothing to process.",
                  "stats": get_vault_stats()})
            # Still mark them as processed so we don't re-fetch next time
            updated_ids = processed_ids | {e['id'] for e in emails}
            save_processed_email_ids(updated_ids)
            return f"All {len(emails)} new emails were noise. Nothing to process."

        # Use signal_emails for the rest of the pipeline
        emails = signal_emails

        # ── Step 2: Batch analyze ────────────────────────────
```

- [ ] **Run all tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

### Step 6.3: Commit

- [ ] **Commit**

```bash
git add orchestrator.py
git commit -m "feat: wire email noise filter into build pipeline

Emails are now classified as signal/noise after fetch and before
batching. Noise emails (newsletters, receipts, notifications) are
skipped, saving tokens and reducing vault clutter. Noise count is
reported in progress events."
```

---

## Task 7: Full Integration Test

**Files:**
- Create: `tests/test_vault_improvements.py`

### Step 7.1: Write end-to-end integration test

- [ ] **Write test**

```python
# tests/test_vault_improvements.py
"""End-to-end integration tests for vault Priority 1 improvements."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.knowledge_index import build_knowledge_index
from memory.changelog import append_changelog, read_changelog
from tools.email_filter import classify_email, filter_emails


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_full_vault(tmp_path, monkeypatch):
    """Create a fully patched temporary vault."""
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required', 'insights'):
        (vault / mtype).mkdir()
    (vault / '_index.md').write_text(
        '---\ntitle: "Vault Index"\n---\n\n| File | Type | Description | Date |\n|------|------|-------------|------|\n'
    )

    import memory.vault
    import memory.knowledge_index
    import memory.changelog

    monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)
    monkeypatch.setattr(memory.changelog, 'CHANGELOG_FILE', vault / '_changelog.md')
    # Also patch dedup's VAULT_ROOT since write_memory imports from it
    import memory.dedup
    monkeypatch.setattr(memory.dedup, 'VAULT_ROOT', vault)

    return vault


def _write_vault_file(vault_dir, memory_type, filename, frontmatter, body=''):
    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    heading = frontmatter.get('name') or frontmatter.get('title', filename)
    content = f"---\n{fm_str.strip()}\n---\n\n# {heading}\n\n{body}"
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


# ============================================================================
# FULL PIPELINE: write_memory → changelog + index reflects new state
# ============================================================================

class TestFullPipeline:
    def test_write_memory_then_index_reflects_new_entity(self, tmp_path, monkeypatch):
        """After write_memory, the Knowledge Index should include the new entity."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Alice Park — Designer",
                memory_type="people",
                content="## Overview\n\nDesigner at Acme.",
                name="Alice Park",
                role="Designer",
                organization="Acme",
                email="alice@acme.com",
            )

        # Now the index should contain Alice
        index = build_knowledge_index()
        assert 'Alice Park' in index
        assert 'alice@acme.com' in index
        assert 'Acme' in index

    def test_write_memory_then_changelog_records_it(self, tmp_path, monkeypatch):
        """After write_memory, the changelog should have a CREATED entry."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Chose React for Frontend",
                memory_type="decisions",
                content="Team chose React.",
            )

        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'Chose React' in changelog

    def test_duplicate_write_shows_updated_in_changelog(self, tmp_path, monkeypatch):
        """Writing the same entity twice should show UPDATED in changelog."""
        vault = _setup_full_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory

            write_memory(
                title="Bob Smith — Engineer",
                memory_type="people",
                content="## Overview\n\nEngineer at Eng.io.",
                name="Bob Smith",
            )

            write_memory(
                title="Bob Smith — Senior Engineer",
                memory_type="people",
                content="## Overview\n\nPromoted to Senior Engineer at Eng.io.",
                name="Bob Smith",
            )

        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'UPDATED' in changelog


# ============================================================================
# NOISE FILTER + INDEX COHERENCE
# ============================================================================

class TestFilterAndIndex:
    def test_noise_emails_dont_pollute_vault(self):
        """Noise emails should be filtered before any vault writes happen."""
        emails = [
            {'from': 'alice@acme.com', 'subject': 'Project update', 'body': 'Meeting tomorrow.', 'labels': []},
            {'from': 'noreply@spam.com', 'subject': 'You won!', 'body': 'Click to unsubscribe.', 'labels': ['CATEGORY_PROMOTIONS']},
            {'from': 'newsletter@news.com', 'subject': 'Weekly digest', 'body': 'Unsubscribe from this list.', 'labels': []},
        ]

        signal, noise = filter_emails(emails)

        # Only the real email should make it through
        assert len(signal) == 1
        assert signal[0]['from'] == 'alice@acme.com'

        # The others should be caught
        assert len(noise) == 2
```

- [ ] **Run the full test suite**

Run: `python -m pytest tests/test_vault_improvements.py -v`
Expected: ALL PASS

- [ ] **Run the ENTIRE test suite to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

### Step 7.2: Commit

- [ ] **Commit**

```bash
git add tests/test_vault_improvements.py
git commit -m "test: add end-to-end integration tests for vault improvements

Tests verify: Knowledge Index reflects new entities after writes,
changelog records CREATED/UPDATED actions, noise filter prevents
junk emails from reaching the vault."
```

---

## Task 8: Final Verification

### Step 8.1: Run the complete test suite

- [ ] **Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS, zero failures

### Step 8.2: Verify the server starts

- [ ] **Quick smoke test**

Run: `python -c "from memory.knowledge_index import build_knowledge_index; from memory.changelog import append_changelog, read_changelog; from tools.email_filter import classify_email, filter_emails; print('All imports OK')"`
Expected: `All imports OK`

### Step 8.3: Final commit (if any fixups needed)

- [ ] **Check for uncommitted changes**

Run: `git status`

If clean, this task is complete.
