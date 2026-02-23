# UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite web/static/index.html from dark tab-based layout to warm Aura-style sidebar interface with full zen effects.

**Architecture:** Single-file rewrite. Dark collapsible sidebar (nav) + white main content area. Four pages: Home (build pipeline), Chat (query), Vault (browser), Profile (new). All existing JS functionality preserved, adapted to new DOM structure. All existing API endpoints unchanged.

**Tech Stack:** HTML5, CSS3 (custom properties), vanilla JS, Google Fonts (Literata + DM Sans + JetBrains Mono)

---

### Task 1: CSS Foundation + App Shell
- Design tokens (full Aura palette)
- Reset, body, app shell layout (.app flex, .app-nav, .main-content)

### Task 2: Sidebar Navigation
- Brand mark, nav items (Home, Chat, Vault), collapse button
- Profile footer, SVG icons, active/hover states
- toggleNav() and navigateTo() JS

### Task 3: Home Page (was Build)
- Auth banner (warm styled)
- Build config card (3-col grid: days, max, filter)
- Sage green build button with shimmer
- Pipeline log with staggered entries
- Port: checkAuthStatus, connectGmail, startBuild, addLogEntry, finishBuild

### Task 4: Chat Page (was Query)
- Welcome orb + greeting + suggestion chips
- Message bubbles with avatars (sage assistant, warm user)
- Typing indicator (3 bouncing dots)
- Pill input with textarea + sage send button
- Ambient radial gradients
- Port: sendMessage, addChatMessage, addChatLoadingMessage, renderFormattedText, askSuggestion

### Task 5: Vault Browser
- Stats grid (staggered entrance)
- Three-pane layout (categories, file list, preview)
- Warm surfaces, sage active states, hover lifts
- Port: loadVaultData, loadStats, loadMemories, filterByType, renderMemoryList, openMemory, renderMarkdown

### Task 6: Profile Page (new)
- Large avatar + name header
- About You card (summary from vault or placeholder)
- Vault Overview card (memory counts from /api/stats)
- Connection card (Gmail status from /api/auth/status)

### Task 7: Zen Animations + Polish
- All 9 keyframe animations (orbFloat, breathe, welcomeIn, messageIn, typingBounce, navIn, contentIn, pageElementIn, statCardIn)
- Ambient gradients on chat
- Hover micro-interactions
- prefers-reduced-motion
- Responsive breakpoints (900px, 600px)

### Task 8: Final Integration
- Full JS audit (all functions work with new DOM)
- API endpoint cross-reference
- End-to-end walkthrough
