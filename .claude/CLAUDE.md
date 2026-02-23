# Project: Email Memory Agent
## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- **Post-Mortem Rule**: If a bug is found in code just written, initiate a 2-minute "Root Cause Analysis" subagent task to identify why the initial plan missed it.
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

## Post-Change Documentation

**MANDATORY**: After completing ANY feature, bug fix, or structural change, invoke `/documenter` (via the Skill tool) before marking work complete. This is not optional — it must run after every implementation task.

Triggers (invoke `/documenter` when any of these happen):
- Adding/removing/renaming agents or MCP servers
- Changing the orchestrator routing logic
- Modifying the memory vault format or structure
- Adding new API endpoints or changing the web layer
- Changing config/settings or environment variables
- Altering data flow between agents
- Adding new frontend pages, components, or navigation changes
- Any change to auth flow or email processing pipeline

## Project-Specific Notes

- Agents share no state — data flows between them as text (email_reader output → memory_writer input)
- The MCP servers (`gmail_server.py`, `memory_server.py`) expose tools; agents consume them
- Memory files use YAML frontmatter + markdown body. Never break this format.
- The orchestrator uses keyword routing — changes to routing logic need careful testing
- Gmail OAuth tokens are stored locally; never commit credentials or token files to git
