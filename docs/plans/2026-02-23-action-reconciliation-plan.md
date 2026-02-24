# Action Required Vault Tab + Status Reconciliation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the action_required tab to the vault browser with status badges/filters, build a ReconciliationAgent that marks action items as Active/Closed/Expired by comparing against sent Gmail messages, and integrate it into the build pipeline.

**Architecture:** A new ReconciliationAgent uses hybrid matching (heuristic subject/recipient overlap first, then LLM for ambiguous items) to reconcile action items against sent emails. Status fields (status, status_reason, status_updated) are added to action_required frontmatter. The vault UI gets a 4th tab with color-coded status badges and filter toggles.

**Tech Stack:** Python (agents, vault, MCP), vanilla JS (frontend), JSDOM (frontend tests), pytest (backend tests)

---

### Task 1: Add status fields to vault write_memory

**Files:**
- Modify: `memory/vault.py:202-224` (write_memory signature)
- Modify: `memory/vault.py:341-374` (action_required frontmatter block)
- Test: `tests/test_vault_preview.py`

**Step 1: Write the failing test**

Add to `tests/test_vault_preview.py` after the existing test classes:

```python
class TestActionRequiredStatusFields:
    """Test that action_required memories support status fields."""

    def test_write_memory_with_status_fields(self):
        """write_memory should include status, status_reason, status_updated in frontmatter."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Reply to Jake about project timeline",
                memory_type="action_required",
                content="Jake asked about Q2 timeline.",
                quadrant="urgent-important",
                status="active",
                status_reason="",
                status_updated="2026-02-23",
            )
            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            assert result is not None
            fm = result['frontmatter']
            assert fm['status'] == 'active'
            assert fm['status_updated'] == '2026-02-23'

    def test_write_memory_status_defaults(self):
        """When no status is provided, default to 'active'."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Follow up on contract",
                memory_type="action_required",
                content="Need to review contract terms.",
                quadrant="important-not-urgent",
            )
            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            fm = result['frontmatter']
            assert fm['status'] == 'active'
            assert fm['status_reason'] == ''

    def test_write_memory_closed_status(self):
        """Should be able to write a memory with closed status."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            filepath = write_memory(
                title="Send report to Sarah",
                memory_type="action_required",
                content="Monthly report due.",
                quadrant="urgent-important",
                status="closed",
                status_reason="Replied to Sarah on 2026-02-22",
                status_updated="2026-02-23",
            )
            rel_path = str(Path(filepath).relative_to(TEST_VAULT))
            result = read_memory(rel_path)

            fm = result['frontmatter']
            assert fm['status'] == 'closed'
            assert 'Replied to Sarah' in fm['status_reason']
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vault_preview.py::TestActionRequiredStatusFields -v`
Expected: FAIL with `TypeError: write_memory() got an unexpected keyword argument 'status'`

**Step 3: Implement — add status params to write_memory and include in frontmatter**

In `memory/vault.py`, add three parameters to `write_memory()` signature (after `source_memories`):

```python
    source_memories: list[str] = None,
    # Status tracking fields (for action_required reconciliation)
    status: str = None,
    status_reason: str = None,
    status_updated: str = None,
```

In the `elif memory_type == 'action_required':` block (around line 341), add to the frontmatter dict after `'source_memories'`:

```python
        'source_memories': source_memories or [],
        'status': status or 'active',
        'status_reason': status_reason or '',
        'status_updated': status_updated or today,
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vault_preview.py::TestActionRequiredStatusFields -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add memory/vault.py tests/test_vault_preview.py
git commit -m "feat: add status/status_reason/status_updated fields to action_required memories"
```

---

### Task 2: Add status fields to memory MCP server write_memory tool

**Files:**
- Modify: `mcp_servers/memory_server.py:60-81` (write_memory tool schema)
- Modify: `mcp_servers/memory_server.py:169-183` (write_memory call handler)

**Step 1: Add status properties to the write_memory tool schema**

In `mcp_servers/memory_server.py`, inside the `write_memory` Tool inputSchema properties (around line 77, after `"source_memories"`), add:

```python
                    "status": {"type": "string", "enum": ["active", "closed", "expired"], "default": "active"},
                    "status_reason": {"type": "string"},
                    "status_updated": {"type": "string"},
```

**Step 2: Pass new fields in the call_tool handler**

In the `call_tool` function's `if name == "write_memory":` block (around line 169-183), add after `source_memories`:

```python
            source_memories=arguments.get('source_memories'),
            status=arguments.get('status'),
            status_reason=arguments.get('status_reason'),
            status_updated=arguments.get('status_updated'),
```

**Step 3: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/test_vault_preview.py -v`
Expected: All PASSED

**Step 4: Commit**

```bash
git add mcp_servers/memory_server.py
git commit -m "feat: expose status fields in memory MCP server write_memory tool"
```

---

### Task 3: Include status in list_memories API response

**Files:**
- Modify: `memory/vault.py:547-557` (list_memories append block)
- Test: `tests/test_vault_preview.py`

**Step 1: Write the failing test**

Add to `TestActionRequiredStatusFields` in `tests/test_vault_preview.py`:

```python
    def test_list_memories_includes_status(self):
        """list_memories should return status field for action_required items."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            write_memory(
                title="Reply to Jake",
                memory_type="action_required",
                content="Timeline question.",
                quadrant="urgent-important",
                status="closed",
                status_reason="Replied on 2026-02-22",
            )
            memories = list_memories("action_required")

            assert len(memories) == 1
            assert memories[0]['status'] == 'closed'
            assert memories[0]['status_reason'] == 'Replied on 2026-02-22'

    def test_list_memories_status_default_for_old_items(self):
        """Items without status field should default to 'active' in listing."""
        with patch('memory.vault.VAULT_ROOT', TEST_VAULT):
            # Write a non-action_required memory (no status field)
            write_memory(
                title="Chose Python",
                memory_type="decisions",
                content="Selected Python for backend.",
            )
            memories = list_memories("decisions")

            assert len(memories) == 1
            # Non-action_required items won't have status — that's fine
            assert memories[0].get('status') is None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vault_preview.py::TestActionRequiredStatusFields::test_list_memories_includes_status -v`
Expected: FAIL — `KeyError: 'status'`

**Step 3: Implement — add status and status_reason to list_memories output**

In `memory/vault.py`, inside `list_memories()`, modify the `memories.append({...})` block (around line 549-557). Add after `'tags'`:

```python
                    'tags': mem['frontmatter'].get('tags', []),
                    'status': mem['frontmatter'].get('status') if mtype == 'action_required' else None,
                    'status_reason': mem['frontmatter'].get('status_reason') if mtype == 'action_required' else None,
                    'quadrant': mem['frontmatter'].get('quadrant') if mtype == 'action_required' else None,
                    'deadline': mem['frontmatter'].get('deadline') if mtype == 'action_required' else None,
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vault_preview.py::TestActionRequiredStatusFields -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add memory/vault.py tests/test_vault_preview.py
git commit -m "feat: include status, quadrant, deadline in list_memories for action_required type"
```

---

### Task 4: Add fetch_sent_emails tool to Gmail MCP server

**Files:**
- Modify: `mcp_servers/gmail_server.py:77-105` (list_tools)
- Modify: `mcp_servers/gmail_server.py:127-142` (call_tool)

**Step 1: Add the new tool to list_tools**

In `mcp_servers/gmail_server.py`, inside `list_tools()`, add a second Tool after the existing `read_emails` Tool (after line 104):

```python
        Tool(
            name="fetch_sent_emails",
            description=(
                "Fetch emails the user has SENT (from their Sent Mail folder). "
                "Use this to check if the user replied to or followed up on something."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum sent emails to fetch (default: 100)",
                        "default": 100
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch sent emails from last N days (default: 30)",
                        "default": 30
                    }
                }
            }
        ),
```

**Step 2: Add the handler in call_tool**

In `call_tool()`, add a new elif before the `raise ValueError` at the end (before line 142):

```python
    elif name == "fetch_sent_emails":
        emails = fetch_emails(
            max_results=arguments.get('max_results', 100),
            query='in:sent',
            days_back=arguments.get('days_back', 30),
        )
        return [TextContent(
            type="text",
            text=json.dumps(emails, indent=2, default=str)
        )]
```

**Step 3: Run the server manually to verify no import errors**

Run: `python -c "from mcp_servers.gmail_server import server; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add mcp_servers/gmail_server.py
git commit -m "feat: add fetch_sent_emails tool to Gmail MCP server"
```

---

### Task 5: Create the ReconciliationAgent

**Files:**
- Create: `agents/reconciliation_agent.py`
- Test: `tests/test_reconciliation.py`

**Step 1: Write the failing tests**

Create `tests/test_reconciliation.py`:

```python
"""Tests for the ReconciliationAgent's heuristic matching and status logic."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.reconciliation_agent import heuristic_match, check_expiry


class TestHeuristicMatching:
    """Test the heuristic matching function that compares action items to sent emails."""

    def test_subject_overlap_match(self):
        """Should match when sent email subject overlaps with source_emails."""
        action = {
            'source_emails': ['Re: Q2 Project Timeline'],
            'related_to': ['Jake'],
        }
        sent_emails = [
            {'subject': 'Re: Q2 Project Timeline', 'to': 'jake@example.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is not None
        assert 'Q2 Project Timeline' in match['reason']

    def test_recipient_match(self):
        """Should match when sent email recipient matches related_to entity."""
        action = {
            'source_emails': [],
            'related_to': ['Sarah Chen'],
        }
        sent_emails = [
            {'subject': 'Monthly report attached', 'to': 'sarah.chen@company.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is not None
        assert 'Sarah' in match['reason'] or 'sarah' in match['reason'].lower()

    def test_no_match(self):
        """Should return None when no sent email matches."""
        action = {
            'source_emails': ['Budget review needed'],
            'related_to': ['Finance Team'],
        }
        sent_emails = [
            {'subject': 'Lunch plans', 'to': 'friend@example.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is None

    def test_empty_sent_emails(self):
        """Should return None with no sent emails."""
        action = {'source_emails': ['Something'], 'related_to': ['Someone']}
        assert heuristic_match(action, []) is None


class TestExpiryCheck:
    """Test deadline-based expiry logic."""

    def test_past_deadline_is_expired(self):
        """Action with past deadline should be marked expired."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert check_expiry(yesterday) is True

    def test_future_deadline_not_expired(self):
        """Action with future deadline should not be expired."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        assert check_expiry(tomorrow) is False

    def test_no_deadline_not_expired(self):
        """Action with no deadline should not be expired."""
        assert check_expiry('') is False
        assert check_expiry(None) is False

    def test_today_deadline_not_expired(self):
        """Action due today should not be expired yet."""
        today = datetime.now().strftime('%Y-%m-%d')
        assert check_expiry(today) is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reconciliation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.reconciliation_agent'`

**Step 3: Write the ReconciliationAgent**

Create `agents/reconciliation_agent.py`:

```python
# agents/reconciliation_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# The Reconciliation Agent compares open action items from the vault against
# sent Gmail messages to determine which actions have been addressed.
#
# It uses a hybrid approach:
#   1. Heuristic matching — subject/recipient overlap (fast, free)
#   2. LLM analysis — for items the heuristic can't resolve (accurate, costs API)
#   3. Expiry check — past-deadline items marked as expired
#
# Status values: active, closed, expired
# ============================================================================

import json
from datetime import datetime

from agents.base_agent import BaseAgent


# ── HEURISTIC MATCHING ────────────────────────────────────────────────

def heuristic_match(action: dict, sent_emails: list[dict]) -> dict | None:
    """
    Try to match an action item against sent emails using simple heuristics.

    Checks:
    1. Subject overlap: does any sent email subject match a source_email?
    2. Recipient overlap: does any sent email go to someone in related_to?

    Args:
        action:      Dict with 'source_emails' and 'related_to' lists.
        sent_emails: List of dicts with 'subject', 'to', 'date' fields.

    Returns:
        Dict with 'reason' and 'date' if match found, None otherwise.
    """
    source_subjects = [s.lower() for s in (action.get('source_emails') or [])]
    related_entities = [e.lower() for e in (action.get('related_to') or [])]

    for email in sent_emails:
        subject = (email.get('subject') or '').lower()
        recipient = (email.get('to') or '').lower()
        date = email.get('date', '')

        # Check 1: Subject overlap
        for source_subj in source_subjects:
            # Check if core words overlap (strip Re:, Fwd:, etc.)
            clean_source = source_subj.replace('re:', '').replace('fwd:', '').strip()
            clean_sent = subject.replace('re:', '').replace('fwd:', '').strip()
            if clean_source and clean_sent and (
                clean_source in clean_sent or clean_sent in clean_source
            ):
                return {
                    'reason': f"Sent email matching '{email.get('subject', '')}' on {date}",
                    'date': date,
                }

        # Check 2: Recipient matches related_to entity
        for entity in related_entities:
            # Match entity name against recipient (e.g., "sarah chen" in "sarah.chen@company.com")
            entity_parts = entity.split()
            if all(part in recipient for part in entity_parts):
                return {
                    'reason': f"Sent email to {email.get('to', '')} on {date}",
                    'date': date,
                }

    return None


def check_expiry(deadline: str | None) -> bool:
    """
    Check if a deadline has passed.

    Args:
        deadline: Date string in YYYY-MM-DD format, or empty/None.

    Returns:
        True if the deadline is strictly in the past, False otherwise.
    """
    if not deadline:
        return False
    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
        return deadline_date < datetime.now().date()
    except (ValueError, TypeError):
        return False


# ── THE RECONCILIATION AGENT ─────────────────────────────────────────

class ReconciliationAgent(BaseAgent):
    """
    Compares open action items against sent emails to update statuses.

    Uses Memory MCP tools (search_vault, read_memory, write_memory) and
    Gmail MCP tools (fetch_sent_emails) to:
    1. Find active action items
    2. Fetch recent sent emails
    3. Match them (heuristic + LLM)
    4. Update statuses in the vault
    """

    def __init__(self):
        super().__init__()
        self.system_prompt = (
            "You are an action item reconciliation agent. Your job is to determine "
            "which action items have been addressed by comparing them against sent emails.\n\n"
            "You will be given:\n"
            "- A list of open action items (with titles, deadlines, related people, source emails)\n"
            "- A list of recently sent emails (with subjects, recipients, dates)\n\n"
            "For each action item, determine if any sent email indicates the action was taken.\n"
            "Be generous in matching — if someone sent an email to the right person about a "
            "related topic, that likely addresses the action item.\n\n"
            "Respond with a JSON array of updates:\n"
            "[\n"
            '  {"filepath": "action_required/filename.md", "status": "closed", '
            '"status_reason": "Sent email to Jake about timeline on 2026-02-22"}\n'
            "]\n\n"
            "Only include items whose status should change. If an item remains active, omit it."
        )

        # Tools: memory vault + gmail
        self.tools = [
            {
                "name": "search_vault",
                "description": "Search across all memories using text matching.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            },
            {
                "name": "read_memory",
                "description": "Read a specific memory file in full.",
                "input_schema": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all memories, optionally filtered by type.",
                "input_schema": {
                    "type": "object",
                    "properties": {"memory_type": {"type": "string"}}
                }
            },
            {
                "name": "write_memory",
                "description": "Update a memory file in the vault. Use to update status fields.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "memory_type": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["active", "closed", "expired"]},
                        "status_reason": {"type": "string"},
                        "status_updated": {"type": "string"},
                        "quadrant": {"type": "string"},
                        "priority_justification": {"type": "string"},
                        "deadline": {"type": "string"},
                        "source_type": {"type": "string"},
                        "source_memories": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "related_to": {"type": "array", "items": {"type": "string"}},
                        "source_emails": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "memory_type", "content"]
                }
            },
            {
                "name": "fetch_sent_emails",
                "description": "Fetch emails the user has SENT. Use to check if user replied to or followed up on action items.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {"type": "integer", "default": 100},
                        "days_back": {"type": "integer", "default": 30}
                    }
                }
            },
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Route tool calls to the appropriate vault/gmail function."""
        from memory.vault import search_vault, read_memory, list_memories, write_memory
        from tools.gmail_tools import fetch_emails

        if tool_name == "search_vault":
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "read_memory":
            result = read_memory(tool_args['filepath'])
            return json.dumps(result, indent=2)

        elif tool_name == "list_memories":
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "write_memory":
            filepath = write_memory(**tool_args)
            return f"Memory written to: {filepath}"

        elif tool_name == "fetch_sent_emails":
            emails = fetch_emails(
                max_results=tool_args.get('max_results', 100),
                query='in:sent',
                days_back=tool_args.get('days_back', 30),
            )
            return json.dumps(emails, indent=2, default=str)

        raise ValueError(f"Unknown tool: {tool_name}")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_reconciliation.py -v`
Expected: 8 PASSED

**Step 5: Commit**

```bash
git add agents/reconciliation_agent.py tests/test_reconciliation.py
git commit -m "feat: create ReconciliationAgent with heuristic matching and expiry logic"
```

---

### Task 6: Integrate ReconciliationAgent into orchestrator

**Files:**
- Modify: `orchestrator.py:28-59` (imports)
- Modify: `orchestrator.py:94-143` (route method — add reconcile keywords)
- Modify: `orchestrator.py:359-378` (build_memory — add Step 5)
- Add new method: `reconcile_actions()`

**Step 1: Add import**

In `orchestrator.py` imports (around line 38), add after `ActionAgent`:

```python
from agents.reconciliation_agent import ReconciliationAgent
```

**Step 2: Initialize the agent in __init__**

Find the `__init__` method and add after `self.action_agent = ActionAgent()`:

```python
        self.reconciliation_agent = ReconciliationAgent()
```

**Step 3: Add reconcile route**

In `route()` (around line 94-143), add a new elif before the stats check:

```python
    # Check for "reconcile" intent
    elif any(kw in user_lower for kw in [
        'reconcile', 'update actions', 'action status',
        'check actions', 'reconcile actions'
    ]):
        return self.reconcile_actions(user_input)
```

**Step 4: Add Step 5 to build_memory**

In `build_memory()`, after Step 4 (Action Agent, around line 364), add before the build summary:

```python
        # ── Step 5: Reconcile action items ────────────────────
        console.print("\n[bold cyan]Step 5/5: Reconciling action items[/bold cyan]")
        reconcile_result = self.reconcile_actions(
            "Reconcile action items against sent emails.",
            progress_callback=progress_callback
        )
```

Update the step labels earlier in build_memory to say "Step N/5" instead of "Step N/4".

**Step 5: Add reconcile_actions method**

Add after `refresh_actions()` (around line 435):

```python
    def reconcile_actions(self, user_input: str, progress_callback=None) -> str:
        """
        Run the Reconciliation Agent to compare action items against sent emails
        and update statuses (active/closed/expired).
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Reconciliation Agent[/bold cyan] checking action item statuses...\n")
        emit({
            "stage": "reconciliation", "status": "started",
            "message": "Comparing action items against sent emails..."
        })

        self.reconciliation_agent.reset()

        def on_reconcile_retry(attempt, max_retries, delay):
            emit({
                "stage": "reconciliation", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.reconciliation_agent.on_retry = on_reconcile_retry

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')

        prompt = (
            "Reconcile open action items against sent emails. Steps:\n"
            "1. List all action_required memories\n"
            "2. Fetch sent emails from the last 30 days\n"
            "3. For each active action item, check if any sent email addresses it\n"
            "4. Update status to 'closed' (with reason) if action was taken\n"
            "5. Update status to 'expired' if deadline has passed with no action\n"
            f"Today's date is {today}."
        )

        result = self.reconciliation_agent.run(prompt, max_tool_rounds=15)

        console.print("[green]OK - Reconciliation complete[/green]\n")
        emit({
            "stage": "reconciliation", "status": "complete",
            "message": "Action item statuses updated"
        })

        return result
```

**Step 6: Run existing tests to check nothing broke**

Run: `python -m pytest tests/test_retry.py tests/test_config.py -v`
Expected: All PASSED

**Step 7: Commit**

```bash
git add orchestrator.py
git commit -m "feat: integrate ReconciliationAgent into build pipeline and add reconcile route"
```

---

### Task 7: Add action_required tab to vault UI

**Files:**
- Modify: `web/static/index.html:2286-2300` (vault type buttons)
- Modify: `web/static/index.html:3422-3435` (updateVaultCounts)

**Step 1: Add the 4th vault type button**

In `web/static/index.html`, after the "Decisions" button (line 2300), add:

```html
<button class="vault-tree-item" data-type="action_required" onclick="selectVaultType('action_required', this)" aria-label="Action Required">
    <i class="fa-solid fa-bolt vault-tree-icon" aria-hidden="true"></i>
    <span class="vault-tree-label">Action Required</span>
    <span class="vault-tree-count" id="countActionRequired">&mdash;</span>
</button>
```

**Step 2: Update updateVaultCounts to include action_required**

In `updateVaultCounts()` (around line 3422), update the counts object and add the element update:

Change:
```javascript
var counts = { people: 0, decisions: 0, commitments: 0 };
```
To:
```javascript
var counts = { people: 0, decisions: 0, commitments: 0, action_required: 0 };
```

Add after the `countCommitments` line:
```javascript
el = document.getElementById('countActionRequired');
if (el) el.textContent = counts.action_required;
```

**Step 3: Verify in browser**

Run: `python main.py`
Open: http://localhost:8000 → navigate to Vault → verify 4th tab appears

**Step 4: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add action_required tab to vault browser"
```

---

### Task 8: Add status badges to action_required items

**Files:**
- Modify: `web/static/index.html` (CSS section + renderVaultItems function)

**Step 1: Add CSS for status badges**

In the CSS section (after the `.vault-file-date` styles, around line 1370), add:

```css
.vault-status-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-sans);
    padding: 1px 8px;
    border-radius: var(--radius-full);
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.vault-status-badge.status-active {
    background: rgba(76, 175, 80, 0.12);
    color: #2E7D32;
}

.vault-status-badge.status-closed {
    background: rgba(158, 158, 158, 0.12);
    color: #757575;
}

.vault-status-badge.status-expired {
    background: rgba(255, 167, 38, 0.12);
    color: #E65100;
}
```

**Step 2: Update renderVaultItems to show status badges**

In `renderVaultItems()` (around line 3495), after the date span creation and before the tags section, add status badge logic:

```javascript
        // Status badge for action_required items
        if (type === 'action_required') {
            var status = m.status || 'active';
            var badge = document.createElement('span');
            badge.className = 'vault-status-badge status-' + status;
            badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            item.appendChild(badge);
        }
```

**Step 3: Verify in browser**

Verify status badges appear next to action items (will need existing action_required files to test visually).

**Step 4: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add color-coded status badges to action_required items in vault"
```

---

### Task 9: Add filter toggles for action_required status

**Files:**
- Modify: `web/static/index.html` (HTML for toggles, CSS, JS filter logic)

**Step 1: Add CSS for filter toggles**

Add after the status badge CSS:

```css
.vault-filter-bar {
    display: none;
    gap: 4px;
    padding: 0 12px 8px;
    flex-wrap: wrap;
}

.vault-filter-bar.visible {
    display: flex;
}

.vault-filter-btn {
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-medium);
    background: none;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
}

.vault-filter-btn:hover {
    background: var(--surface-warm);
}

.vault-filter-btn.active {
    background: var(--accent-sage-glow);
    color: var(--accent-sage-deep);
    border-color: var(--accent-sage-soft);
}
```

**Step 2: Add filter bar HTML**

In the vault column 2 header (around line 2310), after the search input div, add:

```html
        <div class="vault-filter-bar" id="vaultFilterBar">
            <button class="vault-filter-btn active" data-filter="all" onclick="setStatusFilter('all', this)">All</button>
            <button class="vault-filter-btn" data-filter="active" onclick="setStatusFilter('active', this)">Active</button>
            <button class="vault-filter-btn" data-filter="closed" onclick="setStatusFilter('closed', this)">Closed</button>
            <button class="vault-filter-btn" data-filter="expired" onclick="setStatusFilter('expired', this)">Expired</button>
        </div>
```

**Step 3: Add JS for filter state and toggle**

Add a global variable near the other vault globals:
```javascript
var vaultStatusFilter = 'all';
```

Add the `setStatusFilter` function:
```javascript
window.setStatusFilter = function(filter, btn) {
    vaultStatusFilter = filter;
    var buttons = document.querySelectorAll('.vault-filter-btn');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove('active');
    }
    if (btn) btn.classList.add('active');
    renderVaultItems(vaultSelectedType);
};
```

**Step 4: Show/hide filter bar based on selected type**

In `selectVaultType()`, add after the existing code:
```javascript
    // Show filter bar only for action_required
    var filterBar = document.getElementById('vaultFilterBar');
    if (filterBar) {
        filterBar.classList.toggle('visible', type === 'action_required');
    }
    // Reset filter when switching types
    vaultStatusFilter = 'all';
    var filterBtns = document.querySelectorAll('.vault-filter-btn');
    for (var i = 0; i < filterBtns.length; i++) {
        filterBtns[i].classList.toggle('active', filterBtns[i].getAttribute('data-filter') === 'all');
    }
```

**Step 5: Apply status filter in renderVaultItems**

In `renderVaultItems()`, after the type filter and search filter blocks, add:

```javascript
    // Apply status filter for action_required
    if (type === 'action_required' && vaultStatusFilter !== 'all') {
        filtered = filtered.filter(function(m) {
            return (m.status || 'active') === vaultStatusFilter;
        });
    }
```

**Step 6: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add status filter toggles (All/Active/Closed/Expired) for action_required tab"
```

---

### Task 10: Display action_required fields in content viewer

**Files:**
- Modify: `web/static/index.html` (loadVaultContent function)

**Step 1: Update loadVaultContent to show action_required fields**

In `loadVaultContent()` (around line 3567-3577), after the existing meta entries block (`if (fm.email)...`), add:

```javascript
        // Action Required-specific fields
        if (fm.quadrant) metaEntries.push('Quadrant: ' + fm.quadrant.replace(/-/g, ' '));
        if (fm.deadline) metaEntries.push('Deadline: ' + fm.deadline);
        if (fm.status) metaEntries.push('Status: ' + fm.status.charAt(0).toUpperCase() + fm.status.slice(1));
        if (fm.status_reason) metaEntries.push('Reason: ' + fm.status_reason);
        if (fm.source_type) metaEntries.push('Source: ' + fm.source_type);
```

**Step 2: Commit**

```bash
git add web/static/index.html
git commit -m "feat: display quadrant, deadline, status fields in vault content viewer"
```

---

### Task 11: Update step labels in build_memory

**Files:**
- Modify: `orchestrator.py` (build_memory step labels)

**Step 1: Update all step labels from "/4" to "/5"**

In `build_memory()`, find and update all step number labels:
- "Step 1/4" → "Step 1/5"
- "Step 2/4" → "Step 2/5"
- "Step 3/4" → "Step 3/5"
- "Step 3.5/4" → "Step 3.5/5"
- "Step 4/4" → "Step 4/5"

Also update the pipeline header Panel to mention Step 5:
```python
"    Step 5: Reconciliation Agent -- Update action item statuses\n"
```

**Step 2: Commit**

```bash
git add orchestrator.py
git commit -m "feat: update build pipeline step labels for 5-step pipeline"
```

---

### Task 12: Run full test suite and verify

**Step 1: Run all tests**

Run: `python -m pytest tests/test_vault_preview.py tests/test_reconciliation.py tests/test_retry.py tests/test_config.py -v`
Expected: All PASSED

**Step 2: Run the server and test manually**

Run: `python main.py`

Test checklist:
- [ ] Vault tab shows "Action Required" as 4th category
- [ ] Clicking it shows action items (if any exist)
- [ ] Status badges appear (green Active, gray Closed, light orange Expired)
- [ ] Filter toggles appear and filter correctly
- [ ] Content viewer shows quadrant, deadline, status, status_reason
- [ ] Chat command "reconcile actions" triggers reconciliation
- [ ] Build pipeline shows Step 5 reconciliation

**Step 3: Commit any fixes**

---

### Task 13: Run documenter skill

After all tasks complete, invoke `/documenter` to update:
- `docs/roadmap.md` — mark relevant items complete
- `docs/architecture-overview.md` — add ReconciliationAgent
- `docs/dependency-graph.md` — add reconciliation_agent node
- `docs/data-flow.md` — add reconciliation flow
- `docs/config-map.md` — if any new config
- `docs/api-surface.md` — if any new endpoints
