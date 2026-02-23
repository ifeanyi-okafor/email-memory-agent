# Frontend Overhaul Design: Elevated Zen

**Date**: 2026-02-20
**Status**: Approved

## Overview

Overhaul `web/static/index.html` from a 20-line stub into a full production frontend for the Email Memory Agent. Adopt the Aura design language from `assets/sample.html`, elevate it with zen-inspired animations and atmospheric details, and wire it to all 7 backend API endpoints.

Single HTML file. No framework. Vanilla JS + CSS custom properties.

## Design System

### Palette
- Primary bg: `#FAF8F5` (warm cream) with CSS noise texture
- Secondary bg: `#F3F0EB`, surface: `#F0EDE8`
- Dark sidebar: `#36332E`
- Sage accents: `#7B9E87` (primary), `#5C8068` (deep), `#A8C5B2` (soft)
- Warm accent: `#C4956A` (badges, alerts)
- Glass header: `rgba(255,255,255,0.85)` + `backdrop-filter: blur(12px)`

### Typography
- **Literata** (variable, optical sizing) — headings, assistant messages
- **DM Sans** — body, nav, buttons, user messages
- **JetBrains Mono** — stats, vault metadata, tags

### Motion
- Page transitions: staggered `translateY(12px)` fade-up (0.1s delay between children)
- Messages: spring-eased slide-in (`cubic-bezier(0.34, 1.56, 0.64, 1)`)
- Welcome orb: continuous float + rotate (6s cycle)
- Presence dot: breathing pulse (3s cycle)
- Input focus: sage glow ring expansion
- Build progress: orbital ring animation
- Card hover: `translateY(-2px)` lift

## Navigation

Collapsible dark sidebar (220px expanded, 68px collapsed):

| Label | Page | Backend Mapping |
|-------|------|-----------------|
| Home | Stats + quick actions | `GET /api/stats` |
| Chat | Query vault via conversation | `POST /api/query` |
| Vault | Browse + search memories | `GET /api/memories`, `/api/search`, `/api/memory/` |
| Profile | Gmail auth + build pipeline | `GET /api/auth/status`, `POST /api/auth/google`, `GET /api/stream/build` |

## Pages

### Home
- Welcome greeting (Literata)
- Stats grid (3 cards): total memories, types breakdown, categories
- Quick actions: "Build Memory" link, "Ask a Question" link
- Recent memories list (last 5)

### Chat
- Left panel: conversation history (sessionStorage)
- Welcome state: floating orb + suggestion chips
- Message bubbles: user (sage bg, right) + assistant (cream bg, left with avatar)
- Typing indicator: 3 bouncing dots
- Copy button on assistant messages
- Auto-resizing textarea + sage send button
- Backend: `POST /api/query`

### Vault
- Search bar with live filtering (debounced `GET /api/search`)
- Filter chips: All | per memory type
- Responsive card grid (`auto-fill, minmax(280px, 1fr)`)
- Cards: type badge, title, date, preview, tags
- Click to expand: full frontmatter + markdown content
- Backend: `GET /api/memories`, `GET /api/memory/{type}/{filename}`

### Profile
- Gmail connection card with status badge + connect button
- Build memory card with controls (days back, max emails, query)
- SSE progress visualization (stage indicators, live count)
- Vault stats card
- Backend: `GET /api/auth/status`, `POST /api/auth/google`, `GET /api/stream/build`

## Zen Details
- CSS noise texture overlay on main content
- Ambient radial gradients (sage + warm, different corners)
- Glass-morphism header with backdrop blur
- Spring-based easing curves
- Breathing animations on idle elements
- Generous whitespace throughout
