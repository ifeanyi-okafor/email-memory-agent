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

## Build Pipeline State

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Fetching: User triggers build or auto-build
    Fetching --> Filtering: Emails fetched
    Fetching --> Complete: No emails found
    Filtering --> Complete: All emails already processed
    Filtering --> Analyzing: New emails to process
    Analyzing --> Analyzing: Next batch
    Analyzing --> Writing: All batches done
    Analyzing --> Error: All batches failed
    Writing --> Complete: Memories written
    Writing --> Error: Writer failed
    Complete --> Idle: Reset
    Error --> Idle: Reset
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

## Conversation State

| State | Trigger | Effect |
|-------|---------|--------|
| Welcome | Page load / new conversation | Show welcome message + suggestion chips |
| Composing | User types in input | Send button activates |
| Querying | User sends message | Input disabled, typing indicator shown |
| Received | API response arrives | Assistant message rendered, input re-enabled |
| Error | API call fails | Error message in chat, input re-enabled |
