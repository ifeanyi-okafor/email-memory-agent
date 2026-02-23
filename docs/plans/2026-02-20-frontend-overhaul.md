# Frontend Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 20-line `web/static/index.html` stub with a full production frontend adopting the Aura "Elevated Zen" design system, wired to all backend API endpoints.

**Architecture:** Single HTML file with inline CSS and JS. Four navigable pages (Home, Chat, Vault, Profile) controlled by vanilla JS show/hide. Real API integration via fetch + EventSource (SSE). No build tools, no framework.

**Tech Stack:** HTML5, CSS3 (custom properties, animations, grid, backdrop-filter), vanilla JavaScript (ES6+), Google Fonts (Literata, DM Sans, JetBrains Mono)

---

## Reference Files

- **Design spec:** `docs/plans/2026-02-20-frontend-overhaul-design.md`
- **Sample reference:** `assets/sample.html` (Aura design, 1618 lines)
- **Backend API:** `web/app.py` (FastAPI, 382 lines)
- **Vault data shapes:** `memory/vault.py` (return types for list_memories, search_vault, read_memory, get_vault_stats)
- **Target file:** `web/static/index.html`

## API Contracts (from web/app.py + vault.py)

```
GET  /api/stats          → { total: int, by_type: { decisions: int, people: int, commitments: int } }
GET  /api/memories       → { memories: [{ filepath, type, title, date, priority, tags }], count: int }
GET  /api/memories?memory_type=people → same, filtered
GET  /api/memory/{type}/{filename} → { frontmatter: {...}, content: str, filepath: str }
GET  /api/search?q=text  → { results: [{ filepath, type, title, snippet, priority }], count: int }
POST /api/query          → body: { question: str } → { answer: str }
GET  /api/auth/status    → { authenticated: bool, credentials_exist: bool }
POST /api/auth/google    → { status: str, message: str }
GET  /api/stream/build?days_back=30&max_emails=50&gmail_query= → SSE stream:
     data: { stage, status, message, ... }  (repeats)
     data: { stage: "complete", stats: {...} }  (final)
```

---

### Task 1: CSS Design System + Base Layout

**Files:**
- Create: `web/static/index.html` (overwrite the 20-line stub)

**What:** Write the `<head>`, CSS custom properties (from design spec), reset styles, typography, base layout (`.app` flex shell), and all keyframe animations. This is the foundation everything else builds on.

**CSS sections to include:**
1. Design tokens (`:root` variables) — copy palette from design spec, add noise texture
2. Reset (`*`, `html, body`)
3. App shell (`.app` flex container)
4. Left nav styles (`.app-nav`, collapse, brand, items, footer) — port from sample.html
5. Main content area (`.main-content`, border-radius, shadow)
6. Keyframe animations: `navIn`, `contentIn`, `orbFloat`, `welcomeIn`, `breathe`, `typingBounce`, `messageIn`, `pageElementIn`
7. Responsive breakpoint (`@media max-width: 900px`)

**Step 1:** Write the full `<!DOCTYPE html>`, `<head>` with meta tags + font links, opening `<style>` tag, and all CSS through the responsive breakpoint. Close `</style>` and `</head>`.

**Step 2:** Verify: Open the file in browser. Should show a blank page with correct background color (#FAF8F5). Check DevTools — all CSS variables should be defined on `:root`.

**Commit:** `feat: add CSS design system and base layout styles`

---

### Task 2: HTML Shell — Sidebar Navigation

**Files:**
- Modify: `web/static/index.html` (append to `<body>`)

**What:** Write the `<body>` with the app shell div, the dark sidebar nav with 4 nav items (Home, Chat, Vault, Profile), collapse button, brand mark, and profile footer. Port SVG icons from sample.html, adapt labels.

**HTML structure:**
```
<div class="app">
  <nav class="app-nav" id="appNav">
    <button class="nav-collapse-btn">...</button>
    <div class="nav-brand">...</div>
    <div class="nav-items">
      <a data-page="home">Home</a>
      <a data-page="chat" class="active">Chat</a>
      <a data-page="vault">Vault</a>
      <a data-page="profile">Profile</a>
    </div>
    <div class="nav-footer">...</div>
  </nav>
  <div class="main-content" id="mainContent">
    <!-- pages go here in later tasks -->
  </div>
</div>
```

**Step 1:** Write the sidebar HTML with all SVG icons. Use appropriate icons: dashboard circle for Home, chat bubble for Chat, grid/folder for Vault, user circle for Profile.

**Step 2:** Add the `toggleNav()` JavaScript function at bottom of file in a `<script>` tag.

**Step 3:** Verify: sidebar renders with dark background, brand mark, 4 nav items, profile footer. Collapse button works (toggles width). Check hover states.

**Commit:** `feat: add sidebar navigation with collapse`

---

### Task 3: Page Infrastructure + Navigation JS

**Files:**
- Modify: `web/static/index.html`

**What:** Add empty page-view divs for all 4 pages inside `.main-content`, plus the `navigateTo()` function that shows/hides pages and updates nav active state. The Chat page gets a special `chatView` wrapper (it has a sub-panel unlike other pages).

**HTML to add inside `.main-content`:**
```html
<div class="page-view" id="page-home"></div>
<div class="page-view" id="page-vault"></div>
<div class="page-view" id="page-profile"></div>
<div id="chatView" style="display:flex; flex:1; min-width:0;">
  <!-- chat panel + chat main go here -->
</div>
```

**JavaScript:**
- `navigateTo(page)` — hide all `.page-view`, hide chatView, toggle active nav item, show selected page. Re-trigger stagger animations on page children.
- Wire nav item `onclick` handlers.
- Default: `navigateTo('chat')` on page load.

**Step:** Write the page view divs (empty for now) and navigation JS. Verify clicking nav items switches pages (they'll be blank, but only one should be visible at a time).

**Commit:** `feat: add page navigation infrastructure`

---

### Task 4: Chat Page — Full Implementation

**Files:**
- Modify: `web/static/index.html`

**What:** This is the core experience. Build the chat UI inside `chatView`: conversation history panel (left), main chat area (right) with welcome state, message rendering, typing indicator, input area. Wire to `POST /api/query`.

**CSS to add:** Chat panel styles, chat header, messages, welcome state, suggestion chips, input area, typing indicator, message actions. Port from sample.html sections.

**HTML structure inside chatView:**
```
<div class="chat-panel" id="chatPanel">
  <div class="panel-header">Conversations</div>
  <button class="new-chat-btn">New conversation</button>
  <div class="chat-list" id="chatList"></div>
</div>
<div class="chat-main">
  <div class="chat-header">
    <div class="header-left">
      <button class="panel-open-btn">...</button>
      <div class="assistant-presence">...</div>
      <div class="header-info">
        <h2>Memory Vault</h2>
        <p>Ask about your memories</p>
      </div>
    </div>
    <div class="header-actions">...</div>
  </div>
  <div class="messages-container" id="messagesContainer">
    <div class="welcome" id="welcomeState">
      <div class="welcome-orb"></div>
      <h1>Your Memory Vault</h1>
      <p>Ask me anything about your emails...</p>
      <div class="suggestions">
        <button class="suggestion-chip">What decisions have I made?</button>
        <button class="suggestion-chip">Who do I communicate with?</button>
        <button class="suggestion-chip">What are my commitments?</button>
        <button class="suggestion-chip">Summarize my vault</button>
      </div>
    </div>
  </div>
  <div class="input-area">
    <div class="input-wrapper">
      <textarea id="messageInput" placeholder="Ask about your memories..."></textarea>
      <div class="input-actions">
        <button class="send-btn" id="sendBtn">...</button>
      </div>
    </div>
    <div class="input-hint">Answers are synthesized from your memory vault</div>
  </div>
</div>
```

**JavaScript functions:**
- `sendMessage()` — get input, display user bubble, show typing indicator, call `POST /api/query`, display response
- `addUserMessage(text)` — create user message-group DOM element
- `addAssistantMessage(text)` — create assistant message-group with copy button
- `showTyping()` / `hideTyping()` — typing indicator management
- `sendSuggestion(chip)` — populate input from chip text and send
- `autoResize(textarea)` — auto-grow input
- `handleKey(event)` — Enter to send, Shift+Enter for newline
- `scrollBottom()` — smooth scroll to latest message
- `esc(text)` — HTML-escape user input (XSS prevention)
- `togglePanel()` — show/hide conversation panel
- `getTime()` — format current time for message timestamps
- Conversation history in `sessionStorage`: save/load chat list in left panel
- `copyMessage(btn)` — copy assistant message text to clipboard

**API integration:**
```javascript
async function queryVault(question) {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  });
  const data = await res.json();
  return data.answer;
}
```

**Step 1:** Write all chat CSS (port from sample.html, adapt).

**Step 2:** Write chat HTML structure.

**Step 3:** Write all chat JavaScript functions + API integration.

**Step 4:** Verify: type a message, see user bubble appear, typing indicator shows, API call fires (may fail if no vault data — that's OK, check network tab), response displays.

**Commit:** `feat: add chat page with vault query integration`

---

### Task 5: Home Page — Stats + Quick Actions

**Files:**
- Modify: `web/static/index.html`

**What:** Populate the Home page with a welcome greeting, stats grid (3 cards from `/api/stats`), quick action links, and recent memories list (from `/api/memories`).

**CSS to add:** Stats grid, stat cards, page cards, card rows (port from sample.html).

**HTML inside `#page-home`:**
```html
<h1>Welcome to Memory Vault</h1>
<p class="page-subtitle">Here's a snapshot of your memory</p>
<div class="stats-grid" id="statsGrid">
  <div class="stat-card"><div class="stat-value" id="statTotal">—</div><div class="stat-label">Total Memories</div></div>
  <div class="stat-card"><div class="stat-value" id="statPeople">—</div><div class="stat-label">People</div></div>
  <div class="stat-card"><div class="stat-value" id="statDecisions">—</div><div class="stat-label">Decisions</div></div>
</div>
<div class="page-card">
  <h3>Quick Actions</h3>
  <div class="card-row" onclick="navigateTo('profile')">
    <span class="card-row-label">Build memory from emails</span>
    <span class="card-row-value">→</span>
  </div>
  <div class="card-row" onclick="navigateTo('chat')">
    <span class="card-row-label">Ask a question</span>
    <span class="card-row-value">→</span>
  </div>
  <div class="card-row" onclick="navigateTo('vault')">
    <span class="card-row-label">Browse vault</span>
    <span class="card-row-value">→</span>
  </div>
</div>
<div class="page-card">
  <h3>Recent Memories</h3>
  <div id="recentMemories"><p style="color:var(--text-tertiary);font-size:13px;">Loading...</p></div>
</div>
```

**JavaScript:**
- `loadHomeData()` — fetch `/api/stats` and `/api/memories`, populate stats cards and recent list
- Call `loadHomeData()` inside `navigateTo('home')` (lazy load on page visit)

**Step 1:** Write home page CSS + HTML + JS.

**Step 2:** Verify: navigate to Home, stats cards populate (or show 0 if vault empty), recent memories list renders.

**Commit:** `feat: add home page with stats and recent memories`

---

### Task 6: Vault Page — Browse + Search Memories

**Files:**
- Modify: `web/static/index.html`

**What:** Build the vault browser with search bar, type filter chips, responsive card grid, and expandable memory detail view.

**CSS to add:** Vault-specific styles — search bar, filter chips, memory card grid, memory detail overlay/expansion, type badge colors.

**HTML inside `#page-vault`:**
```html
<h1>Memory Vault</h1>
<p class="page-subtitle">Browse and search your memories</p>
<div class="vault-search-bar">
  <input type="text" id="vaultSearch" placeholder="Search memories...">
</div>
<div class="vault-filters" id="vaultFilters">
  <button class="filter-chip active" data-type="all">All</button>
  <button class="filter-chip" data-type="decisions">Decisions</button>
  <button class="filter-chip" data-type="people">People</button>
  <button class="filter-chip" data-type="commitments">Commitments</button>
</div>
<div class="vault-grid" id="vaultGrid">
  <p style="color:var(--text-tertiary)">Loading memories...</p>
</div>
<div class="memory-detail-overlay" id="memoryOverlay" style="display:none;">
  <div class="memory-detail-panel" id="memoryDetail"></div>
</div>
```

**JavaScript:**
- `loadVaultData(type)` — fetch `/api/memories?memory_type=X` (or all), render card grid
- `searchVault(query)` — debounced fetch to `/api/search?q=X`, render results
- `renderMemoryCards(memories)` — create card elements with type badge, title, date, tags
- `openMemoryDetail(type, filename)` — fetch `/api/memory/{type}/{filename}`, show overlay with frontmatter + content
- `closeMemoryDetail()` — hide overlay
- Filter chip click handlers — toggle active, call `loadVaultData(type)`
- Search input `oninput` with 300ms debounce

**Memory card HTML template:**
```html
<div class="memory-card" onclick="openMemoryDetail('people','sarah-chen-a1b2.md')">
  <span class="type-badge people">People</span>
  <h4>Sarah Chen — CTO at Acme</h4>
  <span class="memory-date">2026-02-19</span>
  <div class="memory-tags"><span class="tag">work</span><span class="tag">contact</span></div>
</div>
```

**Step 1:** Write vault CSS (search bar, filter chips, card grid, detail overlay).

**Step 2:** Write vault HTML structure.

**Step 3:** Write vault JavaScript (load, search, render, detail view).

**Step 4:** Verify: navigate to Vault, cards render (or empty state), search filters, clicking card opens detail.

**Commit:** `feat: add vault browser with search and detail view`

---

### Task 7: Profile Page — Auth + Build Pipeline

**Files:**
- Modify: `web/static/index.html`

**What:** Build the Profile page with Gmail connection status, build memory controls with SSE progress visualization, and vault stats summary.

**CSS to add:** Connection status card, build controls, progress visualization (orbital ring or staged progress bar), stage indicators.

**HTML inside `#page-profile`:**
```html
<h1>Profile</h1>
<p class="page-subtitle">Manage your connections and memory pipeline</p>

<!-- Gmail Connection -->
<div class="page-card" id="authCard">
  <h3>Gmail Connection</h3>
  <div class="card-row">
    <span class="card-row-label">Status</span>
    <span class="card-row-value" id="authStatus">Checking...</span>
  </div>
  <div id="authAction"></div>
</div>

<!-- Build Memory -->
<div class="page-card">
  <h3>Build Memory</h3>
  <p style="color:var(--text-secondary);font-size:13px;margin-bottom:16px;">
    Scan your Gmail and extract memories into the vault.
  </p>
  <div class="build-controls">
    <label>Days back: <input type="number" id="buildDays" value="30" min="1" max="365"></label>
    <label>Max emails: <input type="number" id="buildMax" value="50" min="1" max="500"></label>
    <label>Gmail filter: <input type="text" id="buildQuery" placeholder="e.g. from:boss@company.com"></label>
  </div>
  <button class="build-btn" id="buildBtn" onclick="startBuild()">Build Memory</button>
  <div class="build-progress" id="buildProgress" style="display:none;">
    <div class="progress-stages" id="progressStages"></div>
    <div class="progress-message" id="progressMessage"></div>
  </div>
</div>

<!-- Vault Stats -->
<div class="page-card">
  <h3>Vault Summary</h3>
  <div id="profileStats"><p style="color:var(--text-tertiary);font-size:13px;">Loading...</p></div>
</div>
```

**JavaScript:**
- `checkAuthStatus()` — fetch `/api/auth/status`, update badge + show/hide connect button
- `connectGmail()` — POST `/api/auth/google`, show result, re-check status
- `startBuild()` — read control values, connect to `EventSource(/api/stream/build?...)`, render progress
- `handleBuildEvent(event)` — parse SSE data, update stage indicators and message
- `loadProfileStats()` — fetch `/api/stats`, render in profile stats card

**SSE integration:**
```javascript
function startBuild() {
  const days = document.getElementById('buildDays').value;
  const max = document.getElementById('buildMax').value;
  const query = document.getElementById('buildQuery').value;

  const url = `/api/stream/build?days_back=${days}&max_emails=${max}&gmail_query=${encodeURIComponent(query)}`;
  const source = new EventSource(url);

  buildBtn.disabled = true;
  buildProgress.style.display = 'block';

  source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleBuildEvent(event);
    if (event.stage === 'complete' || event.stage === 'error') {
      source.close();
      buildBtn.disabled = false;
    }
  };

  source.onerror = () => {
    source.close();
    buildBtn.disabled = false;
    progressMessage.textContent = 'Connection lost. Check server logs.';
  };
}
```

**Step 1:** Write profile CSS (auth card, build controls, progress stages).

**Step 2:** Write profile HTML structure.

**Step 3:** Write profile JavaScript (auth check, Gmail connect, build pipeline SSE, stats).

**Step 4:** Verify: Profile page shows auth status (check network tab), build button connects SSE (may need Gmail setup to fully test), stats card populates.

**Commit:** `feat: add profile page with auth and build pipeline`

---

### Task 8: Polish — Zen Details + Page Load Integration

**Files:**
- Modify: `web/static/index.html`

**What:** Add the atmospheric zen details (noise texture, ambient gradients, glass header effects), wire up on-load data fetching, add empty states, error handling for API failures, and final responsive tweaks.

**Specific additions:**
1. CSS noise texture overlay on `.main-content` using a tiny inline SVG data URI
2. Ambient radial gradients on `.chat-main::before` (already in sample.html, verify it's included)
3. Verify glass-morphism header (`backdrop-filter: blur(12px)`)
4. Add empty state messages for vault (no memories yet), chat (welcome state), home (no data)
5. Add error handling: if `fetch()` fails, show user-friendly error in the relevant section
6. Add `window.onload` that calls `checkAuthStatus()` and optionally pre-loads stats
7. Verify all animations play correctly (page transitions, message slide-ins, orb float)
8. Test responsive: at < 900px, sidebar collapses, chat panel hides

**Step 1:** Add noise texture CSS and verify ambient gradient is present.

**Step 2:** Add empty states and error handling to all API-calling functions.

**Step 3:** Wire `window.onload` initialization.

**Step 4:** Full manual test: open browser, check all 4 pages load, type a chat message, browse vault, check profile auth, verify animations.

**Commit:** `feat: add zen polish, error handling, and initialization`

---

### Task 9: Final Verification

**Files:** None (read-only)

**What:** Complete end-to-end walkthrough of the frontend.

**Checklist:**
- [ ] `python main.py` starts without errors
- [ ] `http://localhost:8000` loads the frontend
- [ ] Sidebar renders with dark bg, 4 nav items, collapse works
- [ ] Home page: stats load (or show 0), quick actions navigate correctly
- [ ] Chat page: welcome state shows, suggestion chips work, typing a message calls `/api/query`, response renders
- [ ] Vault page: memories load (or empty state), search bar filters, clicking card opens detail
- [ ] Profile page: auth status shows, build button triggers SSE stream, progress updates render
- [ ] Responsive: at narrow width, sidebar collapses, chat panel hides
- [ ] Animations: page transitions stagger, messages slide in, orb floats, typing dots bounce
- [ ] No console errors in DevTools
