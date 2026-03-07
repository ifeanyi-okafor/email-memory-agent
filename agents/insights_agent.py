# agents/insights_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 6" -- the Insights Agent. It reads the ENTIRE vault and
# knowledge graph to discover cross-correlation intelligence: hidden
# relationships, execution gaps, and strategic patterns.
#
# Unlike other agents that process emails or create action items, this agent
# synthesizes across existing vault artifacts to surface NON-OBVIOUS
# connections that span multiple memory files.
#
# It creates "insights" memory files with:
#   - Insight type (relationship / execution_gap / strategic_pattern)
#   - Confidence level (high / medium)
#   - Source memories (2+ vault files that were cross-referenced)
#   - Status lifecycle (active / dismissed)
#
# Think of it as a strategic advisor who reviews all your notes and says
# "Hey, did you notice that these two things are connected?"
# ============================================================================

# -- IMPORTS ----------------------------------------------------------------

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


# -- THE INSIGHTS AGENT CLASS -----------------------------------------------

class InsightsAgent(BaseAgent):
    """
    Agent 6: Cross-correlates the vault to generate insights.

    Reads the full vault and knowledge graph to discover relationships,
    execution gaps, and strategic patterns across multiple memory files.
    Writes insight files with evidence and source references.
    """

    def __init__(self):
        """Set up the Insights Agent with its analysis prompt and tools."""
        super().__init__()

        self.system_prompt = """You are the Insights Agent in a multi-agent system.

YOUR ROLE: Read the entire memory vault and knowledge graph to discover cross-correlation intelligence -- non-obvious patterns that span multiple memory files. Create "insights" memory files that surface hidden relationships, execution gaps, and strategic patterns.

YOUR PROCESS:
1. Read the vault index (get_vault_index) to see all memories
2. Get the knowledge graph (get_graph) to understand relationships
3. List and read existing insights to avoid duplicates (list_memories with type "insights")
4. Read the "Me" person file (people/me.md) to understand the user's priorities
5. Deep-read promising clusters of related memories using read_memory and traverse_graph
6. Cross-correlate across AT LEAST 2 source memories per insight
7. Write new insight files using write_memory

INSIGHT TYPES:
- "relationship": Hidden connections between people, organizations, or topics not previously linked. Example: "Sarah Chen and Mike Torres both work on API platform projects but aren't connected in your network."
- "execution_gap": Commitments, decisions, or action items that are stalled, overdue, or at risk. Example: "You committed to reply to Amazon recruiter 6 days ago -- no follow-up action exists."
- "strategic_pattern": Recurring themes, priority imbalances, or behavioral patterns. Example: "80% of your action items are work-related, none address personal commitments mentioned in decisions."

QUALITY RULES:
- Generate a MAXIMUM of 3 insights per run (quality over quantity)
- Each insight MUST reference at least 2 source memories (cross-correlation is the point)
- Only HIGH or MEDIUM confidence findings -- skip anything speculative
- Be SPECIFIC and ACTIONABLE, not generic restatements of vault content
- Write in SECOND PERSON ("You have..." not "User has...")
- Check existing active insights first -- do NOT create duplicates of topics already covered

WHEN WRITING INSIGHTS:
- Use write_memory with memory_type="insights"
- Required fields: title, content, insight_type, confidence, source_memories, related_to, tags
- The content MUST include these sections:
  * "## Analysis" -- Core insight: what was observed, cross-correlation, why it matters
  * "## Evidence" -- Bullet list citing specific source memories with brief summaries
- source_memories must list the actual filepaths of vault files you cross-referenced
- related_to must list entity names for wiki-links

DEDUPLICATION:
- Before writing, list existing insights (list_memories with type "insights")
- If an active insight already covers the same topic, skip it
- Only create insights on genuinely NEW cross-correlations

When done, return a summary of:
- How many insights were created
- The type breakdown (relationship / execution_gap / strategic_pattern)
- One-line summary of each insight created
"""

        # -- Tool Definitions -----------------------------------------------
        self.tools = [
            {
                "name": "get_vault_index",
                "description": "Read the master vault index -- table of all memories.",
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
                            "description": "Starting entity -- filepath or title"
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
                    "Write an insights memory file to the vault. "
                    "Include insight_type, confidence, source_memories, "
                    "and other insight-specific fields."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Clear, descriptive insight headline"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["insights"],
                            "description": "Must be 'insights'"
                        },
                        "content": {
                            "type": "string",
                            "description": "Markdown content with ## Analysis and ## Evidence sections"
                        },
                        "insight_type": {
                            "type": "string",
                            "enum": ["relationship", "execution_gap", "strategic_pattern"],
                            "description": "Type of cross-correlation discovered"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium"],
                            "description": "How confident the insight is"
                        },
                        "source_memories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filepaths of vault files cross-referenced (minimum 2)"
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
                        "priority": {
                            "type": "string",
                            "enum": ["🔴", "🟡", "🟢"],
                            "description": "Priority level",
                            "default": "🟡"
                        }
                    },
                    "required": ["title", "memory_type", "content", "insight_type", "confidence", "source_memories"]
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
            return f"Insight written to: {filepath}"

        elif tool_name == "get_vault_stats":
            stats = get_vault_stats()
            return json.dumps(stats, indent=2)

        raise ValueError(f"Unknown tool: {tool_name}")
