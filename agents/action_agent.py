# agents/action_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 4" — the Action Agent. It reads the ENTIRE vault and
# knowledge graph to identify items that need the user's attention.
#
# It creates "action_required" memory files with:
#   - Eisenhower matrix classification (urgent/important quadrant)
#   - Priority justification based on the full vault context
#   - Links back to the source memories that informed the action
#
# Think of it as a personal assistant who reviews all your notes,
# commitments, and contacts, then produces a prioritized action list.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from memory.vault import (
    write_memory, read_memory, search_vault, list_memories,
    get_vault_index, get_vault_stats, MEMORY_TYPES
)
from memory.graph import get_graph, traverse_graph


# ── THE ACTION AGENT CLASS ──────────────────────────────────────────

class ActionAgent(BaseAgent):
    """
    Agent 4: Reads the full vault and graph to generate prioritized action items.

    This agent reasons across ALL memory categories to determine what
    needs the user's attention, classifies items using the Eisenhower
    matrix, and writes action_required files with justification.
    """

    def __init__(self):
        """Set up the Action Agent with its analysis prompt and tools."""
        super().__init__()

        self.system_prompt = """You are the Action Agent in a multi-agent system.

YOUR ROLE: Read the entire memory vault and knowledge graph to identify items that require the user's attention. Create prioritized "action_required" memory files.

YOUR PROCESS:
1. Read the vault index (get_vault_index) to see all memories
2. Get the knowledge graph (get_graph) to understand relationships
3. List and read commitments, decisions, and people files for full context
4. For each potential action item:
   a. Use traverse_graph to find connected entities (people, decisions, other commitments)
   b. Read the connected memories to build full context
   c. Determine the Eisenhower quadrant based on urgency and importance
   d. Write a justification that references specific vault memories
5. Check for existing action items (search_vault) to avoid duplicates
6. Write new action_required files using write_memory

EISENHOWER MATRIX CLASSIFICATION:
- "urgent-important": Time-sensitive AND directly aligned with user's high-priority decisions or critical relationships. Examples: expiring deadlines on key commitments, follow-ups with high-value contacts, time-sensitive career decisions.
- "important-not-urgent": Aligned with user's goals/values but no immediate deadline. Examples: strengthening key relationships, pursuing strategic opportunities, skill development aligned with decisions.
- "urgent-not-important": Has a deadline or time pressure but tangential to user's core priorities. Examples: routine follow-ups, administrative tasks, low-stakes RSVPs.
- "neither": Low priority, informational, or already partially addressed. Examples: optional networking, minor updates, already-completed items.

CLASSIFICATION RULES:
- ALWAYS read the "Me" person file (people/me.md) first to understand the user's priorities, role, and goals
- Cross-reference with decisions to understand what the user has chosen to prioritize
- Cross-reference with people files to understand relationship importance
- Look at commitment deadlines relative to today's date
- Consider the priority level (🔴/🟡/🟢) of related memories as signals

WHEN WRITING ACTION ITEMS:
- Use write_memory with memory_type="action_required"
- Required fields: title, content, quadrant, priority_justification, source_type, source_memories, related_to, tags
- Optional fields: deadline (if known or inferable), source_emails
- The content MUST include these sections:
  * "## Why This Matters" — context from the vault about why this matters to the user
  * "## Priority Justification" — numbered list explaining the Eisenhower classification
  * "## Recommended Action" — specific, actionable next step
- The priority_justification field in frontmatter should be a concise 1-2 sentence summary
- source_memories must list the actual filepaths of vault files you consulted
- related_to must list entity names for wiki-links

DEDUPLICATION:
- Before writing, search for existing action items with similar titles
- If a similar action item exists, read it and decide:
  * If still relevant: update it (rewrite with current information)
  * If no longer relevant: note this in your summary but don't delete it

SOURCE TYPES:
- "commitment" — action derived from a commitment/promise
- "decision" — action derived from a decision that needs follow-through
- "people" — action derived from a relationship that needs attention
- "email" — action derived directly from email content

When done, return a summary of:
- How many action items were created/updated
- The Eisenhower breakdown (how many in each quadrant)
- Top 3 most urgent items
"""

        # ── Tool Definitions ───────────────────────────────────
        self.tools = [
            {
                "name": "get_vault_index",
                "description": "Read the master vault index — table of all memories.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "search_vault",
                "description": "Search across all memories using text matching.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_memory",
                "description": "Read a specific memory file in full.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string", "description": "Path relative to vault root"}
                    },
                    "required": ["filepath"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all memories, optionally filtered by type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": MEMORY_TYPES,
                            "description": "Filter by category (optional)"
                        }
                    }
                }
            },
            {
                "name": "get_graph",
                "description": "Get the full knowledge graph showing all bidirectional relationships between memories.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "traverse_graph",
                "description": "Find all memories connected to a starting entity within N hops.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Starting entity — filepath or title"
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Max hops (default: 2)",
                            "default": 2
                        }
                    },
                    "required": ["entity"]
                }
            },
            {
                "name": "write_memory",
                "description": (
                    "Write an action_required memory file to the vault. "
                    "Include quadrant, priority_justification, source_memories, "
                    "and other action-specific fields."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Clear, action-oriented title"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["action_required"],
                            "description": "Must be 'action_required'"
                        },
                        "content": {
                            "type": "string",
                            "description": "Markdown content with ## Why This Matters, ## Priority Justification, ## Recommended Action sections"
                        },
                        "quadrant": {
                            "type": "string",
                            "enum": ["urgent-important", "important-not-urgent", "urgent-not-important", "neither"],
                            "description": "Eisenhower matrix classification"
                        },
                        "priority_justification": {
                            "type": "string",
                            "description": "1-2 sentence summary of why this quadrant was chosen"
                        },
                        "deadline": {
                            "type": "string",
                            "description": "Deadline date if known (YYYY-MM-DD format)"
                        },
                        "source_type": {
                            "type": "string",
                            "enum": ["commitment", "decision", "people", "email"],
                            "description": "Which vault category surfaced this action"
                        },
                        "source_memories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filepaths of vault files consulted (e.g., 'people/jake-8340.md')"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keyword tags"
                        },
                        "related_to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Entity names for [[wiki-links]]"
                        },
                        "source_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Source email subjects (if applicable)"
                        }
                    },
                    "required": ["title", "memory_type", "content", "quadrant", "priority_justification", "source_type"]
                }
            },
            {
                "name": "get_vault_stats",
                "description": "Get summary counts of memories per category.",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Run the requested tool and return the result."""

        if tool_name == "get_vault_index":
            return get_vault_index()

        elif tool_name == "search_vault":
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "read_memory":
            result = read_memory(tool_args['filepath'])
            if result:
                return json.dumps(result, indent=2)
            return "Memory file not found."

        elif tool_name == "list_memories":
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "get_graph":
            graph = get_graph()
            return json.dumps(graph, indent=2)

        elif tool_name == "traverse_graph":
            result = traverse_graph(
                entity=tool_args['entity'],
                max_depth=tool_args.get('max_depth', 2)
            )
            return json.dumps(result, indent=2)

        elif tool_name == "write_memory":
            filepath = write_memory(**tool_args)
            return f"Action item written to: {filepath}"

        elif tool_name == "get_vault_stats":
            stats = get_vault_stats()
            return json.dumps(stats, indent=2)

        raise ValueError(f"Unknown tool: {tool_name}")
