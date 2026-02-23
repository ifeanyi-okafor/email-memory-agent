\# Documentation File Reference



Each file lives in `/docs` unless otherwise noted. Claude reads this file for detailed guidance on what each doc covers and when to update it.



| File | Purpose | Update when... |

|---|---|---|

| `architecture-overview.md` | Top-level system map: services, databases, caches, external APIs, integrations. Include a high-level Mermaid component diagram. | Adding/removing a service, database, cache, or external integration |

| `data-flow.md` | Data lifecycle: ingestion → transform → storage → output. Mermaid flowcharts for each major pipeline. | Adding a new data source, transform step, or output sink |

| `data-model.md` | All persistent data: databases, tables/collections, relationships, key fields, indexes, engine assignments. | Any schema change, migration, new table/collection, or index change |

| `api-surface.md` | All endpoints (internal + external): method, path, description, auth required, request/response shape, owning service. Also third-party APIs consumed: rate limits, failure modes, retry policy. | Adding/changing/removing an endpoint, or integrating a new external API |

| `state-machines.md` | Entity lifecycles: states, transitions, triggers, side effects. Mermaid state diagrams. Covers conversations, sessions, onboarding flows, jobs, agent tasks, etc. | Adding a new stateful entity or modifying state transitions |

| `auth-flow.md` | Auth/authz architecture: authentication methods, token lifecycle, tenant isolation (API/DB/files/queues), middleware and guards. Security-critical for multi-tenant systems. | Changing auth methods, token handling, tenant isolation, or adding new permission scopes |

| `event-flow.md` | Async communication: events/messages/jobs on queues/bus/pubsub. Document publisher, subscriber, payload shape, delivery guarantees, failure handling. Include webhooks. | Adding a new event, queue, topic, webhook, or changing delivery guarantees |

| `config-map.md` | All environment variables, feature flags, and config values: name, purpose, required/optional, default value, per-environment differences. | Adding/removing env vars, feature flags, or config values |

| `dependency-graph.md` | Internal module/service dependencies (not npm/pip packages). Call direction, blast radius analysis. Mermaid flowcharts. | Changing which services/modules call each other, or introducing new internal dependencies |

| `error-handling.md` | Failure strategy: caught vs propagated errors, retry/backoff policies, DLQ setup, circuit breakers, logging/alerting, user-facing error responses. | Adding a new integration/service, changing retry logic, or modifying error response format |

| `decisions/YYYY-MM-DD-short-title.md` | Architecture Decision Records. Sections: Context, Options Considered, Decision, Reasoning. Append-only — never edit a past ADR, write a new one that supersedes it. | Making an architectural choice, adopting/replacing technology, or any non-obvious tradeoff |

