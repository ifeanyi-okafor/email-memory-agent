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
- [ ] 3.2 Memory deduplication and merging within vault
- [x] 3.3 Bidirectional knowledge graph (`_graph.json`) with wiki-link resolution
- [x] 3.4 New memory type: `action_required` with Eisenhower matrix prioritization
- [x] 3.5 Action Agent — scans vault + graph, generates prioritized action items
- [x] 3.6 Multi-provider LLM support (OpenRouter primary, Anthropic fallback)
- [x] 3.7 Action Required vault tab with status badges and filter toggles
- [x] 3.8 Reconciliation Agent (compare action items vs sent emails → Active/Closed/Expired)
- [ ] 3.9 Memory confidence scoring and source attribution
- [ ] 3.10 Query Agent context window optimization

## Phase 4: Polish & Deployment
Production hardening, performance, and deployment.

- [ ] 4.1 Rate limiting and error recovery improvements
- [ ] 4.2 Multi-user support (separate vaults per account)
- [ ] 4.3 Docker containerization
- [ ] 4.4 Vault export/import (JSON, markdown zip)
- [ ] 4.5 Background scheduled syncs
- [ ] 4.6 Performance profiling and optimization
