# Dependency Graph

## Internal Module Dependencies

```mermaid
flowchart TD
    main[main.py] --> app[web/app.py]
    app --> orchestrator[orchestrator.py]
    app --> vault[memory/vault.py]
    app --> gmail_tools[tools/gmail_tools.py]

    orchestrator --> email_reader[agents/email_reader.py]
    orchestrator --> memory_writer[agents/memory_writer.py]
    orchestrator --> query_agent[agents/query_agent.py]
    orchestrator --> vault
    orchestrator --> gmail_tools
    orchestrator --> settings[config/settings.py]

    orchestrator --> action_agent[agents/action_agent.py]
    orchestrator --> reconciliation_agent[agents/reconciliation_agent.py]
    orchestrator --> graph[memory/graph.py]
    orchestrator --> dedup[memory/dedup.py]

    email_reader --> base_agent[agents/base_agent.py]
    memory_writer --> base_agent
    query_agent --> base_agent
    action_agent --> base_agent
    reconciliation_agent --> base_agent
    reconciliation_agent --> vault
    reconciliation_agent --> gmail_tools

    base_agent --> settings
    base_agent --> openrouter["OpenRouter (openai SDK)"]
    base_agent -.->|fallback| anthropic_api["Anthropic (anthropic SDK)"]

    vault --> dedup
    gmail_tools --> settings
    vault --> settings
```

## Blast Radius Analysis

| Module Changed | Affected Components |
|---------------|-------------------|
| `config/settings.py` | All agents, vault, gmail_tools, orchestrator |
| `agents/base_agent.py` | All five agents (provider adapter + retry + fallback) |
| `memory/vault.py` | Orchestrator, web/app.py, Memory MCP server |
| `memory/dedup.py` | vault.py (pre-write check), Orchestrator (cleanup route) |
| `tools/gmail_tools.py` | Orchestrator, web/app.py, Gmail MCP server |
| `orchestrator.py` | web/app.py only |
| `web/app.py` | Frontend only |
| `web/static/index.html` | Browser only (no backend impact) |
| Individual agent | Orchestrator only |
