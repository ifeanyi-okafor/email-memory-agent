# State Machines

## Auth State

```mermaid
stateDiagram-v2
    [*] --> Checking: Page load
    Checking --> LoggedOut: not authenticated
    Checking --> LoggedIn: authenticated
    LoggedOut --> Authenticating: Click "Sign in with Google"
    Authenticating --> LoggedIn: OAuth success
    Authenticating --> LoggedOut: OAuth failure
    LoggedIn --> LoggedOut: Click "Logout"
    LoggedIn --> Building: Auto-build starts
    Building --> LoggedIn: Build complete/error
```

## Build Pipeline State (Backend-tracked)

The build state is persisted in-memory on the backend (`web/app.py:build_state`). The frontend polls `/api/build/status` on page load to reconnect to a running build instead of restarting it. Only one build can run at a time (409 returned if concurrent build attempted).

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> running: /api/stream/build called
    running --> running: Progress events update stage/message/step
    running --> complete: Pipeline finishes successfully
    running --> error: Pipeline throws exception
    complete --> idle: Frontend starts new build
    error --> idle: Frontend starts new build

    state running {
        [*] --> fetching
        fetching --> email_reader: Emails fetched
        fetching --> complete_inner: No new emails
        email_reader --> memory_writer: All batches analyzed
        memory_writer --> graph_rebuild: Files written
        graph_rebuild --> action_agent: Graph rebuilt
        action_agent --> reconciliation: Actions generated
        reconciliation --> [*]: Statuses updated
    }
```

### Frontend Page-Refresh Behavior

```mermaid
flowchart TD
    LOAD[Page load / refresh] --> POLL["GET /api/build/status"]
    POLL --> CHECK{status?}
    CHECK -->|running| RESTORE[Show current progress + poll every 1.5s]
    CHECK -->|complete + recent| SHOW_DONE[Show 'done' briefly]
    CHECK -->|idle or stale| START[Start new auto-build]
    CHECK -->|error| START
```

## Frontend Page State

```mermaid
stateDiagram-v2
    [*] --> LoginPage: Not authenticated
    LoginPage --> Home: Authenticated
    Home --> Chat: navigateTo('chat')
    Chat --> Home: navigateTo('home')
    Chat --> Vault: navigateTo('vault')
    Vault --> Chat: navigateTo('chat')
    Home --> Vault: navigateTo('vault')
    Vault --> Home: navigateTo('home')
    Home --> Profile: navigateTo('profile') or click footer
    Chat --> Profile: click footer
    Vault --> Profile: click footer
    Profile --> Home: navigateTo('home')
    Profile --> Chat: navigateTo('chat')
    Profile --> Vault: navigateTo('vault')
```

## Commitment Status Lifecycle

Tracks the user's participation state for commitment memory files.

```mermaid
stateDiagram-v2
    [*] --> invited: Email mentions event/commitment
    invited --> confirmed: User RSVP'd, registered, or accepted
    invited --> declined: User explicitly declined
    invited --> tentative: User expressed interest ("maybe")
    tentative --> confirmed: User confirms attendance
    tentative --> declined: User declines
    confirmed --> declined: User cancels
```

- **Default**: `invited` — the LLM must have explicit evidence to set any other status
- **Evidence for confirmed**: words like "registered", "RSVP'd", "signed up", "accepted", "will attend"
- **Status is set at write time** by the Memory Writer Agent based on email content analysis

## Conversation State

| State | Trigger | Effect |
|-------|---------|--------|
| Welcome | Page load / new conversation | Show welcome message + suggestion chips |
| Composing | User types in input | Send button activates |
| Querying | User sends message | Input disabled, typing indicator shown |
| Received | API response arrives | Assistant message rendered, input re-enabled |
| Error | API call fails | Error message in chat, input re-enabled |
