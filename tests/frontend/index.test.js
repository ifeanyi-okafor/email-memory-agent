/**
 * Comprehensive frontend tests for Email Memory Agent
 * Covers: Home, Chat, Vault, Profile pages
 * Plus: navigation, API integrations, sessionStorage, XSS prevention, responsive behavior
 */

const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(__dirname, '..', '..', 'web', 'static', 'index.html');
const rawHtml = fs.readFileSync(HTML_PATH, 'utf8');

const flush = () => new Promise(r => setTimeout(r, 0));

function parseHtml(html) {
    const scriptTag = '<script>';
    const scriptEndTag = '</script>';
    const start = html.indexOf(scriptTag);
    const end = html.indexOf(scriptEndTag, start);
    if (start === -1 || end === -1) return { htmlOnly: html, scriptContent: '' };
    return {
        htmlOnly: html.slice(0, start) + html.slice(end + scriptEndTag.length),
        scriptContent: html.slice(start + scriptTag.length, end),
    };
}

function createEnv(fetchOverrides = {}) {
    const { htmlOnly, scriptContent } = parseHtml(rawHtml);

    const dom = new JSDOM(htmlOnly, {
        url: 'http://localhost:8000',
        runScripts: 'dangerously',
        pretendToBeVisual: true,
    });

    const win = dom.window;
    const doc = win.document;

    const responses = {
        '/api/auth/status': { authenticated: false, credentials_exist: false },
        '/api/stats': { total: 0, by_type: {} },
        '/api/memories': { memories: [] },
        '/api/query': { answer: 'Test answer from vault' },
        '/api/search': { results: [] },
        ...fetchOverrides,
    };

    const fetchMock = jest.fn((url) => {
        const urlStr = String(url);
        for (const [key, data] of Object.entries(responses)) {
            if (urlStr.includes(key)) {
                return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
            }
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    win.fetch = fetchMock;

    win.navigator.clipboard = { writeText: jest.fn().mockResolvedValue(undefined) };

    const esSources = [];
    win.EventSource = class MockEventSource {
        constructor(url) {
            this.url = url;
            this.onmessage = null;
            this.onerror = null;
            esSources.push(this);
        }
        close() { this.closed = true; }
    };

    const scriptEl = doc.createElement('script');
    scriptEl.textContent = scriptContent;
    doc.body.appendChild(scriptEl);

    return { dom, win, doc, fetchMock, esSources };
}

// ═══════════════════════════════════════════════════════════════
// 1. HTML STRUCTURE
// ═══════════════════════════════════════════════════════════════
describe('HTML Structure', () => {
    let doc;
    beforeAll(() => {
        const dom = new JSDOM(rawHtml, { url: 'http://localhost:8000' });
        doc = dom.window.document;
    });

    test('page title is Memory Vault', () => {
        expect(doc.title).toBe('Memory Vault');
    });

    test('has charset and viewport meta tags', () => {
        expect(doc.querySelector('meta[charset]')).not.toBeNull();
        expect(doc.querySelector('meta[name="viewport"]')).not.toBeNull();
    });

    test('has sidebar navigation with 3 items', () => {
        expect(doc.getElementById('appNav')).not.toBeNull();
        const items = doc.querySelectorAll('.nav-item');
        expect(items.length).toBe(3);
    });

    test('nav items are Home, Chat, Vault', () => {
        const pages = Array.from(doc.querySelectorAll('.nav-item')).map(i => i.dataset.page);
        expect(pages).toEqual(['home', 'chat', 'vault']);
    });

    test('has home page with 4 stat cards', () => {
        expect(doc.getElementById('page-home')).not.toBeNull();
        expect(doc.querySelectorAll('#statsGrid .stat-card').length).toBe(4);
    });

    test('has chat view with messages, input, and send button', () => {
        expect(doc.getElementById('chatView')).not.toBeNull();
        expect(doc.getElementById('chatMessages')).not.toBeNull();
        expect(doc.getElementById('messageInput')).not.toBeNull();
        expect(doc.getElementById('sendBtn')).not.toBeNull();
    });

    test('has welcome state with 4 suggestion chips', () => {
        expect(doc.getElementById('welcomeState')).not.toBeNull();
        expect(doc.querySelectorAll('.suggestion-chip').length).toBe(4);
    });

    test('has vault page with three-column tree layout', () => {
        expect(doc.getElementById('page-vault')).not.toBeNull();
        expect(doc.getElementById('vaultColTypes')).not.toBeNull();
        expect(doc.getElementById('vaultColItems')).not.toBeNull();
        expect(doc.getElementById('vaultColContent')).not.toBeNull();
        expect(doc.querySelectorAll('.vault-tree-item').length).toBe(3);
        expect(doc.getElementById('vaultSearch')).not.toBeNull();
    });

    test('has profile page with auth card and build controls', () => {
        expect(doc.getElementById('page-profile')).not.toBeNull();
        expect(doc.getElementById('authCard')).not.toBeNull();
        expect(doc.getElementById('buildDays')).not.toBeNull();
        expect(doc.getElementById('buildMax')).not.toBeNull();
        expect(doc.getElementById('buildBtn')).not.toBeNull();
    });

    test('has conversations panel', () => {
        expect(doc.getElementById('chatPanel')).not.toBeNull();
        expect(doc.getElementById('chatList')).not.toBeNull();
    });

    test('chat nav item is active by default', () => {
        const chatNav = doc.querySelector('.nav-item[data-page="chat"]');
        expect(chatNav.classList.contains('active')).toBe(true);
    });

    test('has login page with Google sign-in button', () => {
        const loginPage = doc.getElementById('loginPage');
        expect(loginPage).not.toBeNull();
        expect(loginPage.classList.contains('login-page')).toBe(true);
        expect(doc.getElementById('loginGoogleBtn')).not.toBeNull();
        expect(doc.querySelector('.login-title').textContent).toBe('Memory Vault');
    });

    test('has top bar with logout button', () => {
        const topBar = doc.getElementById('topBar');
        expect(topBar).not.toBeNull();
        expect(doc.querySelector('.logout-btn')).not.toBeNull();
        expect(doc.getElementById('logoutEmail')).not.toBeNull();
    });

    test('sidebar footer is a button that navigates to profile', () => {
        const profileBtn = doc.querySelector('.nav-profile');
        expect(profileBtn).not.toBeNull();
        expect(profileBtn.tagName).toBe('BUTTON');
        expect(profileBtn.getAttribute('onclick')).toContain('profile');
    });

    test('sidebar footer has profile name and sub elements', () => {
        expect(doc.getElementById('navAvatar')).not.toBeNull();
        expect(doc.getElementById('navProfileName')).not.toBeNull();
        expect(doc.getElementById('navProfileSub')).not.toBeNull();
    });

    test('has global build indicator in sidebar', () => {
        const indicator = doc.getElementById('buildIndicator');
        expect(indicator).not.toBeNull();
        expect(indicator.classList.contains('build-indicator')).toBe(true);
        expect(doc.getElementById('buildIndicatorText')).not.toBeNull();
        expect(doc.getElementById('buildIndicatorBar')).not.toBeNull();
    });

    test('has home page build progress card', () => {
        const card = doc.getElementById('homeBuildCard');
        expect(card).not.toBeNull();
        expect(card.classList.contains('home-build-card')).toBe(true);
        expect(doc.getElementById('homeBuildFill')).not.toBeNull();
        expect(doc.getElementById('homeBuildMessage')).not.toBeNull();
        expect(doc.getElementById('homeBuildStages')).not.toBeNull();
    });
});

// ═══════════════════════════════════════════════════════════════
// 2. CSS DESIGN TOKENS
// ═══════════════════════════════════════════════════════════════
describe('CSS Design Tokens', () => {
    let styleContent;
    beforeAll(() => {
        const dom = new JSDOM(rawHtml, { url: 'http://localhost:8000' });
        const style = dom.window.document.querySelector('style');
        styleContent = style ? style.textContent : '';
    });

    test('defines color tokens', () => {
        expect(styleContent).toContain('--bg-primary:');
        expect(styleContent).toContain('--accent-sage:');
        expect(styleContent).toContain('--text-primary:');
    });

    test('defines font families', () => {
        expect(styleContent).toContain("'Literata'");
        expect(styleContent).toContain("'DM Sans'");
        expect(styleContent).toContain("'JetBrains Mono'");
    });

    test('defines spacing and radius tokens', () => {
        expect(styleContent).toContain('--radius-sm:');
        expect(styleContent).toContain('--radius-md:');
        expect(styleContent).toContain('--radius-lg:');
    });

    test('defines shadow tokens', () => {
        expect(styleContent).toContain('--shadow-soft:');
        expect(styleContent).toContain('--shadow-medium:');
        expect(styleContent).toContain('--shadow-float:');
    });

    test('defines easing and layout tokens', () => {
        expect(styleContent).toContain('--ease-gentle:');
        expect(styleContent).toContain('--ease-spring:');
        expect(styleContent).toContain('--nav-width-expanded:');
    });

    test('includes keyframe animations', () => {
        expect(styleContent).toContain('@keyframes orbFloat');
        expect(styleContent).toContain('@keyframes breathe');
        expect(styleContent).toContain('@keyframes messageIn');
        expect(styleContent).toContain('@keyframes pageElementIn');
    });

    test('chat flex chain has min-height: 0 for scroll containment', () => {
        // #chatView and .chat-main must have min-height: 0 so that
        // .chat-messages overflow-y: auto actually triggers a scrollbar
        expect(styleContent).toMatch(/#chatView\s*\{[^}]*min-height:\s*0/);
        expect(styleContent).toMatch(/\.chat-main\s*\{[^}]*min-height:\s*0/);
        expect(styleContent).toMatch(/\.chat-messages\s*\{[^}]*overflow-y:\s*auto/);
    });
});

// ═══════════════════════════════════════════════════════════════
// 3. NAVIGATION
// ═══════════════════════════════════════════════════════════════
describe('Navigation', () => {
    let env;
    beforeEach(async () => {
        env = createEnv();
        await flush();
    });
    afterEach(() => env.dom.window.close());

    test('navigateTo("home") shows home page, hides chat', async () => {
        env.win.navigateTo('home');
        await flush();
        expect(env.doc.getElementById('page-home').classList.contains('active')).toBe(true);
        expect(env.doc.getElementById('chatView').style.display).toBe('none');
    });

    test('navigateTo("chat") shows chat view', () => {
        env.win.navigateTo('chat');
        expect(env.doc.getElementById('chatView').style.display).toBe('flex');
    });

    test('navigateTo("vault") shows vault page', async () => {
        env.win.navigateTo('vault');
        await flush();
        expect(env.doc.getElementById('page-vault').classList.contains('active')).toBe(true);
    });

    test('navigateTo("profile") shows profile page', async () => {
        env.win.navigateTo('profile');
        await flush();
        expect(env.doc.getElementById('page-profile').classList.contains('active')).toBe(true);
    });

    test('navigateTo updates active nav item', () => {
        env.win.navigateTo('vault');
        expect(env.doc.querySelector('.nav-item[data-page="vault"]').classList.contains('active')).toBe(true);
        expect(env.doc.querySelector('.nav-item[data-page="chat"]').classList.contains('active')).toBe(false);
    });

    test('navigateTo("home") fetches stats and memories', async () => {
        env.win.navigateTo('home');
        await flush();
        const urls = env.fetchMock.mock.calls.map(c => String(c[0]));
        expect(urls.some(u => u.includes('/api/stats'))).toBe(true);
        expect(urls.some(u => u.includes('/api/memories'))).toBe(true);
    });

    test('navigateTo("profile") checks auth status', async () => {
        env.fetchMock.mockClear();
        env.win.navigateTo('profile');
        await flush();
        const urls = env.fetchMock.mock.calls.map(c => String(c[0]));
        expect(urls.some(u => u.includes('/api/auth/status'))).toBe(true);
    });

    test('toggleNav collapses and expands sidebar', () => {
        const nav = env.doc.getElementById('appNav');
        expect(nav.classList.contains('collapsed')).toBe(false);
        env.win.toggleNav();
        expect(nav.classList.contains('collapsed')).toBe(true);
        env.win.toggleNav();
        expect(nav.classList.contains('collapsed')).toBe(false);
    });

    test('togglePanel hides/shows panel on desktop', () => {
        Object.defineProperty(env.win, 'innerWidth', { value: 1200, configurable: true });
        const panel = env.doc.getElementById('chatPanel');
        env.win.togglePanel();
        expect(panel.classList.contains('hidden')).toBe(true);
        env.win.togglePanel();
        expect(panel.classList.contains('hidden')).toBe(false);
    });

    test('togglePanel uses mobile class on small screens', () => {
        Object.defineProperty(env.win, 'innerWidth', { value: 600, configurable: true });
        const panel = env.doc.getElementById('chatPanel');
        env.win.togglePanel();
        expect(panel.classList.contains('panel-mobile-open')).toBe(true);
    });
});

// ═══════════════════════════════════════════════════════════════
// 4. XSS PREVENTION
// ═══════════════════════════════════════════════════════════════
describe('XSS Prevention', () => {
    let env;
    beforeEach(async () => {
        env = createEnv();
        await flush();
    });
    afterEach(() => env.dom.window.close());

    test('esc() escapes HTML tags', () => {
        expect(env.win.esc('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;'
        );
    });

    test('esc() escapes ampersands', () => {
        expect(env.win.esc('a & b')).toBe('a &amp; b');
    });

    test('esc() returns empty string for falsy values', () => {
        expect(env.win.esc(null)).toBe('');
        expect(env.win.esc(undefined)).toBe('');
        expect(env.win.esc('')).toBe('');
    });

    test('esc() escapes img onerror attack vector', () => {
        const result = env.win.esc('<img src=x onerror=alert(1)>');
        expect(result).not.toContain('<img');
        expect(result).toContain('&lt;');
    });

    test('user message uses textContent, not innerHTML', async () => {
        const input = env.doc.getElementById('messageInput');
        input.value = '<b>bold</b>';
        env.win.sendMessage();
        await flush();
        const bubble = env.doc.querySelector('.message-group.user .msg-bubble');
        expect(bubble.textContent).toBe('<b>bold</b>');
        expect(bubble.querySelector('b')).toBeNull();
    });
});

// ═══════════════════════════════════════════════════════════════
// 5. CHAT PAGE
// ═══════════════════════════════════════════════════════════════
describe('Chat Page', () => {
    let env;
    beforeEach(async () => {
        env = createEnv();
        await flush();
    });
    afterEach(() => env.dom.window.close());

    test('welcome state is visible initially', () => {
        expect(env.doc.getElementById('welcomeState').style.display).not.toBe('none');
    });

    test('sendMessage hides welcome and adds user message', async () => {
        env.doc.getElementById('messageInput').value = 'Hello';
        env.win.sendMessage();
        await flush();
        expect(env.doc.getElementById('welcomeState').style.display).toBe('none');
        const bubble = env.doc.querySelector('.message-group.user .msg-bubble');
        expect(bubble).not.toBeNull();
        expect(bubble.textContent).toBe('Hello');
    });

    test('sendMessage clears input after sending', async () => {
        const input = env.doc.getElementById('messageInput');
        input.value = 'Test';
        env.win.sendMessage();
        await flush();
        expect(input.value).toBe('');
    });

    test('sendMessage shows typing indicator then assistant reply', async () => {
        env.doc.getElementById('messageInput').value = 'Query';
        env.win.sendMessage();
        expect(env.doc.getElementById('typingIndicator')).not.toBeNull();
        await flush();
        expect(env.doc.getElementById('typingIndicator')).toBeNull();
        expect(env.doc.querySelector('.message-group.assistant .msg-bubble')).not.toBeNull();
    });

    test('sendMessage ignores empty input', () => {
        env.doc.getElementById('messageInput').value = '   ';
        env.win.sendMessage();
        expect(env.doc.querySelector('.message-group.user')).toBeNull();
    });

    test('sendMessage blocks while querying', async () => {
        env.doc.getElementById('messageInput').value = 'First';
        env.win.sendMessage();
        env.doc.getElementById('messageInput').value = 'Second';
        env.win.sendMessage();
        await flush();
        expect(env.doc.querySelectorAll('.message-group.user').length).toBe(1);
    });

    test('sendSuggestion fills input and sends', async () => {
        const chip = env.doc.querySelector('.suggestion-chip');
        const text = chip.textContent;
        env.win.sendSuggestion(chip);
        await flush();
        expect(env.doc.querySelector('.message-group.user .msg-bubble').textContent).toBe(text);
    });

    test('handleKey sends on Enter, not on Shift+Enter', () => {
        env.doc.getElementById('messageInput').value = 'Enter test';
        let prevented = false;
        const enterEvt = new env.win.KeyboardEvent('keydown', { key: 'Enter', shiftKey: false });
        Object.defineProperty(enterEvt, 'preventDefault', { value: () => { prevented = true; } });
        env.win.handleKey(enterEvt);
        expect(prevented).toBe(true);
    });

    test('autoResize toggles send button active class', () => {
        const input = env.doc.getElementById('messageInput');
        const btn = env.doc.getElementById('sendBtn');
        input.value = 'text';
        env.win.autoResize(input);
        expect(btn.classList.contains('active')).toBe(true);
        input.value = '';
        env.win.autoResize(input);
        expect(btn.classList.contains('active')).toBe(false);
    });

    test('newConversation resets chat state', async () => {
        env.doc.getElementById('messageInput').value = 'Msg';
        env.win.sendMessage();
        await flush();
        env.win.newConversation();
        expect(env.doc.getElementById('welcomeState').style.display).not.toBe('none');
        expect(env.doc.querySelectorAll('.message-group').length).toBe(0);
    });

    test('assistant message has copy button', async () => {
        env.doc.getElementById('messageInput').value = 'Copy test';
        env.win.sendMessage();
        await flush();
        expect(env.doc.querySelector('.message-group.assistant .msg-copy-btn')).not.toBeNull();
    });

    test('copyMessage calls clipboard API', async () => {
        env.doc.getElementById('messageInput').value = 'Copy me';
        env.win.sendMessage();
        await flush();
        const copyBtn = env.doc.querySelector('.msg-copy-btn');
        env.win.copyMessage(copyBtn);
        await flush();
        expect(env.win.navigator.clipboard.writeText).toHaveBeenCalled();
    });

    test('query sends POST to /api/query with question', async () => {
        env.doc.getElementById('messageInput').value = 'What are my decisions?';
        env.win.sendMessage();
        await flush();
        const call = env.fetchMock.mock.calls.find(c => String(c[0]).includes('/api/query'));
        expect(call).toBeDefined();
        expect(call[1].method).toBe('POST');
        expect(JSON.parse(call[1].body).question).toBe('What are my decisions?');
    });

    test('chat messages container has overflow-y auto for scrolling', async () => {
        const chatMsgs = env.doc.getElementById('chatMessages');
        expect(chatMsgs).not.toBeNull();
        expect(chatMsgs.classList.contains('chat-messages')).toBe(true);
        // Verify the CSS rule exists via the stylesheet
        const style = env.doc.querySelector('style');
        expect(style.textContent).toMatch(/\.chat-messages\s*\{[^}]*overflow-y:\s*auto/);
    });
});

// ═══════════════════════════════════════════════════════════════
// 6. HOME PAGE
// ═══════════════════════════════════════════════════════════════
describe('Home Page', () => {
    test('displays stats from API', async () => {
        const env = createEnv({
            '/api/stats': { total: 42, by_type: { people: 10, decisions: 20, commitments: 12 } },
        });
        env.win.navigateTo('home');
        await flush();
        expect(env.doc.getElementById('statTotal').textContent).toBe('42');
        expect(env.doc.getElementById('statPeople').textContent).toBe('10');
        expect(env.doc.getElementById('statDecisions').textContent).toBe('20');
        expect(env.doc.getElementById('statCommitments').textContent).toBe('12');
        env.dom.window.close();
    });

    test('displays recent memories', async () => {
        const env = createEnv({
            '/api/memories': {
                memories: [
                    { title: 'Mem 1', type: 'decisions', date: '2026-01-01', filepath: 'decisions/m1.md' },
                    { title: 'Mem 2', type: 'people', date: '2026-01-02', filepath: 'people/m2.md' },
                ]
            },
        });
        env.win.navigateTo('home');
        await flush();
        expect(env.doc.querySelectorAll('#recentMemories .card-row').length).toBe(2);
        env.dom.window.close();
    });

    test('shows empty state when no memories', async () => {
        const env = createEnv();
        env.win.navigateTo('home');
        await flush();
        const empty = env.doc.querySelector('#recentMemories .empty-state');
        expect(empty).not.toBeNull();
        expect(empty.textContent).toContain('No memories yet');
        env.dom.window.close();
    });

    test('handles stats API failure gracefully', async () => {
        const env = createEnv();
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/stats')) return Promise.reject(new Error('fail'));
            return Promise.resolve({ ok: true, json: () => Promise.resolve({ memories: [] }) });
        });
        env.win.navigateTo('home');
        await flush();
        expect(env.doc.getElementById('page-home')).not.toBeNull();
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 7. VAULT PAGE (Three-Column Tree Navigator)
// ═══════════════════════════════════════════════════════════════
describe('Vault Page', () => {
    const vaultMemories = [
        { title: 'D1', type: 'decisions', filepath: 'decisions/d1.md', date: '2026-01-01', tags: ['t1'] },
        { title: 'D2', type: 'decisions', filepath: 'decisions/d2.md', date: '2026-01-03', tags: [] },
        { title: 'P1', type: 'people', filepath: 'people/p1.md', date: '2026-01-02', tags: ['team'] },
        { title: 'C1', type: 'commitments', filepath: 'commitments/c1.md', date: '2026-02-01', tags: [] },
    ];

    test('column 1 has three type categories', async () => {
        const env = createEnv();
        await flush();
        const items = env.doc.querySelectorAll('.vault-tree-item');
        expect(items.length).toBe(3);
        const types = Array.from(items).map(i => i.dataset.type);
        expect(types).toContain('people');
        expect(types).toContain('commitments');
        expect(types).toContain('decisions');
        env.dom.window.close();
    });

    test('navigating to vault loads memories and shows counts', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        expect(env.doc.getElementById('countPeople').textContent).toBe('1');
        expect(env.doc.getElementById('countDecisions').textContent).toBe('2');
        expect(env.doc.getElementById('countCommitments').textContent).toBe('1');
        env.dom.window.close();
    });

    test('selectVaultType highlights type and shows items in column 2', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        const btn = env.doc.querySelector('.vault-tree-item[data-type="decisions"]');
        env.win.selectVaultType('decisions', btn);
        expect(btn.classList.contains('active')).toBe(true);
        const fileItems = env.doc.querySelectorAll('.vault-file-item');
        expect(fileItems.length).toBe(2);
        expect(env.doc.getElementById('vaultItemsTitle').textContent).toBe('Decisions');
        env.dom.window.close();
    });

    test('selecting a file loads markdown content in column 3', async () => {
        const env = createEnv({
            '/api/memories': { memories: vaultMemories },
            '/api/memory/decisions/d1.md': {
                frontmatter: { title: 'Decision One', date: '2026-01-01', tags: ['t1'] },
                content: '# My Decision\n\nThis is the **body** of the decision.'
            }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        const fileBtn = env.doc.querySelector('.vault-file-item');
        fileBtn.click();
        await flush();
        const header = env.doc.getElementById('vaultContentHeader');
        expect(header.style.display).toBe('block');
        expect(env.doc.getElementById('vaultContentTitle').textContent).toBe('Decision One');
        const body = env.doc.getElementById('vaultContentBody');
        expect(body.querySelector('.vault-rendered-md')).not.toBeNull();
        env.dom.window.close();
    });

    test('markdown content is rendered with formatting', async () => {
        const env = createEnv({
            '/api/memories': { memories: vaultMemories },
            '/api/memory/decisions/d1.md': {
                frontmatter: { title: 'Test' },
                content: '**bold text** and *italic text* and `code`'
            }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        env.doc.querySelector('.vault-file-item').click();
        await flush();
        const md = env.doc.querySelector('.vault-rendered-md');
        expect(md.querySelector('strong')).not.toBeNull();
        expect(md.querySelector('em')).not.toBeNull();
        expect(md.querySelector('code')).not.toBeNull();
        env.dom.window.close();
    });

    test('content header shows metadata badges', async () => {
        const env = createEnv({
            '/api/memories': { memories: vaultMemories },
            '/api/memory/people/p1.md': {
                frontmatter: { title: 'Person One', date: '2026-01-02', role: 'Engineer', tags: ['team'] },
                content: 'Person details'
            }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('people', env.doc.querySelector('.vault-tree-item[data-type="people"]'));
        env.doc.querySelector('.vault-file-item').click();
        await flush();
        const meta = env.doc.getElementById('vaultContentMeta');
        expect(meta.querySelectorAll('span').length).toBeGreaterThanOrEqual(1);
        env.dom.window.close();
    });

    test('search filters items in column 2', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        env.doc.getElementById('vaultSearch').value = 'D1';
        env.win.debouncedSearch();
        await new Promise(r => setTimeout(r, 400));
        const fileItems = env.doc.querySelectorAll('.vault-file-item');
        expect(fileItems.length).toBe(1);
        expect(fileItems[0].querySelector('.vault-file-title').textContent).toBe('D1');
        env.dom.window.close();
    });

    test('empty search shows all items for selected type', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        env.doc.getElementById('vaultSearch').value = '';
        env.win.debouncedSearch();
        await new Promise(r => setTimeout(r, 400));
        expect(env.doc.querySelectorAll('.vault-file-item').length).toBe(2);
        env.dom.window.close();
    });

    test('switching types clears content column', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('people', env.doc.querySelector('.vault-tree-item[data-type="people"]'));
        const contentHeader = env.doc.getElementById('vaultContentHeader');
        expect(contentHeader.style.display).toBe('none');
        const empty = env.doc.querySelector('.vault-content-empty');
        expect(empty).not.toBeNull();
        env.dom.window.close();
    });

    test('Escape key clears content viewer', async () => {
        const env = createEnv({
            '/api/memories': { memories: vaultMemories },
            '/api/memory/decisions/d1.md': { frontmatter: { title: 'T' }, content: 'body' }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        env.doc.querySelector('.vault-file-item').click();
        await flush();
        env.doc.dispatchEvent(new env.win.KeyboardEvent('keydown', { key: 'Escape' }));
        expect(env.doc.querySelector('.vault-content-empty')).not.toBeNull();
        env.dom.window.close();
    });

    test('shows empty state when type has no memories', async () => {
        const env = createEnv({ '/api/memories': { memories: [] } });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('people', env.doc.querySelector('.vault-tree-item[data-type="people"]'));
        const empty = env.doc.querySelector('#vaultItemList .empty-state');
        expect(empty).not.toBeNull();
        expect(empty.textContent).toContain('No memories found');
        env.dom.window.close();
    });

    test('file items display tags', async () => {
        const env = createEnv({ '/api/memories': { memories: vaultMemories } });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('people', env.doc.querySelector('.vault-tree-item[data-type="people"]'));
        const tags = env.doc.querySelectorAll('.vault-file-item .tag');
        expect(tags.length).toBe(1);
        expect(tags[0].textContent).toBe('team');
        env.dom.window.close();
    });

    test('file item shows active state when selected', async () => {
        const env = createEnv({
            '/api/memories': { memories: vaultMemories },
            '/api/memory/decisions/d1.md': { frontmatter: { title: 'T' }, content: 'x' }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        const fileBtn = env.doc.querySelector('.vault-file-item');
        fileBtn.click();
        await flush();
        expect(fileBtn.classList.contains('active')).toBe(true);
        env.dom.window.close();
    });

    test('handles backslash filepaths from Windows API responses', async () => {
        const winMemories = [
            { title: 'WinDecision', type: 'decisions', filepath: 'decisions\\wd1.md', date: '2026-01-01', tags: [] },
        ];
        const env = createEnv({
            '/api/memories': { memories: winMemories },
            '/api/memory/decisions/wd1.md': {
                frontmatter: { title: 'WinDecision' },
                content: 'Windows path content here'
            }
        });
        env.win.navigateTo('vault');
        await flush();
        env.win.selectVaultType('decisions', env.doc.querySelector('.vault-tree-item[data-type="decisions"]'));
        const fileItems = env.doc.querySelectorAll('.vault-file-item');
        expect(fileItems.length).toBe(1);
        // Click the file item — should correctly extract filename despite backslash
        fileItems[0].click();
        await flush();
        expect(env.doc.getElementById('vaultContentTitle').textContent).toBe('WinDecision');
        expect(env.doc.querySelector('.vault-rendered-md').textContent).toContain('Windows path content');
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 8. PROFILE PAGE
// ═══════════════════════════════════════════════════════════════
describe('Profile Page', () => {
    test('shows Connected when authenticated', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: true, credentials_exist: true } });
        env.win.navigateTo('profile');
        await flush();
        expect(env.doc.getElementById('authStatus').textContent).toContain('Connected');
        expect(env.doc.getElementById('authActionRow').style.display).toBe('none');
        env.dom.window.close();
    });

    test('shows Not connected with connect button when credentials exist', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: true } });
        env.win.navigateTo('profile');
        await flush();
        expect(env.doc.getElementById('authStatus').textContent).toContain('Not connected');
        expect(env.doc.getElementById('authActionRow').style.display).toBe('flex');
        env.dom.window.close();
    });

    test('shows No credentials when none exist', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: false } });
        env.win.navigateTo('profile');
        await flush();
        expect(env.doc.getElementById('authStatus').textContent).toContain('No credentials');
        env.dom.window.close();
    });

    test('connectGmail sends POST to /api/auth/google', async () => {
        const env = createEnv({
            '/api/auth/status': { authenticated: false, credentials_exist: true },
            '/api/auth/google': { status: 'success' },
        });
        env.win.navigateTo('profile');
        await flush();
        env.win.connectGmail();
        await flush();
        const call = env.fetchMock.mock.calls.find(c => String(c[0]).includes('/api/auth/google'));
        expect(call).toBeDefined();
        expect(call[1].method).toBe('POST');
        env.dom.window.close();
    });

    test('connectGmail disables button during connection', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: true } });
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/auth/google')) return new Promise(() => {});
            if (String(url).includes('/api/auth/status'))
                return Promise.resolve({ ok: true, json: () => Promise.resolve({ authenticated: false, credentials_exist: true }) });
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        env.win.navigateTo('profile');
        await flush();
        env.win.connectGmail();
        expect(env.doc.getElementById('connectBtn').disabled).toBe(true);
        expect(env.doc.getElementById('connectBtn').textContent).toBe('Connecting...');
        env.dom.window.close();
    });

    test('startBuild creates EventSource with parameters', async () => {
        const env = createEnv();
        await flush();
        env.doc.getElementById('buildDays').value = '7';
        env.doc.getElementById('buildMax').value = '25';
        env.doc.getElementById('buildQuery').value = 'from:test@test.com';
        env.win.startBuild();
        expect(env.esSources.length).toBe(1);
        expect(env.esSources[0].url).toContain('days_back=7');
        expect(env.esSources[0].url).toContain('max_emails=25');
        expect(env.doc.getElementById('buildBtn').disabled).toBe(true);
        env.dom.window.close();
    });

    test('build SSE complete event re-enables button', async () => {
        const env = createEnv();
        await flush();
        env.win.navigateTo('profile');
        await flush();
        env.win.startBuild();
        const es = env.esSources[0];
        es.onmessage({ data: JSON.stringify({ stage: 'reading', message: 'Reading...' }) });
        es.onmessage({ data: JSON.stringify({ stage: 'complete', message: 'Done', stats: { total: 10 } }) });
        await flush();
        expect(env.doc.getElementById('buildBtn').disabled).toBe(false);
        expect(es.closed).toBe(true);
        env.dom.window.close();
    });

    test('build SSE error event shows error message', async () => {
        const env = createEnv();
        await flush();
        env.win.navigateTo('profile');
        await flush();
        env.win.startBuild();
        env.esSources[0].onmessage({ data: JSON.stringify({ stage: 'error', message: 'Pipeline failed' }) });
        expect(env.doc.getElementById('progressMessage').textContent).toContain('Pipeline failed');
        expect(env.doc.getElementById('buildBtn').disabled).toBe(false);
        env.dom.window.close();
    });

    test('build SSE connection error handles gracefully', async () => {
        const env = createEnv();
        await flush();
        env.win.startBuild();
        env.esSources[0].onerror();
        expect(env.doc.getElementById('progressMessage').textContent).toContain('Connection lost');
        expect(env.doc.getElementById('buildBtn').disabled).toBe(false);
        env.dom.window.close();
    });

    test('auto-build activates sidebar and home indicators', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: true, credentials_exist: true } });
        await flush();
        // showMainApp() was called which triggers startIncrementalBuild()
        // The EventSource for auto-build should exist
        const autoBuildES = env.esSources.find(es => es.url.includes('max_emails=500'));
        expect(autoBuildES).toBeDefined();
        // Sidebar indicator should be active
        expect(env.doc.getElementById('buildIndicator').classList.contains('active')).toBe(true);
        // Home card should be active
        expect(env.doc.getElementById('homeBuildCard').classList.contains('active')).toBe(true);
        env.dom.window.close();
    });

    test('auto-build SSE events update progress indicators', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: true, credentials_exist: true } });
        await flush();
        const autoBuildES = env.esSources.find(es => es.url.includes('max_emails=500'));
        // Simulate a fetching event
        autoBuildES.onmessage({ data: JSON.stringify({ stage: 'fetching', status: 'started', message: 'Fetching 50 emails' }) });
        expect(env.doc.getElementById('buildIndicatorText').textContent).toBe('Fetching 50 emails');
        expect(env.doc.getElementById('homeBuildMessage').textContent).toBe('Fetching 50 emails');
        // Simulate complete
        autoBuildES.onmessage({ data: JSON.stringify({ stage: 'complete', status: 'complete', message: 'Done! 5 memories.', stats: { total: 5 } }) });
        expect(env.doc.getElementById('buildIndicator').classList.contains('done')).toBe(true);
        expect(env.doc.getElementById('homeBuildCard').classList.contains('done')).toBe(true);
        // Let async loadHomeData() settle before closing DOM
        await flush();
        env.dom.window.close();
    });

    test('displays vault stats on profile page', async () => {
        const env = createEnv({
            '/api/auth/status': { authenticated: true, credentials_exist: true },
            '/api/stats': { total: 15, by_type: { people: 5, decisions: 10 } },
        });
        env.win.navigateTo('profile');
        await flush();
        const rows = env.doc.querySelectorAll('#profileStats .card-row');
        expect(rows.length).toBeGreaterThanOrEqual(1);
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 9. SESSION STORAGE
// ═══════════════════════════════════════════════════════════════
describe('Session Storage', () => {
    test('conversation is saved after message', async () => {
        const env = createEnv();
        await flush();
        env.doc.getElementById('messageInput').value = 'Test persist';
        env.win.sendMessage();
        await flush();
        const convs = JSON.parse(env.win.sessionStorage.getItem('mv_conversations'));
        expect(convs.length).toBe(1);
        expect(convs[0].title).toContain('Test persist');
        env.dom.window.close();
    });

    test('messages are saved with correct roles', async () => {
        const env = createEnv();
        await flush();
        env.doc.getElementById('messageInput').value = 'User hello';
        env.win.sendMessage();
        await flush();
        const convs = JSON.parse(env.win.sessionStorage.getItem('mv_conversations'));
        const msgs = JSON.parse(env.win.sessionStorage.getItem('mv_messages_' + convs[0].id));
        expect(msgs.length).toBe(2);
        expect(msgs[0].role).toBe('user');
        expect(msgs[0].text).toBe('User hello');
        expect(msgs[1].role).toBe('assistant');
        env.dom.window.close();
    });

    test('assistant messages preserve raw text via data-raw', async () => {
        const env = createEnv({ '/api/query': { answer: '**Bold** and *italic*' } });
        await flush();
        env.doc.getElementById('messageInput').value = 'Format test';
        env.win.sendMessage();
        await flush();
        const convs = JSON.parse(env.win.sessionStorage.getItem('mv_conversations'));
        const msgs = JSON.parse(env.win.sessionStorage.getItem('mv_messages_' + convs[0].id));
        const assistantMsg = msgs.find(m => m.role === 'assistant');
        expect(assistantMsg.text).toBe('**Bold** and *italic*');
        env.dom.window.close();
    });

    test('conversation title truncates long messages', async () => {
        const env = createEnv();
        await flush();
        env.doc.getElementById('messageInput').value = 'A'.repeat(60);
        env.win.sendMessage();
        await flush();
        const convs = JSON.parse(env.win.sessionStorage.getItem('mv_conversations'));
        expect(convs[0].title.length).toBeLessThanOrEqual(44);
        expect(convs[0].title).toContain('...');
        env.dom.window.close();
    });

    test('newConversation clears active state', async () => {
        const env = createEnv();
        await flush();
        env.doc.getElementById('messageInput').value = 'First conv';
        env.win.sendMessage();
        await flush();
        env.win.newConversation();
        expect(env.doc.getElementById('welcomeState').style.display).not.toBe('none');
        expect(env.doc.querySelectorAll('.chat-list-item.active').length).toBe(0);
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 10. ERROR HANDLING
// ═══════════════════════════════════════════════════════════════
describe('Error Handling', () => {
    test('query error shows error message in chat', async () => {
        const env = createEnv();
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/query')) return Promise.reject(new Error('fail'));
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        await flush();
        env.doc.getElementById('messageInput').value = 'Error test';
        env.win.sendMessage();
        await flush();
        await flush();
        const last = Array.from(env.doc.querySelectorAll('.message-group.assistant .msg-bubble')).pop();
        expect(last.textContent).toContain('Sorry, something went wrong');
        env.dom.window.close();
    });

    test('vault load error shows zero counts', async () => {
        const env = createEnv();
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/memories')) return Promise.reject(new Error('fail'));
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        await flush();
        env.win.navigateTo('vault');
        await flush();
        expect(env.doc.getElementById('countPeople').textContent).toBe('0');
        expect(env.doc.getElementById('countDecisions').textContent).toBe('0');
        expect(env.doc.getElementById('countCommitments').textContent).toBe('0');
        env.dom.window.close();
    });

    test('authenticated user sees login page hidden', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: true, credentials_exist: true } });
        await flush();
        const loginPage = env.doc.getElementById('loginPage');
        expect(loginPage).not.toBeNull();
        expect(loginPage.classList.contains('hidden')).toBe(true);
        env.dom.window.close();
    });

    test('unauthenticated user sees login page visible', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: true } });
        await flush();
        const loginPage = env.doc.getElementById('loginPage');
        expect(loginPage).not.toBeNull();
        expect(loginPage.classList.contains('hidden')).toBe(false);
        env.dom.window.close();
    });

    test('auth check error shows login page', async () => {
        const { htmlOnly, scriptContent } = parseHtml(rawHtml);
        const dom = new JSDOM(htmlOnly, { url: 'http://localhost:8000', runScripts: 'dangerously', pretendToBeVisual: true });
        const win = dom.window;
        const doc = win.document;
        // Set up fetch to always reject for auth status
        win.fetch = jest.fn((url) => {
            if (String(url).includes('/api/auth/status')) return Promise.reject(new Error('fail'));
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        win.navigator.clipboard = { writeText: jest.fn() };
        win.EventSource = class { constructor() {} close() {} };
        const scriptEl = doc.createElement('script');
        scriptEl.textContent = scriptContent;
        doc.body.appendChild(scriptEl);
        // init() calls checkLoginStatus() which fails → shows login page
        await flush();
        const loginPage = doc.getElementById('loginPage');
        expect(loginPage).not.toBeNull();
        expect(loginPage.classList.contains('hidden')).toBe(false);
        dom.window.close();
    });

    test('connectGmail error shows error in auth card', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: true } });
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/auth/google')) return Promise.reject(new Error('fail'));
            if (String(url).includes('/api/auth/status'))
                return Promise.resolve({ ok: true, json: () => Promise.resolve({ authenticated: false, credentials_exist: true }) });
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        env.win.navigateTo('profile');
        await flush();
        env.win.connectGmail();
        await flush();
        expect(env.doc.querySelector('.auth-error-msg')).not.toBeNull();
        expect(env.doc.getElementById('connectBtn').disabled).toBe(false);
        env.dom.window.close();
    });

    test('memory detail load error shows error message', async () => {
        const memories = [{ type: 'decisions', filename: 'missing.md', title: 'Missing', tags: [] }];
        const env = createEnv({ '/api/memories': { memories } });
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/memory/')) return Promise.reject(new Error('fail'));
            if (String(url).includes('/api/memories'))
                return Promise.resolve({ ok: true, json: () => Promise.resolve({ memories }) });
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        await flush();
        env.win.navigateTo('vault');
        await flush(); // wait for loadVaultData to finish populating vaultAllMemories
        // Select the type so items render in column 2
        const typeBtn = env.doc.querySelector('.vault-tree-item[data-type="decisions"]');
        env.win.selectVaultType('decisions', typeBtn);
        await flush();
        // Click the file item to trigger loadVaultContent (which will fail)
        const fileBtn = env.doc.querySelector('.vault-file-item');
        expect(fileBtn).not.toBeNull();
        fileBtn.click();
        await flush();
        expect(env.doc.getElementById('vaultContentBody').textContent).toContain('Could not load memory');
        env.dom.window.close();
    });

    test('search with no matching results shows empty item list', async () => {
        const env = createEnv({
            '/api/memories': { memories: [{ type: 'people', filename: 'alice.md', title: 'Alice', tags: ['friend'] }] },
        });
        await flush();
        env.win.navigateTo('vault');
        await flush();
        // Select a type first so items are rendered
        const typeBtn = env.doc.querySelector('.vault-tree-item[data-type="people"]');
        env.win.selectVaultType('people', typeBtn);
        await flush();
        // Search for something that doesn't match
        env.doc.getElementById('vaultSearch').value = 'zzz_no_match';
        env.win.debouncedSearch();
        await new Promise(r => setTimeout(r, 400));
        await flush();
        expect(env.doc.querySelectorAll('.vault-file-item').length).toBe(0);
        env.dom.window.close();
    });

    test('connectGmail handles non-ok response', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: false, credentials_exist: true } });
        env.fetchMock.mockImplementation((url) => {
            if (String(url).includes('/api/auth/google'))
                return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'Server error' }) });
            if (String(url).includes('/api/auth/status'))
                return Promise.resolve({ ok: true, json: () => Promise.resolve({ authenticated: false, credentials_exist: true }) });
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
        env.win.navigateTo('profile');
        await flush();
        env.win.connectGmail();
        await flush();
        expect(env.doc.querySelector('.auth-error-msg')).not.toBeNull();
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 11. RESPONSIVE DESIGN
// ═══════════════════════════════════════════════════════════════
describe('Responsive Design', () => {
    test('panel open button hidden when panel is visible', async () => {
        const env = createEnv({ '/api/auth/status': { authenticated: true, credentials_exist: true } });
        await flush();
        Object.defineProperty(env.win, 'innerWidth', { value: 1200, configurable: true });
        env.win.navigateTo('chat');
        expect(env.doc.getElementById('panelOpenBtn').style.display).toBe('none');
        env.win.togglePanel();
        expect(env.doc.getElementById('panelOpenBtn').style.display).toBe('flex');
        env.dom.window.close();
    });

    test('mobile panel toggle uses panel-mobile-open class', async () => {
        const env = createEnv();
        await flush();
        Object.defineProperty(env.win, 'innerWidth', { value: 500, configurable: true });
        env.win.togglePanel();
        expect(env.doc.getElementById('chatPanel').classList.contains('panel-mobile-open')).toBe(true);
        env.dom.window.close();
    });

    test('resize event does not throw', async () => {
        const env = createEnv();
        await flush();
        expect(() => {
            env.win.dispatchEvent(new env.win.Event('resize'));
        }).not.toThrow();
        env.dom.window.close();
    });
});

// ═══════════════════════════════════════════════════════════════
// 12. ACCESSIBILITY
// ═══════════════════════════════════════════════════════════════
describe('Accessibility', () => {
    let doc;
    beforeAll(() => {
        const dom = new JSDOM(rawHtml, { url: 'http://localhost:8000' });
        doc = dom.window.document;
    });

    test('html has lang attribute', () => {
        expect(doc.documentElement.getAttribute('lang')).toBe('en');
    });

    test('navigation has aria-label', () => {
        expect(doc.getElementById('appNav').getAttribute('aria-label')).toBe('Main navigation');
    });

    test('all nav items have aria-labels', () => {
        doc.querySelectorAll('.nav-item').forEach(item => {
            expect(item.getAttribute('aria-label')).toBeTruthy();
        });
    });

    test('message input and send button have aria-labels', () => {
        expect(doc.getElementById('messageInput').getAttribute('aria-label')).toBeTruthy();
        expect(doc.getElementById('sendBtn').getAttribute('aria-label')).toBe('Send message');
    });

    test('toggle sidebar button has aria-label', () => {
        expect(doc.querySelector('.nav-collapse-btn').getAttribute('aria-label')).toBe('Toggle sidebar');
    });

    test('decorative icons have aria-hidden', () => {
        expect(doc.querySelector('.nav-brand-icon').getAttribute('aria-hidden')).toBe('true');
        expect(doc.querySelector('.chat-header-avatar').getAttribute('aria-hidden')).toBe('true');
    });

    test('panel toggle buttons have aria-labels', () => {
        expect(doc.querySelector('.panel-toggle-btn').getAttribute('aria-label')).toBeTruthy();
        expect(doc.getElementById('panelOpenBtn').getAttribute('aria-label')).toBeTruthy();
    });
});
