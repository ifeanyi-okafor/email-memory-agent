# Vault Priority 2 & 3: New Entity Types + Self-Maintenance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Organizations and Projects as first-class vault entity types (Priority 2), then add a Vault Linting Agent, file change detection, and background scheduling for self-maintenance (Priority 3).

**Architecture:** Priority 2 follows the existing pattern for adding memory types — register in MEMORY_TYPES, add frontmatter branch in write_memory(), add Knowledge Index scanner, update agent prompts, wire into graph. Priority 3 adds a new LintAgent that scans for stale/orphaned/contradictory data, a change detection module tracking file hashes, and a lightweight scheduled-task runner invokable via CLI.

**Tech Stack:** Python, pytest, yaml, pathlib, hashlib (no new dependencies)

---

## File Structure

### Priority 2: New Entity Types

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `memory/vault.py` | Add `organizations` + `projects` to MEMORY_TYPES, add frontmatter branches, add write_memory params |
| Modify | `config/settings.py` | Sync MEMORY_TYPES list |
| Modify | `memory/graph.py` | Add new types to MEMORY_CATEGORIES |
| Modify | `memory/knowledge_index.py` | Add `_build_organizations_rows()` and `_build_projects_rows()` |
| Modify | `memory/vault.py` (list_memories) | Add type-specific field extraction for new types |
| Modify | `agents/email_reader.py` | Update system prompt with organizations + projects observation types |
| Modify | `agents/memory_writer.py` | Add organization/project templates and process instructions |
| Modify | `agents/query_agent.py` | Update type awareness in system prompt |
| Create | `tests/test_organizations.py` | Tests for organization entity type end-to-end |
| Create | `tests/test_projects.py` | Tests for project entity type end-to-end |

### Priority 3: Self-Maintenance

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `memory/vault_lint.py` | Pure-function lint checks (no LLM) — stale, orphaned, contradictions |
| Create | `agents/vault_lint_agent.py` | LLM-powered lint agent that interprets results and suggests fixes |
| Modify | `orchestrator.py` | Add "lint"/"health" route, wire lint agent |
| Create | `memory/change_detection.py` | Track mtime + content hash per vault file |
| Create | `memory/scheduler.py` | Lightweight task scheduler with JSON config + state |
| Modify | `main.py` | Add `--run-scheduled` CLI flag |
| Create | `tests/test_vault_lint.py` | Tests for lint checks |
| Create | `tests/test_change_detection.py` | Tests for file change tracking |
| Create | `tests/test_scheduler.py` | Tests for task scheduling |

---

# PRIORITY 2: NEW ENTITY TYPES

## Task 1: Register Organizations + Projects in Vault Core

**Files:**
- Modify: `memory/vault.py:65-71` (MEMORY_TYPES)
- Modify: `config/settings.py:118-124` (MEMORY_TYPES)
- Modify: `memory/graph.py:25` (MEMORY_CATEGORIES)
- Test: `tests/test_organizations.py`

### Step 1.1: Write failing test — organizations vault folder created

- [ ] **Write test**

```python
# tests/test_organizations.py
"""Tests for the Organizations entity type."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Test Helpers ──────────────────────────────────────────────────────

def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault with all memory type folders."""
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


# ============================================================================
# ORGANIZATIONS IN MEMORY_TYPES
# ============================================================================

class TestOrganizationsRegistered:
    def test_organizations_in_memory_types(self):
        """'organizations' should be a valid memory type."""
        from memory.vault import MEMORY_TYPES
        assert 'organizations' in MEMORY_TYPES

    def test_organizations_folder_created_on_init(self, tmp_path, monkeypatch):
        """initialize_vault() should create an organizations/ folder."""
        import memory.vault
        vault = tmp_path / 'vault'
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        memory.vault.initialize_vault()
        assert (vault / 'organizations').exists()
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_organizations.py::TestOrganizationsRegistered -v`
Expected: FAIL — `'organizations' not in MEMORY_TYPES`

### Step 1.2: Add organizations + projects to MEMORY_TYPES

- [ ] **Modify `memory/vault.py:65-71`**

Replace the MEMORY_TYPES list:

```python
MEMORY_TYPES = [
    'decisions',        # Choices: "chose React over Vue"
    'people',           # Contacts: "Sarah — CTO at Acme"
    'commitments',      # Promises: "review PRs by Friday"
    'action_required',  # Action items: prioritized by Eisenhower matrix
    'insights',         # Cross-correlation intelligence
    'organizations',    # Companies, teams, institutions the user interacts with
    'projects',         # Initiatives, deals, products the user is involved in
]
```

- [ ] **Modify `config/settings.py:118-124`** — same change

```python
MEMORY_TYPES = [
    'decisions',        # Choices you've made
    'people',           # People you interact with
    'commitments',      # Promises and deadlines
    'action_required',  # Items that need your attention
    'insights',         # Cross-correlation intelligence
    'organizations',    # Companies, teams, institutions
    'projects',         # Initiatives, deals, products
]
```

- [ ] **Modify `memory/graph.py:25`** — add new types to graph scanning

```python
MEMORY_CATEGORIES = ['decisions', 'people', 'commitments', 'action_required', 'organizations', 'projects']
```

- [ ] **Run test to verify it passes**

Run: `python -m pytest tests/test_organizations.py::TestOrganizationsRegistered -v`
Expected: PASS

- [ ] **Commit**

```bash
git add memory/vault.py config/settings.py memory/graph.py tests/test_organizations.py
git commit -m "feat: register organizations and projects as memory types"
```

---

## Task 2: Organizations Frontmatter + write_memory

**Files:**
- Modify: `memory/vault.py` (write_memory function — add params + frontmatter branch)
- Test: `tests/test_organizations.py`

### Step 2.1: Write failing test — write organization memory

- [ ] **Write test**

Add to `tests/test_organizations.py`:

```python
# ============================================================================
# WRITE ORGANIZATION MEMORY
# ============================================================================

class TestWriteOrganization:
    def test_write_organization_creates_file(self, tmp_path, monkeypatch):
        """write_memory with memory_type='organizations' should create a file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Acme Corp",
                memory_type="organizations",
                content="## Overview\n\nEnterprise software company.",
                tags=["enterprise", "software"],
                org_domain="acme.com",
                org_industry="Technology",
                org_relationship="customer",
            )

        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])

        assert fm['title'] == 'Acme Corp'
        assert fm['category'] == 'organizations'
        assert fm['domain'] == 'acme.com'
        assert fm['industry'] == 'Technology'
        assert fm['relationship_type'] == 'customer'

    def test_organization_frontmatter_has_all_fields(self, tmp_path, monkeypatch):
        """Organization files should have domain, industry, relationship_type in frontmatter."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Stripe",
                memory_type="organizations",
                content="## Overview\n\nPayment processing.",
                org_domain="stripe.com",
                org_industry="Fintech",
                org_relationship="partner",
            )

        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])

        # All org-specific fields should be present
        assert 'domain' in fm
        assert 'industry' in fm
        assert 'relationship_type' in fm
        assert fm['memoryType'] == 'organizations'

    def test_organization_with_empty_fields(self, tmp_path, monkeypatch):
        """Organization with no optional fields should still write successfully."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Unknown Corp",
                memory_type="organizations",
                content="## Overview\n\nLittle information available.",
            )

        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['domain'] == ''
        assert fm['industry'] == ''
        assert fm['relationship_type'] == ''
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_organizations.py::TestWriteOrganization -v`
Expected: FAIL — `write_memory() got an unexpected keyword argument 'org_domain'`

### Step 2.2: Add organization params + frontmatter branch to write_memory

- [ ] **Add parameters to write_memory signature** in `memory/vault.py`

After the people-specific fields (around line 235), add:

```python
    # Organization-specific fields (optional, only used when memory_type == 'organizations')
    org_domain: str = None,
    org_industry: str = None,
    org_relationship: str = None,
```

- [ ] **Add organizations frontmatter branch** in `memory/vault.py`

Insert a new `elif` before the `elif memory_type == 'commitments':` branch (around line 480). Add:

```python
    elif memory_type == 'organizations':
        # ── Organization-specific frontmatter ─────────────────
        # Organizations are companies, teams, or institutions the user
        # interacts with. They have a domain, industry, and relationship type.
        frontmatter = {
            'title': title,
            'date': today,
            'updated': today,
            'category': 'organizations',
            'memoryType': 'organizations',
            'priority': priority,
            'domain': org_domain or '',
            'industry': org_industry or '',
            'relationship_type': org_relationship or '',
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

        wiki_links_section = ''
        if related_to:
            links = ', '.join([f'[[{entity}]]' for entity in related_to])
            wiki_links_section = f'\n**Related:** {links}\n'

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        file_content = f"""---
{yaml_str.strip()}
---

# {title}

{wiki_links_section}
{content}
"""
```

- [ ] **Update list_memories** in `memory/vault.py` to extract org-specific fields

In the `list_memories` function, inside the `memories.append({...})` dict (around line 696-710), add after the `confidence` line:

```python
                    'domain': mem['frontmatter'].get('domain') if mtype == 'organizations' else None,
                    'industry': mem['frontmatter'].get('industry') if mtype == 'organizations' else None,
                    'relationship_type': mem['frontmatter'].get('relationship_type') if mtype == 'organizations' else None,
```

- [ ] **Run test to verify it passes**

Run: `python -m pytest tests/test_organizations.py::TestWriteOrganization -v`
Expected: PASS

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_organizations.py
git commit -m "feat: add organizations frontmatter and write_memory support"
```

---

## Task 3: Projects Frontmatter + write_memory

**Files:**
- Modify: `memory/vault.py` (write_memory — add params + frontmatter branch)
- Create: `tests/test_projects.py`

### Step 3.1: Write failing test — write project memory

- [ ] **Write test**

```python
# tests/test_projects.py
"""Tests for the Projects entity type."""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_vault(tmp_path, monkeypatch):
    """Create a temporary vault with all memory type folders."""
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


class TestProjectsRegistered:
    def test_projects_in_memory_types(self):
        """'projects' should be a valid memory type."""
        from memory.vault import MEMORY_TYPES
        assert 'projects' in MEMORY_TYPES

    def test_projects_folder_created_on_init(self, tmp_path, monkeypatch):
        """initialize_vault() should create a projects/ folder."""
        import memory.vault
        vault = tmp_path / 'vault'
        monkeypatch.setattr(memory.vault, 'VAULT_ROOT', vault)
        memory.vault.initialize_vault()
        assert (vault / 'projects').exists()


class TestWriteProject:
    def test_write_project_creates_file(self, tmp_path, monkeypatch):
        """write_memory with memory_type='projects' should create a file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Series A Fundraising",
                memory_type="projects",
                content="## Overview\n\nRaising seed round.",
                tags=["fundraising"],
                project_status="active",
                project_type="deal",
            )

        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])

        assert fm['title'] == 'Series A Fundraising'
        assert fm['category'] == 'projects'
        assert fm['project_status'] == 'active'
        assert fm['project_type'] == 'deal'

    def test_project_frontmatter_has_all_fields(self, tmp_path, monkeypatch):
        """Project files should have project_status, project_type, started in frontmatter."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Product Launch Q2",
                memory_type="projects",
                content="## Overview\n\nQ2 launch prep.",
                project_status="planning",
                project_type="product",
            )

        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])

        assert 'project_status' in fm
        assert 'project_type' in fm
        assert fm['memoryType'] == 'projects'

    def test_project_default_status(self, tmp_path, monkeypatch):
        """Projects without explicit status should default to 'active'."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            filepath = write_memory(
                title="Unnamed Project",
                memory_type="projects",
                content="## Overview\n\nSomething.",
            )

        text = Path(filepath).read_text(encoding='utf-8')
        fm = yaml.safe_load(text.split('---')[1])
        assert fm['project_status'] == 'active'
        assert fm['project_type'] == ''
```

- [ ] **Run test to verify it fails**

Run: `python -m pytest tests/test_projects.py -v`
Expected: FAIL — `write_memory() got an unexpected keyword argument 'project_status'`

### Step 3.2: Add project params + frontmatter branch to write_memory

- [ ] **Add parameters to write_memory signature** in `memory/vault.py`

After the organization fields, add:

```python
    # Project-specific fields (optional, only used when memory_type == 'projects')
    project_status: str = None,
    project_type: str = None,
```

- [ ] **Add projects frontmatter branch** in `memory/vault.py`

Insert a new `elif` after the organizations branch, before commitments:

```python
    elif memory_type == 'projects':
        # ── Project-specific frontmatter ──────────────────────
        # Projects are initiatives, deals, or products the user tracks.
        # They have a status lifecycle and a type classification.
        frontmatter = {
            'title': title,
            'date': today,
            'updated': today,
            'category': 'projects',
            'memoryType': 'projects',
            'priority': priority,
            'project_status': project_status or 'active',
            'project_type': project_type or '',
            'tags': tags or [],
            'related_to': related_to or [],
        }
        if source_emails:
            frontmatter['source_emails'] = source_emails

        wiki_links_section = ''
        if related_to:
            links = ', '.join([f'[[{entity}]]' for entity in related_to])
            wiki_links_section = f'\n**Related:** {links}\n'

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        file_content = f"""---
{yaml_str.strip()}
---

# {title}

{wiki_links_section}
{content}
"""
```

- [ ] **Update list_memories** — add project-specific field extraction

After the organization fields, add:

```python
                    'project_status': mem['frontmatter'].get('project_status') if mtype == 'projects' else None,
                    'project_type': mem['frontmatter'].get('project_type') if mtype == 'projects' else None,
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_projects.py tests/test_organizations.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/vault.py tests/test_projects.py
git commit -m "feat: add projects frontmatter and write_memory support"
```

---

## Task 4: Knowledge Index for Organizations + Projects

**Files:**
- Modify: `memory/knowledge_index.py`
- Modify: `tests/test_knowledge_index.py`

### Step 4.1: Write failing tests

- [ ] **Add tests to `tests/test_knowledge_index.py`**

Add a new test class:

```python
class TestBuildKnowledgeIndexNewTypes:
    def test_organizations_appear_with_domain(self, tmp_path, monkeypatch):
        """Organization files should appear with title, domain, industry, relationship."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'organizations', 'acme-a1b2.md', {
            'title': 'Acme Corp',
            'date': '2026-02-20',
            'category': 'organizations',
            'domain': 'acme.com',
            'industry': 'Technology',
            'relationship_type': 'customer',
        })
        index = build_knowledge_index()
        assert 'Acme Corp' in index
        assert 'acme.com' in index
        assert 'Technology' in index
        assert 'customer' in index
        assert 'organizations/acme-a1b2.md' in index

    def test_projects_appear_with_status(self, tmp_path, monkeypatch):
        """Project files should appear with title, status, type."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'projects', 'series-a-a1b2.md', {
            'title': 'Series A Fundraising',
            'date': '2026-02-20',
            'category': 'projects',
            'project_status': 'active',
            'project_type': 'deal',
        })
        index = build_knowledge_index()
        assert 'Series A Fundraising' in index
        assert 'active' in index
        assert 'deal' in index
        assert 'projects/series-a-a1b2.md' in index
```

Also update `_setup_vault` in this test file to include the new folders:

```python
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_knowledge_index.py::TestBuildKnowledgeIndexNewTypes -v`
Expected: FAIL — organizations/projects not in index output

### Step 4.2: Add index builders for new types

- [ ] **Add to `memory/knowledge_index.py`**

Add `_build_organizations_rows()` function:

```python
def _build_organizations_rows() -> list[str]:
    """Build table rows for organization files."""
    rows = []
    org_dir = VAULT_ROOT / 'organizations'
    if not org_dir.exists():
        return rows
    for md_file in sorted(org_dir.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = _safe(fm.get('title', md_file.stem))
        domain = _safe(fm.get('domain', ''))
        industry = _safe(fm.get('industry', ''))
        rel_type = _safe(fm.get('relationship_type', ''))
        rows.append(f"| {rel_path} | {title} | {domain} | {industry} | {rel_type} |")
    return rows
```

Add `_build_projects_rows()` function:

```python
def _build_projects_rows() -> list[str]:
    """Build table rows for project files."""
    rows = []
    proj_dir = VAULT_ROOT / 'projects'
    if not proj_dir.exists():
        return rows
    for md_file in sorted(proj_dir.glob('*.md')):
        fm = _parse_frontmatter(md_file)
        rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
        title = _safe(fm.get('title', md_file.stem))
        status = _safe(fm.get('project_status', ''))
        ptype = _safe(fm.get('project_type', ''))
        rows.append(f"| {rel_path} | {title} | {status} | {ptype} |")
    return rows
```

Add Organizations and Projects sections to `build_knowledge_index()`, after Insights:

```python
    # Organizations
    org_rows = _build_organizations_rows()
    sections.append("## Organizations")
    sections.append("| File | Title | Domain | Industry | Relationship |")
    sections.append("|------|-------|--------|----------|--------------|")
    if org_rows:
        sections.extend(org_rows)
    else:
        sections.append("| (none) | | | | |")

    sections.append("")

    # Projects
    proj_rows = _build_projects_rows()
    sections.append("## Projects")
    sections.append("| File | Title | Status | Type |")
    sections.append("|------|-------|--------|------|")
    if proj_rows:
        sections.extend(proj_rows)
    else:
        sections.append("| (none) | | | |")
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_knowledge_index.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/knowledge_index.py tests/test_knowledge_index.py
git commit -m "feat: add organizations and projects to Knowledge Index"
```

---

## Task 5: Update Agent Prompts for New Types

**Files:**
- Modify: `agents/email_reader.py` (system prompt)
- Modify: `agents/memory_writer.py` (system prompt + tool schema)
- Modify: `agents/query_agent.py` (system prompt)
- Modify: `mcp_servers/memory_server.py` (write_memory tool schema)

### Step 5.1: Update Email Reader system prompt

- [ ] **Modify `agents/email_reader.py`**

In the system prompt, find the analysis section (around line 84-86) and add:

```
- What organizations/companies are mentioned? (organizations)
- What projects, initiatives, or deals are being tracked? (projects)
```

Find the granularity rules section (around lines 136-154) and add:

```
- Create ONE observation per ORGANIZATION (companies, institutions, teams)
- Create ONE observation per PROJECT (initiatives, deals, products, campaigns)
```

Find the observation types restriction (around line 240) and update:

```
- Use ONLY these types: decisions, people, commitments, action_required, organizations, projects
```

Add the organization observation format after the people format:

```
FOR "organizations" OBSERVATIONS — include additional "org_data" object:
{
    "type": "organizations",
    "title": "Acme Corp",
    "content": "Enterprise software company. Primary customer for Q2 deal.",
    "priority": "🟡",
    "evidence_emails": ["Re: Acme contract", "Acme onboarding"],
    "tags": ["customer", "enterprise"],
    "related_entities": ["Sarah Chen", "Series A"],
    "org_data": {
        "domain": "acme.com",
        "industry": "Enterprise Software",
        "relationship_type": "customer"
    }
}

FOR "projects" OBSERVATIONS — include additional "project_data" object:
{
    "type": "projects",
    "title": "Q2 Product Launch",
    "content": "Major product launch planned for Q2. Cross-team initiative.",
    "priority": "🔴",
    "evidence_emails": ["Re: Launch timeline", "Q2 planning"],
    "tags": ["product", "launch"],
    "related_entities": ["Alice Park", "Acme Corp"],
    "project_data": {
        "project_status": "active",
        "project_type": "product"
    }
}
```

Add guidelines for when to create each type:

```
ORGANIZATION RULES:
- Create observations for companies, institutions, or teams that appear repeatedly
- Do NOT create organization observations for the user's own company (that goes in the "Me" person file)
- Include domain (website), industry, and how the user relates to them (customer/partner/vendor/prospect)

PROJECT RULES:
- Create observations for initiatives, deals, products, or campaigns being actively tracked
- Include status (active/planning/on-hold/completed/cancelled) and type (deal/product/initiative/hiring)
- Link to related people and organizations via related_entities
```

### Step 5.2: Update Memory Writer system prompt

- [ ] **Modify `agents/memory_writer.py`**

In the MEMORY TYPE GUIDELINES section (around line 94-108), add:

```
- "organizations" — Companies, teams, or institutions the user interacts with.
  Uses org-specific fields: org_domain, org_industry, org_relationship.
  Do NOT create organization entries for the user's own company — that info goes in the Me file.
- "projects" — Initiatives, deals, products, or campaigns the user tracks.
  Uses project-specific fields: project_status (active/planning/on-hold/completed/cancelled),
  project_type (deal/product/initiative/hiring).
```

Add organization and project templates after the person template:

```
═══════════════════════════════════════════════════════════════
ORGANIZATION MEMORY TEMPLATE
═══════════════════════════════════════════════════════════════

## Overview
[Brief description: what this organization does, user's relationship]

## Key Contacts
- [[Person Name]] — Role at this org

## Interactions
### YYYY-MM-DD
[Notable interaction summary]

## Notes
[Additional context]

═══════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════
PROJECT MEMORY TEMPLATE
═══════════════════════════════════════════════════════════════

## Overview
[Brief description: what this project is, its goal]

## Status
[Current status and next steps]

## People Involved
- [[Person Name]] — Role in project

## Timeline
### YYYY-MM-DD
[Key milestone or decision]

## Decisions
- [Key decisions made about this project]

## Notes
[Additional context]

═══════════════════════════════════════════════════════════════
```

Add tool schema properties for new types in the `write_memory` tool definition:

```python
"org_domain": {
    "type": "string",
    "description": "Organization's website domain (organizations only)"
},
"org_industry": {
    "type": "string",
    "description": "Organization's industry (organizations only)"
},
"org_relationship": {
    "type": "string",
    "description": "How the user relates: customer, partner, vendor, prospect, employer (organizations only)"
},
"project_status": {
    "type": "string",
    "enum": ["active", "planning", "on-hold", "completed", "cancelled"],
    "description": "Project lifecycle status (projects only)"
},
"project_type": {
    "type": "string",
    "description": "Type: deal, product, initiative, hiring (projects only)"
},
```

Also update the `execute_tool` method to pass new params through:

```python
if tool_name == "write_memory":
    filepath = write_memory(**tool_args)
    return f"Memory written to: {filepath}"
```

This already works since it uses `**tool_args` — the new params will pass through automatically.

### Step 5.3: Update Query Agent system prompt

- [ ] **Modify `agents/query_agent.py`**

Find the memory types awareness section and update:

```
Memories are organized by type: decisions, people, commitments, action_required,
insights, organizations, projects.
Organizations capture companies/institutions with domain, industry, and relationship type.
Projects capture initiatives/deals with status and type.
```

### Step 5.4: Update MCP server tool schema

- [ ] **Modify `mcp_servers/memory_server.py`**

In the `write_memory` tool inputSchema (around line 68), add after the existing optional properties:

```python
"org_domain": {"type": "string"},
"org_industry": {"type": "string"},
"org_relationship": {"type": "string"},
"project_status": {"type": "string", "enum": ["active", "planning", "on-hold", "completed", "cancelled"]},
"project_type": {"type": "string"},
```

In the `call_tool` handler for `write_memory` (around line 174), add the new fields:

```python
org_domain=arguments.get('org_domain'),
org_industry=arguments.get('org_industry'),
org_relationship=arguments.get('org_relationship'),
project_status=arguments.get('project_status'),
project_type=arguments.get('project_type'),
```

- [ ] **Run all tests to verify no regressions**

Run: `python -m pytest tests/test_organizations.py tests/test_projects.py tests/test_knowledge_index.py tests/test_dedup.py -v`
Expected: ALL PASS (excluding the pre-existing dedup test failure)

- [ ] **Commit**

```bash
git add agents/email_reader.py agents/memory_writer.py agents/query_agent.py mcp_servers/memory_server.py
git commit -m "feat: update agent prompts and MCP server for organizations and projects"
```

---

## Task 6: Integration Tests for New Entity Types

**Files:**
- Modify: `tests/test_organizations.py`
- Modify: `tests/test_projects.py`

### Step 6.1: Add organization dedup + Knowledge Index + changelog tests

- [ ] **Add to `tests/test_organizations.py`**

```python
class TestOrganizationDedup:
    def test_duplicate_org_merges(self, tmp_path, monkeypatch):
        """Writing the same org twice should merge into one file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            path1 = write_memory(
                title="Acme Corp", memory_type="organizations",
                content="## Overview\n\nSoftware company.", tags=["software"],
                org_domain="acme.com",
            )
            path2 = write_memory(
                title="Acme Corp", memory_type="organizations",
                content="## Overview\n\nUpdated: enterprise software.", tags=["enterprise"],
                org_industry="Enterprise Software",
            )

        assert Path(path1).name == Path(path2).name
        files = list((vault / 'organizations').glob('*.md'))
        assert len(files) == 1


class TestOrganizationInKnowledgeIndex:
    def test_org_appears_in_index(self, tmp_path, monkeypatch):
        """After writing an org, it should appear in the Knowledge Index."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.knowledge_index
        monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Stripe", memory_type="organizations",
                content="## Overview\n\nPayments.", org_domain="stripe.com",
            )

        from memory.knowledge_index import build_knowledge_index
        index = build_knowledge_index()
        assert 'Stripe' in index
        assert 'stripe.com' in index


class TestOrganizationInChangelog:
    def test_org_write_logged(self, tmp_path, monkeypatch):
        """Writing an org should create a changelog entry."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Acme Corp", memory_type="organizations",
                content="## Overview\n\nSoftware.",
            )

        from memory.changelog import read_changelog
        changelog = read_changelog()
        assert 'CREATED' in changelog
        assert 'Acme Corp' in changelog
```

### Step 6.2: Add project integration tests

- [ ] **Add to `tests/test_projects.py`**

```python
class TestProjectDedup:
    def test_duplicate_project_merges(self, tmp_path, monkeypatch):
        """Writing the same project twice should merge into one file."""
        vault = _setup_vault(tmp_path, monkeypatch)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            path1 = write_memory(
                title="Series A Fundraising", memory_type="projects",
                content="## Overview\n\nRaising seed.",
                project_status="active", tags=["fundraising"],
            )
            path2 = write_memory(
                title="Series A Fundraising", memory_type="projects",
                content="## Overview\n\nRound in progress.",
                project_status="active", tags=["investor"],
            )

        assert Path(path1).name == Path(path2).name
        files = list((vault / 'projects').glob('*.md'))
        assert len(files) == 1


class TestProjectInKnowledgeIndex:
    def test_project_appears_in_index(self, tmp_path, monkeypatch):
        """After writing a project, it should appear in the Knowledge Index."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import memory.knowledge_index
        monkeypatch.setattr(memory.knowledge_index, 'VAULT_ROOT', vault)

        with patch('memory.graph.rebuild_graph', return_value={'nodes': {}, 'edges': []}):
            from memory.vault import write_memory
            write_memory(
                title="Q2 Launch", memory_type="projects",
                content="## Overview\n\nLaunch.", project_status="planning",
            )

        from memory.knowledge_index import build_knowledge_index
        index = build_knowledge_index()
        assert 'Q2 Launch' in index
        assert 'planning' in index
```

- [ ] **Run all new entity type tests**

Run: `python -m pytest tests/test_organizations.py tests/test_projects.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add tests/test_organizations.py tests/test_projects.py
git commit -m "test: add integration tests for organizations and projects entity types"
```

---

# PRIORITY 3: SELF-MAINTENANCE

## Task 7: Vault Lint Checks (Pure Functions)

**Files:**
- Create: `memory/vault_lint.py`
- Create: `tests/test_vault_lint.py`

### Step 7.1: Write failing tests for lint checks

- [ ] **Write tests**

```python
# tests/test_vault_lint.py
"""Tests for vault lint checks (memory/vault_lint.py)."""

import sys
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
        """Active action items past their deadline should be flagged as stale."""
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
        """Closed action items past deadline should NOT be flagged."""
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
        """Action items with future deadlines should not be flagged."""
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
        """Files with no related_to and no graph connections should be flagged."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'lonely-a1b2.md', {
            'title': 'Lonely Decision',
            'category': 'decisions',
            'related_to': [],
            'tags': [],
        })
        # Write an empty graph
        import json
        (vault / '_graph.json').write_text(json.dumps({
            'nodes': {'decisions/lonely-a1b2.md': {'title': 'Lonely Decision', 'type': 'decisions'}},
            'edges': [],
        }))

        results = run_lint_checks()
        orphaned = [r for r in results if r['check'] == 'orphaned_file']
        assert len(orphaned) == 1
        assert 'Lonely Decision' in orphaned[0]['description']

    def test_connected_file_not_orphaned(self, tmp_path, monkeypatch):
        """Files with graph connections should NOT be flagged."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'decisions', 'connected-a1b2.md', {
            'title': 'Connected Decision',
            'category': 'decisions',
            'related_to': ['Alice'],
        })
        import json
        (vault / '_graph.json').write_text(json.dumps({
            'nodes': {'decisions/connected-a1b2.md': {'title': 'Connected', 'type': 'decisions'}},
            'edges': [{'from': 'decisions/connected-a1b2.md', 'to': 'people/alice.md', 'relation': 'related_to'}],
        }))

        results = run_lint_checks()
        orphaned = [r for r in results if r['check'] == 'orphaned_file']
        assert len(orphaned) == 0


class TestLintEmptyFiles:
    def test_detects_empty_content(self, tmp_path, monkeypatch):
        """Files with only frontmatter and no body content should be flagged."""
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
        """A clean vault with no issues should return an empty list."""
        vault = _setup_vault(tmp_path, monkeypatch)
        import json
        (vault / '_graph.json').write_text(json.dumps({'nodes': {}, 'edges': []}))

        results = run_lint_checks()
        assert results == []


class TestLintReturnFormat:
    def test_result_has_required_fields(self, tmp_path, monkeypatch):
        """Each lint result should have check, severity, filepath, description."""
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
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_vault_lint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memory.vault_lint'`

### Step 7.2: Implement vault lint checks

- [ ] **Create `memory/vault_lint.py`**

```python
# memory/vault_lint.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Pure-function lint checks for the memory vault. Scans for common
# issues like stale data, orphaned files, and empty content.
#
# These are heuristic checks — no LLM calls. The Vault Lint Agent
# (agents/vault_lint_agent.py) uses these results to produce
# human-readable reports and suggest fixes.
# ============================================================================

import json
import yaml
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path('vault')

MEMORY_TYPES = [
    'decisions', 'people', 'commitments', 'action_required',
    'insights', 'organizations', 'projects',
]


def _parse_frontmatter(filepath: Path) -> dict:
    """Read YAML frontmatter from a markdown file."""
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


def _parse_body(filepath: Path) -> str:
    """Read the body content (after frontmatter) from a markdown file."""
    try:
        text = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''
    if not text.startswith('---'):
        return text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return text
    # Strip the # heading line — just return the actual content
    import re
    body = parts[2].strip()
    body = re.sub(r'^#\s+[^\n]+\n*', '', body).strip()
    return body


def run_lint_checks() -> list[dict]:
    """
    Run all lint checks on the vault and return a list of issues.

    Each issue is a dict with:
        check:       str — which check found the issue
        severity:    str — 'error', 'warning', or 'info'
        filepath:    str — path to the affected file (relative to vault)
        description: str — human-readable description of the issue

    Returns an empty list if the vault is clean.
    """
    issues = []
    issues.extend(_check_stale_action_items())
    issues.extend(_check_orphaned_files())
    issues.extend(_check_empty_content())
    return issues


def _check_stale_action_items() -> list[dict]:
    """Find active action items whose deadline has passed."""
    issues = []
    action_dir = VAULT_ROOT / 'action_required'
    if not action_dir.exists():
        return issues

    today = datetime.now().strftime('%Y-%m-%d')

    for md_file in action_dir.glob('*.md'):
        fm = _parse_frontmatter(md_file)
        status = fm.get('status', 'active')
        deadline = str(fm.get('deadline', ''))
        title = fm.get('title', md_file.stem)

        if status == 'active' and deadline and deadline < today:
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            issues.append({
                'check': 'stale_action_item',
                'severity': 'warning',
                'filepath': rel_path,
                'description': f'Action item "{title}" is active but past deadline ({deadline})',
            })

    return issues


def _check_orphaned_files() -> list[dict]:
    """Find files with no graph connections (no edges in or out)."""
    issues = []
    graph_file = VAULT_ROOT / '_graph.json'

    if not graph_file.exists():
        return issues

    try:
        graph = json.loads(graph_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return issues

    edges = graph.get('edges', [])
    nodes = graph.get('nodes', {})

    # Build set of all files that participate in any edge
    connected = set()
    for edge in edges:
        connected.add(edge.get('from', ''))
        connected.add(edge.get('to', ''))

    # Check each node — if it has no edges, it's orphaned
    for filepath, node_data in nodes.items():
        if filepath not in connected:
            title = node_data.get('title', filepath)
            issues.append({
                'check': 'orphaned_file',
                'severity': 'info',
                'filepath': filepath,
                'description': f'File "{title}" has no connections in the knowledge graph',
            })

    return issues


def _check_empty_content() -> list[dict]:
    """Find files with no meaningful body content (just frontmatter + heading)."""
    issues = []

    for mtype in MEMORY_TYPES:
        folder = VAULT_ROOT / mtype
        if not folder.exists():
            continue

        for md_file in folder.glob('*.md'):
            body = _parse_body(md_file)
            fm = _parse_frontmatter(md_file)
            title = fm.get('title') or fm.get('name', md_file.stem)

            if not body.strip():
                rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
                issues.append({
                    'check': 'empty_content',
                    'severity': 'warning',
                    'filepath': rel_path,
                    'description': f'File "{title}" has no body content (only frontmatter)',
                })

    return issues
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_vault_lint.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/vault_lint.py tests/test_vault_lint.py
git commit -m "feat: add vault lint checks for stale data, orphans, and empty content"
```

---

## Task 8: Vault Lint Agent + Orchestrator Integration

**Files:**
- Create: `agents/vault_lint_agent.py`
- Modify: `orchestrator.py` (add route + handler)

### Step 8.1: Create the Vault Lint Agent

- [ ] **Create `agents/vault_lint_agent.py`**

```python
# agents/vault_lint_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the Vault Lint Agent — it runs the programmatic lint checks
# from memory/vault_lint.py and produces a human-readable report.
#
# Unlike other agents, this one doesn't need LLM calls for the checks
# themselves (they're pure functions). It formats the results into a
# clear, actionable report.
# ============================================================================

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault_lint import run_lint_checks
from memory.vault import get_vault_stats


def run_vault_lint() -> str:
    """
    Run all vault lint checks and return a formatted report.

    Returns:
        str: Human-readable report of vault health issues.
    """
    issues = run_lint_checks()
    stats = get_vault_stats()

    if not issues:
        return (
            f"Vault Health Check: ALL CLEAR\n\n"
            f"Scanned {stats['total']} memories across {len(stats) - 1} categories.\n"
            f"No issues found — vault is clean!"
        )

    # Group by severity
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    infos = [i for i in issues if i['severity'] == 'info']

    report = f"Vault Health Check: {len(issues)} issue(s) found\n\n"
    report += f"Scanned {stats['total']} memories.\n\n"

    if errors:
        report += f"ERRORS ({len(errors)}):\n"
        for issue in errors:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"
        report += "\n"

    if warnings:
        report += f"WARNINGS ({len(warnings)}):\n"
        for issue in warnings:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"
        report += "\n"

    if infos:
        report += f"INFO ({len(infos)}):\n"
        for issue in infos:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"

    return report
```

### Step 8.2: Wire into orchestrator

- [ ] **Add import to `orchestrator.py`**

After the existing agent imports (around line 48):

```python
from agents.vault_lint_agent import run_vault_lint
```

- [ ] **Add route keywords** in `route()` method

After the "deduplicate" check (around line 164), add:

```python
        # ── Check for "lint"/"health check" intent ─────────────
        elif any(kw in user_lower for kw in [
            'lint', 'health check', 'vault health', 'audit vault',
            'check vault', 'vault issues'
        ]):
            return self.lint_vault()
```

- [ ] **Add handler method** after `deduplicate_vault()`:

```python
    def lint_vault(self, progress_callback=None) -> str:
        """
        Run vault health checks and return a formatted report.

        Checks for stale action items, orphaned files, empty content,
        and other vault quality issues.
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Vault Health Check[/bold cyan] scanning for issues...\n")
        emit({
            "stage": "vault_lint", "status": "started",
            "message": "Running vault health checks..."
        })

        result = run_vault_lint()

        console.print(f"[green]{result.split(chr(10))[0]}[/green]\n")
        emit({
            "stage": "vault_lint", "status": "complete",
            "message": result.split('\n')[0]
        })

        return result
```

- [ ] **Run all tests to verify no regressions**

Run: `python -m pytest tests/test_vault_lint.py tests/test_organizations.py tests/test_projects.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add agents/vault_lint_agent.py orchestrator.py
git commit -m "feat: add vault lint agent and orchestrator integration"
```

---

## Task 9: Change Detection Module

**Files:**
- Create: `memory/change_detection.py`
- Create: `tests/test_change_detection.py`

### Step 9.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_change_detection.py
"""Tests for vault file change detection (memory/change_detection.py)."""

import sys
import json
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.change_detection import (
    scan_vault_state,
    detect_changes,
    save_state,
    load_state,
)


def _setup_vault(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for mtype in ('decisions', 'people', 'commitments', 'action_required',
                   'insights', 'organizations', 'projects'):
        (vault / mtype).mkdir()
    monkeypatch.setattr('memory.change_detection.VAULT_ROOT', vault)
    monkeypatch.setattr('memory.change_detection.STATE_FILE',
                        vault / '_file_state.json')
    return vault


def _write_vault_file(vault_dir, memory_type, filename, content='test'):
    filepath = vault_dir / memory_type / filename
    filepath.write_text(content, encoding='utf-8')
    return filepath


class TestScanVaultState:
    def test_empty_vault_returns_empty(self, tmp_path, monkeypatch):
        """An empty vault should return an empty state dict."""
        _setup_vault(tmp_path, monkeypatch)
        state = scan_vault_state()
        assert state == {}

    def test_scans_all_files(self, tmp_path, monkeypatch):
        """Should include all .md files across all memory types."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md')
        _write_vault_file(vault, 'decisions', 'react.md')

        state = scan_vault_state()
        assert len(state) == 2
        assert 'people/alice.md' in state
        assert 'decisions/react.md' in state

    def test_state_includes_hash(self, tmp_path, monkeypatch):
        """Each entry should include a content hash."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'hello world')

        state = scan_vault_state()
        entry = state['people/alice.md']
        assert 'hash' in entry
        assert isinstance(entry['hash'], str)
        assert len(entry['hash']) == 64  # SHA-256 hex digest


class TestDetectChanges:
    def test_new_file_detected(self, tmp_path, monkeypatch):
        """A file not in the previous state should be reported as 'added'."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md')

        old_state = {}
        new_state = scan_vault_state()
        changes = detect_changes(old_state, new_state)

        assert len(changes['added']) == 1
        assert 'people/alice.md' in changes['added']

    def test_modified_file_detected(self, tmp_path, monkeypatch):
        """A file with a different hash should be reported as 'modified'."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'version 1')

        old_state = scan_vault_state()

        _write_vault_file(vault, 'people', 'alice.md', 'version 2')
        new_state = scan_vault_state()

        changes = detect_changes(old_state, new_state)
        assert len(changes['modified']) == 1
        assert 'people/alice.md' in changes['modified']

    def test_deleted_file_detected(self, tmp_path, monkeypatch):
        """A file in old state but not new should be reported as 'deleted'."""
        vault = _setup_vault(tmp_path, monkeypatch)
        filepath = _write_vault_file(vault, 'people', 'alice.md')

        old_state = scan_vault_state()

        filepath.unlink()
        new_state = scan_vault_state()

        changes = detect_changes(old_state, new_state)
        assert len(changes['deleted']) == 1
        assert 'people/alice.md' in changes['deleted']

    def test_unchanged_file_not_reported(self, tmp_path, monkeypatch):
        """A file with the same hash should not appear in changes."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'stable')

        state = scan_vault_state()
        changes = detect_changes(state, state)

        assert changes['added'] == []
        assert changes['modified'] == []
        assert changes['deleted'] == []

    def test_no_changes_returns_empty_lists(self, tmp_path, monkeypatch):
        """No changes at all should return empty lists for all categories."""
        _setup_vault(tmp_path, monkeypatch)
        changes = detect_changes({}, {})
        assert changes == {'added': [], 'modified': [], 'deleted': []}


class TestStatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """Saved state should be loadable."""
        vault = _setup_vault(tmp_path, monkeypatch)
        _write_vault_file(vault, 'people', 'alice.md', 'hello')

        state = scan_vault_state()
        save_state(state)
        loaded = load_state()

        assert loaded == state

    def test_load_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """Loading when no state file exists should return empty dict."""
        _setup_vault(tmp_path, monkeypatch)
        loaded = load_state()
        assert loaded == {}
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_change_detection.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 9.2: Implement change detection

- [ ] **Create `memory/change_detection.py`**

```python
# memory/change_detection.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Tracks the state of vault files using content hashes (SHA-256).
# Enables detecting which files were added, modified, or deleted
# between two points in time.
#
# Inspired by Rowboat's graph_state.ts — hybrid mtime + hash strategy.
# We use hash-only (no mtime) since the vault is small enough that
# rehashing all files is fast, and it avoids false positives from
# mtime changes without content changes (e.g., git checkout).
# ============================================================================

import json
import hashlib
from pathlib import Path

VAULT_ROOT = Path('vault')
STATE_FILE = VAULT_ROOT / '_file_state.json'

MEMORY_TYPES = [
    'decisions', 'people', 'commitments', 'action_required',
    'insights', 'organizations', 'projects',
]


def _hash_file(filepath: Path) -> str:
    """Compute SHA-256 hash of a file's content."""
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()


def scan_vault_state() -> dict:
    """
    Scan all vault files and return a state dict mapping
    relative file paths to their content hashes.

    Returns:
        Dict like: {'people/alice.md': {'hash': 'abc123...'}, ...}
    """
    state = {}

    for mtype in MEMORY_TYPES:
        folder = VAULT_ROOT / mtype
        if not folder.exists():
            continue

        for md_file in sorted(folder.glob('*.md')):
            rel_path = md_file.relative_to(VAULT_ROOT).as_posix()
            state[rel_path] = {
                'hash': _hash_file(md_file),
            }

    return state


def detect_changes(old_state: dict, new_state: dict) -> dict:
    """
    Compare two vault states and return the differences.

    Args:
        old_state: Previous state from scan_vault_state() or load_state()
        new_state: Current state from scan_vault_state()

    Returns:
        Dict with three lists:
        {
            'added': ['people/new-person.md'],
            'modified': ['decisions/updated.md'],
            'deleted': ['commitments/removed.md'],
        }
    """
    old_paths = set(old_state.keys())
    new_paths = set(new_state.keys())

    added = sorted(new_paths - old_paths)
    deleted = sorted(old_paths - new_paths)

    modified = []
    for path in sorted(old_paths & new_paths):
        if old_state[path]['hash'] != new_state[path]['hash']:
            modified.append(path)

    return {'added': added, 'modified': modified, 'deleted': deleted}


def save_state(state: dict):
    """Save vault state to disk for future comparison."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def load_state() -> dict:
    """Load previously saved vault state. Returns empty dict if no file."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_change_detection.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/change_detection.py tests/test_change_detection.py
git commit -m "feat: add vault file change detection with SHA-256 hashing"
```

---

## Task 10: Background Task Scheduler

**Files:**
- Create: `memory/scheduler.py`
- Create: `tests/test_scheduler.py`
- Modify: `main.py`

### Step 10.1: Write failing tests

- [ ] **Write tests**

```python
# tests/test_scheduler.py
"""Tests for the background task scheduler (memory/scheduler.py)."""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.scheduler import (
    get_scheduled_tasks,
    is_task_due,
    mark_task_run,
    get_due_tasks,
)


def _setup_scheduler(tmp_path, monkeypatch):
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    monkeypatch.setattr('memory.scheduler.CONFIG_FILE', config_dir / 'scheduled_tasks.json')
    monkeypatch.setattr('memory.scheduler.STATE_FILE', config_dir / 'scheduler_state.json')
    return config_dir


class TestGetScheduledTasks:
    def test_returns_empty_when_no_config(self, tmp_path, monkeypatch):
        """Should return empty list if config file doesn't exist."""
        _setup_scheduler(tmp_path, monkeypatch)
        tasks = get_scheduled_tasks()
        assert tasks == []

    def test_loads_tasks_from_config(self, tmp_path, monkeypatch):
        """Should load task definitions from config file."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {
                "name": "daily_lint",
                "description": "Run vault health check",
                "action": "lint",
                "interval_hours": 24,
                "enabled": True,
            },
            {
                "name": "weekly_reconcile",
                "description": "Reconcile action items",
                "action": "reconcile",
                "interval_hours": 168,
                "enabled": True,
            },
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))

        tasks = get_scheduled_tasks()
        assert len(tasks) == 2
        assert tasks[0]['name'] == 'daily_lint'
        assert tasks[1]['name'] == 'weekly_reconcile'

    def test_skips_disabled_tasks(self, tmp_path, monkeypatch):
        """Disabled tasks should not appear in the list."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {"name": "active", "action": "lint", "interval_hours": 24, "enabled": True},
            {"name": "inactive", "action": "lint", "interval_hours": 24, "enabled": False},
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))

        tasks = get_scheduled_tasks()
        assert len(tasks) == 1
        assert tasks[0]['name'] == 'active'


class TestIsTaskDue:
    def test_never_run_is_due(self, tmp_path, monkeypatch):
        """A task that has never run should be due."""
        _setup_scheduler(tmp_path, monkeypatch)
        task = {"name": "test", "interval_hours": 24}
        assert is_task_due(task) is True

    def test_recently_run_not_due(self, tmp_path, monkeypatch):
        """A task run less than interval_hours ago should not be due."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        task = {"name": "test", "interval_hours": 24}

        # Record a recent run
        recent = datetime.now().isoformat()
        state = {"test": {"last_run": recent}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))

        assert is_task_due(task) is False

    def test_old_run_is_due(self, tmp_path, monkeypatch):
        """A task run more than interval_hours ago should be due."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        task = {"name": "test", "interval_hours": 1}

        # Record an old run (2 hours ago)
        old = (datetime.now() - timedelta(hours=2)).isoformat()
        state = {"test": {"last_run": old}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))

        assert is_task_due(task) is True


class TestMarkTaskRun:
    def test_records_run_time(self, tmp_path, monkeypatch):
        """mark_task_run should record the current time."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        mark_task_run("daily_lint")

        state = json.loads((config_dir / 'scheduler_state.json').read_text())
        assert "daily_lint" in state
        assert "last_run" in state["daily_lint"]

    def test_preserves_other_tasks(self, tmp_path, monkeypatch):
        """Marking one task should not affect other tasks' state."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        old_time = datetime.now().isoformat()
        state = {"other_task": {"last_run": old_time}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))

        mark_task_run("new_task")

        loaded = json.loads((config_dir / 'scheduler_state.json').read_text())
        assert "other_task" in loaded
        assert "new_task" in loaded
        assert loaded["other_task"]["last_run"] == old_time


class TestGetDueTasks:
    def test_returns_only_due_tasks(self, tmp_path, monkeypatch):
        """Should return only tasks that are due based on interval."""
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {"name": "due_task", "action": "lint", "interval_hours": 1, "enabled": True},
            {"name": "not_due", "action": "reconcile", "interval_hours": 24, "enabled": True},
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))

        # Mark not_due as recently run
        recent = datetime.now().isoformat()
        state = {"not_due": {"last_run": recent}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))

        due = get_due_tasks()
        assert len(due) == 1
        assert due[0]['name'] == 'due_task'
```

- [ ] **Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 10.2: Implement the scheduler

- [ ] **Create `memory/scheduler.py`**

```python
# memory/scheduler.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Lightweight task scheduler for background vault maintenance.
# Tasks are defined in config/scheduled_tasks.json and run via
# `python main.py --run-scheduled`.
#
# This is NOT an always-running daemon — it's designed to be invoked
# by an OS-level scheduler (cron on Linux/Mac, Task Scheduler on Windows).
# Each invocation checks which tasks are due and runs them.
# ============================================================================

import json
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_FILE = Path('config') / 'scheduled_tasks.json'
STATE_FILE = Path('config') / 'scheduler_state.json'


def get_scheduled_tasks() -> list[dict]:
    """
    Load enabled task definitions from config file.

    Config format:
    [
        {
            "name": "daily_lint",
            "description": "Run vault health check",
            "action": "lint",
            "interval_hours": 24,
            "enabled": true
        }
    ]

    Returns only enabled tasks.
    """
    if not CONFIG_FILE.exists():
        return []

    try:
        tasks = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return []

    return [t for t in tasks if t.get('enabled', True)]


def _load_state() -> dict:
    """Load scheduler state (last run times)."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict):
    """Save scheduler state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def is_task_due(task: dict) -> bool:
    """
    Check if a task should run based on its interval and last run time.

    Args:
        task: Task definition dict with 'name' and 'interval_hours'

    Returns:
        True if the task has never run or was last run more than
        interval_hours ago.
    """
    state = _load_state()
    task_state = state.get(task['name'], {})
    last_run = task_state.get('last_run')

    if not last_run:
        return True

    try:
        last_run_dt = datetime.fromisoformat(last_run)
    except (ValueError, TypeError):
        return True

    interval = timedelta(hours=task.get('interval_hours', 24))
    return datetime.now() - last_run_dt >= interval


def mark_task_run(task_name: str):
    """Record that a task was just run."""
    state = _load_state()
    state[task_name] = {
        'last_run': datetime.now().isoformat(),
    }
    _save_state(state)


def get_due_tasks() -> list[dict]:
    """Get all enabled tasks that are due to run."""
    tasks = get_scheduled_tasks()
    return [t for t in tasks if is_task_due(t)]
```

- [ ] **Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: ALL PASS

### Step 10.3: Wire scheduler into main.py

- [ ] **Read current `main.py`** and add `--run-scheduled` flag

Add after the existing argparse setup:

```python
parser.add_argument('--run-scheduled', action='store_true',
                    help='Run any due scheduled tasks and exit')
```

Add the handler before `uvicorn.run()`:

```python
if args.run_scheduled:
    from memory.scheduler import get_due_tasks, mark_task_run
    from orchestrator import Orchestrator

    orch = Orchestrator()
    due = get_due_tasks()

    if not due:
        print("No scheduled tasks are due.")
    else:
        for task in due:
            print(f"Running scheduled task: {task['name']} ({task.get('description', '')})")
            action = task.get('action', '')

            if action == 'lint':
                result = orch.lint_vault()
            elif action == 'reconcile':
                result = orch.reconcile_actions("Scheduled reconciliation")
            elif action == 'insights':
                result = orch.generate_insights("Scheduled insights generation")
            elif action == 'refresh_actions':
                result = orch.refresh_actions("Scheduled action refresh")
            elif action == 'build':
                result = orch.build_memory("Scheduled build")
            else:
                print(f"  Unknown action: {action}")
                continue

            mark_task_run(task['name'])
            print(f"  Done: {result[:200]}...")

    sys.exit(0)
```

- [ ] **Create example config file** `config/scheduled_tasks.example.json`:

```json
[
    {
        "name": "daily_lint",
        "description": "Run vault health check daily",
        "action": "lint",
        "interval_hours": 24,
        "enabled": true
    },
    {
        "name": "daily_reconcile",
        "description": "Reconcile action items against sent emails",
        "action": "reconcile",
        "interval_hours": 24,
        "enabled": true
    },
    {
        "name": "weekly_insights",
        "description": "Generate cross-correlation insights weekly",
        "action": "insights",
        "interval_hours": 168,
        "enabled": true
    }
]
```

- [ ] **Run all tests**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: ALL PASS

- [ ] **Commit**

```bash
git add memory/scheduler.py tests/test_scheduler.py main.py config/scheduled_tasks.example.json
git commit -m "feat: add background task scheduler with CLI runner"
```

---

## Task 11: Final Verification + Documentation

### Step 11.1: Run the complete test suite

- [ ] **Run all new tests**

Run: `python -m pytest tests/test_organizations.py tests/test_projects.py tests/test_knowledge_index.py tests/test_vault_lint.py tests/test_change_detection.py tests/test_scheduler.py -v`
Expected: ALL PASS

- [ ] **Run the full test suite for regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS (excluding the pre-existing dedup test failure)

### Step 11.2: Verify all imports

- [ ] **Smoke test**

Run: `python -c "from memory.vault import MEMORY_TYPES; assert 'organizations' in MEMORY_TYPES; assert 'projects' in MEMORY_TYPES; from memory.vault_lint import run_lint_checks; from memory.change_detection import scan_vault_state, detect_changes; from memory.scheduler import get_due_tasks; print('All imports OK')"`
Expected: `All imports OK`

### Step 11.3: Update documentation

- [ ] **Invoke `/documenter` skill** to update roadmap and living docs

### Step 11.4: Final commit if needed

- [ ] **Check for uncommitted changes**

Run: `git status`
