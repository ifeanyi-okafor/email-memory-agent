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

    email_reader --> base_agent[agents/base_agent.py]
    memory_writer --> base_agent
    query_agent --> base_agent

    base_agent --> settings

    gmail_tools --> settings
    vault --> settings
```

## Blast Radius Analysis

| Module Changed | Affected Components |
|---------------|-------------------|
| `config/settings.py` | All agents, vault, gmail_tools, orchestrator |
| `agents/base_agent.py` | All three agents |
| `memory/vault.py` | Orchestrator, web/app.py, Memory MCP server |
| `tools/gmail_tools.py` | Orchestrator, web/app.py, Gmail MCP server |
| `orchestrator.py` | web/app.py only |
| `web/app.py` | Frontend only |
| `web/static/index.html` | Browser only (no backend impact) |
| Individual agent | Orchestrator only |
