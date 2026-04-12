# Email Memory Agent — Roadmap

## Phase 1: Core Pipeline
Build the end-to-end email-to-memory pipeline with CLI and basic web UI.

- [x] 1.1 Gmail OAuth integration (read-only scope)
- [x] 1.2 MCP server for Gmail (fetch_emails tool)
- [x] 1.3 MCP server for memory vault (read/write/search tools)
- [x] 1.4 Email Reader Agent (analyze emails, produce observations)
- [x] 1.5 Memory Writer Agent (create structured vault files)
- [x] 1.6 Query Agent (search vault, answer questions)
- [x] 1.7 Orchestrator with keyword routing (build/query/stats)
- [x] 1.8 FastAPI web server with SSE streaming
- [x] 1.9 Browser chat UI (single-page app)

✅ Completed [2026-02-20]

## Phase 2: Frontend Overhaul & Auth UX
Redesign the UI with a polished aesthetic, add login/logout flow, and incremental processing.

- [x] 2.1 "Elevated Zen" UI redesign (sage/warm palette, Literata + DM Sans fonts)
- [x] 2.2 Sidebar navigation (Home, Chat, Vault, collapsible)
- [x] 2.3 Three-column vault browser (types → files → content)
- [x] 2.4 Conversations panel with session storage
- [x] 2.5 Font Awesome icon migration (18 SVG → FA icons)
- [x] 2.6 Login page with Google sign-in (auth gate)
- [x] 2.7 Logout endpoint and top-bar logout button
- [x] 2.8 User info endpoint (sidebar/header email display)
- [x] 2.9 Incremental email processing (skip already-processed IDs)
- [x] 2.10 Auto-build on login with dual progress indicators (sidebar + home)
- [x] 2.11 Sidebar reorganization (Profile in footer, build indicator above profile)
- [x] 2.12 107 frontend tests (JSDOM + Jest)

✅ Completed [2026-02-22]

## Phase 3: Intelligence & Quality
Improve agent intelligence, vault quality, and add new memory types.

- [ ] 3.1 LLM-based intent classification (replace keyword routing)
- [x] 3.2 Memory deduplication and merging within vault
- [x] 3.3 Bidirectional knowledge graph (`_graph.json`) with wiki-link resolution
- [x] 3.4 New memory type: `action_required` with Eisenhower matrix prioritization
- [x] 3.5 Action Agent — scans vault + graph, generates prioritized action items
- [x] 3.6 Multi-provider LLM support (OpenRouter primary, Anthropic fallback)
- [x] 3.7 Action Required vault tab with status badges and filter toggles
- [x] 3.8 Reconciliation Agent (compare action items vs sent emails → Active/Closed/Expired)
- [x] 3.9 Commitment status property (invited/confirmed/declined/tentative lifecycle tracking)
- [x] 3.10 Eisenhower matrix UI (clickable 2x2 quadrant grid with live counts and filtering)
- [x] 3.11 Vault UI polish (premium Eisenhower matrix, semantic status badges, category icon chips, stagger animations, enhanced content viewer)
- [x] 3.12 Insights Agent — cross-correlates vault to discover relationships, execution gaps, strategic patterns
- [x] 3.13 Person deduplication with name-only enforcement (strip titles/roles/orgs from names)
- [x] 3.14 Section-based content merge (holistic update instead of blind append, idempotent)
- [x] 3.15 Append-only vault changelog for audit trail (`memory/changelog.py`)
- [x] 3.16 Knowledge Index — pre-built entity catalog injected into MemoryWriter prompt for entity resolution (`memory/knowledge_index.py`)
- [x] 3.17 Email noise filter — heuristic classifier skips newsletters/receipts/notifications before LLM processing (`tools/email_filter.py`)
- [x] 3.18 Knowledge Index wired into build pipeline (orchestrator builds index, injects into MemoryWriter prompt)
- [x] 3.19 Email noise filter wired into build pipeline (filter between fetch and batch analyze)
- [x] 3.20 Organizations as first-class entity type (domain, industry, relationship_type frontmatter)
- [x] 3.21 Projects as first-class entity type (project_status, project_type frontmatter)
- [x] 3.22 Vault Lint Agent — detects stale action items, orphaned files, and empty content
- [x] 3.23 File change detection with SHA-256 hashing (`memory/change_detection.py`)
- [x] 3.24 Background task scheduler with CLI runner (`memory/scheduler.py`, `--run-scheduled` flag)
- [ ] 3.25 Memory confidence scoring and source attribution
- [ ] 3.26 Query Agent context window optimization

## Phase 4: Polish & Deployment
Production hardening, performance, and deployment.

- [x] 4.1 Build state persistence (page refresh reconnects to running build, not restart)
- [x] 4.2 Incremental email ingestion (scan IDs first, fetch only new emails — 97% API call reduction)
- [ ] 4.3 Rate limiting and error recovery improvements
- [ ] 4.4 Multi-user support (separate vaults per account)
- [ ] 4.5 Docker containerization
- [ ] 4.6 Vault export/import (JSON, markdown zip)
- [ ] 4.7 Background scheduled syncs
- [ ] 4.8 Performance profiling and optimization
