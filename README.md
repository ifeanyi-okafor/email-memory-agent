# 🧠 Email Memory Agent

### Most memory systems wait to learn about you. This one already knows.

---

## 🧊 The Cold-Start Problem

Most AI memory systems save your chat conversations. They only learn about you as you keep chatting. New app? Blank slate. Every time.

That's backwards. The signal is already there — sitting in apps you use every day.

☕ That Starbucks receipt in your inbox by 7:15 every morning? You like your coffee black.
✈️ That flight booking? Window, not aisle.
🔋 That Tesla charging report? You drive an EV.

**Memory should learn about you as you live your life — not only when you chat with chatbots.**

---

## 🔮 Persistent Ambient Memory

This app flips the script. Instead of waiting to learn about you, it scans your Gmail and builds a rich picture of who you are **the moment you onboard**:

- 👤 **People** — who they are, how you know them, what you've discussed
- 📋 **Decisions** — what was agreed, when, and with whom
- 🤝 **Commitments** — promises made (by you and to you), with follow-through tracking
- 🚨 **Action Items** — what you need to do, prioritized by urgency

Ask questions in plain English:

> *"What did I promise Mike last month?"*
> *"Who do I need to follow up with this week?"*

No cold-start. No training period. Just memory, from day one.

---

## ✨ How It Works (The Simple Version)

```
1. 📬  You connect your Gmail account
2. 🤖  AI reads your emails and extracts what matters
3. 🗂️  Everything gets organized into a local memory vault
4. 💬  You chat with your memory through a browser interface
```

That's it. Your emails become a searchable, organized second brain.

Everything stays **local on your computer** — your emails and memories are never stored on someone else's server.

---

## 🏗️ Architecture & Components

Under the hood, the app is a **team of AI agents** that each have a specific job. Think of it like a small office where each worker has a role:

```
┌─────────────────────────────────────────────────┐
│                 🌐 Browser Chat UI               │
│           (where you interact with it)           │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              🎯 The Orchestrator                 │
│     (the manager — decides who does what)        │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 📨 Email │ │ 📝 Memory│ │ 🔍 Query         │ │
│  │  Reader  │ │  Writer  │ │    Agent          │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────────────┐ ┌──────────────────────┐   │
│  │ ⚡ Action Agent   │ │ 🔄 Reconciliation   │   │
│  │ (finds to-dos)   │ │    Agent (tracks     │   │
│  │                   │ │    follow-through)   │   │
│  └──────────────────┘ └──────────────────────┘   │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              🗄️ Memory Vault                     │
│   (organized markdown files on your computer)    │
│                                                  │
│   📁 people/        — profiles of contacts       │
│   📁 decisions/     — agreements & choices        │
│   📁 commitments/   — promises & obligations      │
│   📁 action_required/ — your prioritized to-dos   │
│   🕸️ _graph.json    — how everything connects     │
└─────────────────────────────────────────────────┘
```

### 🤖 The Five Agents

| Agent | Role | Analogy |
|-------|------|---------|
| 📨 **Email Reader** | Reads your Gmail and pulls out important observations | The *mail clerk* who opens and sorts every letter |
| 📝 **Memory Writer** | Organizes observations into structured memory files | The *filing clerk* who puts everything in the right folder |
| ⚡ **Action Agent** | Scans your memories and finds things you need to act on | The *executive assistant* who flags your to-do list |
| 🔄 **Reconciliation Agent** | Checks if you've already handled your action items | The *accountability partner* who tracks follow-through |
| 🔍 **Query Agent** | Answers your questions by searching the vault | The *librarian* who finds exactly what you're looking for |

### 🗂️ The Memory Vault

Your memories aren't stored in a database — they're **plain text files** on your computer. Each file is a readable document with:

- **Metadata** at the top (type, date, related people, status)
- **Content** in the middle (the actual memory, in plain language)
- **Links** to related memories (so everything stays connected)

This means you can open, read, and edit your memories with any text editor. You own your data completely.

### 🕸️ The Knowledge Graph

Every memory is connected to related memories through a **knowledge graph** — a web of relationships. When you ask *"Tell me about the project with Sarah"*, the agent doesn't just search for "Sarah" — it follows the connections between Sarah's profile, decisions she was part of, commitments involving her, and action items related to her.

---

## 🔄 The Agentic Flow

When you tell the app to **build your memory**, here's what happens step by step:

```
 Step 1   📬  Fetch your recent emails from Gmail
            │
            ▼
 Step 2   📨  The Email Reader analyzes each email:
            │  "Who is this about? What was decided?
            │   Were any promises made?"
            ▼
 Step 3   📝  The Memory Writer creates organized files:
            │  People profiles, decisions, commitments —
            │  each one neatly categorized and linked
            ▼
 Step 4   🕸️  The Knowledge Graph rebuilds:
            │  All memories get connected to each other
            │  (Sarah → Q3 Decision → Budget Commitment)
            ▼
 Step 5   ⚡  The Action Agent scans everything and asks:
            │  "What does this person still need to do?"
            │  Generates a prioritized to-do list
            ▼
 Step 6   🔄  The Reconciliation Agent checks your sent mail:
            │  "Did they already respond to this?"
            │  Marks completed items as done
            ▼
 Done!    ✅  Your memory vault is up to date
```

When you **ask a question**, the flow is simpler:

```
 You ask   💬  "What did I promise the design team?"
              │
              ▼
 Search    🔍  The Query Agent searches the vault,
              │  follows knowledge graph connections,
              │  and reads relevant memories
              ▼
 Answer    💡  "You promised to deliver the brand
               guidelines by March 15th and review
               the mockups by end of week."
```

### ⚡ Action Prioritization

Action items aren't just a flat list — they're organized using the **Eisenhower Matrix**, a well-known prioritization method:

| | ⏰ Urgent | 📅 Not Urgent |
|---|---|---|
| ⭐ **Important** | 🔴 Do first | 🟡 Schedule it |
| ○ **Not Important** | 🟠 Delegate if possible | ⚪ Consider dropping |

So when you ask *"What should I focus on today?"*, you get the most critical items first.

---

## 🚀 Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Set up your API key**: Copy `.env.example` to `.env` and add your key
3. **Connect Gmail**: One-time OAuth setup (see the tutorial)
4. **Launch**: `python main.py`
5. **Open** `http://localhost:8000` in your browser

That's it — type **"build"** in the chat to scan your emails and start building your memory.

---

## 🛡️ Privacy

- All data stays **local on your machine** — no cloud storage, no third-party servers
- Email content is processed through AI APIs (OpenRouter or Anthropic) but **is not stored** by them
- Your memory vault is just files on your hard drive — you can delete them anytime
- OAuth tokens are stored locally and never committed to source control

---

## 🛠️ Built With

| What | Why |
|------|-----|
| Python | Core language |
| AI (LLM) | Powers the reading, writing, and querying agents |
| Gmail API | Securely reads your email with your permission |
| FastAPI | Runs the local web server |
| Markdown files | Stores your memories as human-readable text |

---

<p align="center">
  <em>Built as a learning project for multi-agent AI systems.</em><br>
  <em>Memory should learn about you as you live your life — not only when you chat with chatbots.</em>
</p>
