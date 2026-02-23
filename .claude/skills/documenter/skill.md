---
name: documenter
description: Maintain project roadmap and living documentation after feature completion or structural changes. Use when completing features, modifying architecture, changing schemas, adding endpoints, updating auth, events, config, or dependencies.
---

You are responsible for keeping the project roadmap and documentation in sync with the codebase. This skill has two parts: roadmap maintenance (after any feature completion) and doc updates (after structural changes).

---

## Part 1: Roadmap

Source of truth: **docs/roadmap.md**

### Format

```markdown
## Phase N: [Name]
[One-sentence goal]

- [x] N.1 Feature description
- [x] N.2 Feature description
- [ ] N.3 Feature description
```

- Phases numbered sequentially, ordered by dependency/priority
- Each phase should deliver standalone value and span 1–3 weeks
- Features use hierarchical numbering: `N.M` (Phase.Feature)
- Checkboxes: `- [x]` done, `- [ ]` pending

### After completing a feature

1. Mark the feature `- [x]` in roadmap immediately
2. If that completes the entire phase, add `✅ Completed [YYYY-MM-DD]` below the phase goal
3. If the change was structural, continue to Part 2

### On scope changes

- Keep numbering sequential with no gaps — renumber if you remove or defer items
- If deferring a feature to a later phase, remove it from the current phase and append it to the target phase, then renumber both
- Split any phase that grows beyond 10–12 features

---

## Part 2: Documentation

Living docs live in `/docs`. Use Markdown with Mermaid diagrams. Docs must stay synced with code.

See [reference.md](reference.md) for the full doc file table (what each file covers, when to update it).

### Update rules

After any structural change — new service, endpoint, schema migration, integration, auth change, event/queue, config key, or dependency shift — update **all** affected doc files before considering the work complete.

- Keep entries concise — prefer Mermaid diagrams over long prose
- Never let docs drift from implementation
- When in doubt, update
- ADRs (`decisions/YYYY-MM-DD-short-title.md`) are append-only: never edit past ADRs, write a new one that supersedes

### Post-change checklist

After a structural change, walk this list and update every affected file:

- [ ] `architecture-overview.md`
- [ ] `data-flow.md`
- [ ] `data-model.md`
- [ ] `api-surface.md`
- [ ] `state-machines.md`
- [ ] `auth-flow.md`
- [ ] `event-flow.md`
- [ ] `config-map.md`
- [ ] `dependency-graph.md`
- [ ] `error-handling.md`
- [ ] `decisions/YYYY-MM-DD-title.md` (if an architectural decision was made)

Not every change touches every file. Use judgment — but bias toward updating.


