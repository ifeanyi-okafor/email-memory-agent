# agents/query_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 3" — the Query Agent. It's the one users interact with
# directly through the chat interface.
#
# When you type a question like "Who do I email the most?", this agent:
#   1. Reads the vault index (table of contents) to see what's available
#   2. Searches for relevant memories using text matching
#   3. Reads the full content of matching memory files
#   4. Synthesizes a natural, conversational answer
#
# It speaks as if it "knows" you: "Based on your emails, you tend to..."
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "json" for formatting data as JSON strings
import json

# "sys" and "Path" for project path setup
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the base agent blueprint
from agents.base_agent import BaseAgent

# Import memory vault reading/searching functions.
# Note: this agent does NOT import "write_memory" — it only READS.
# That's by design: the Query Agent should never modify the vault.
from memory.vault import (
    search_vault, read_memory, list_memories,
    get_vault_index, get_vault_stats, MEMORY_TYPES
)


# ── THE QUERY AGENT CLASS ─────────────────────────────────────────────

class QueryAgent(BaseAgent):
    """
    Agent 3: The conversational interface to the memory vault.

    This agent READS the vault and ANSWERS questions. It never writes.
    It has five tools, all read-only:
        - get_vault_index: See the table of contents
        - search_vault:    Find memories by keyword
        - read_memory:     Read a specific memory file in full
        - list_memories:   List all memories (with optional type filter)
        - get_vault_stats: Get counts per category
    """

    def __init__(self):
        """Set up the Query Agent with its chat-oriented prompt and read-only tools."""
        # Call the parent class's setup
        super().__init__()

        # ── The System Prompt ──────────────────────────────────
        # This prompt tells Claude to act as a knowledgeable companion
        # who "knows" the user based on their memory vault.
        # Key instruction: speak in SECOND PERSON ("You tend to...").
        self.system_prompt = """You are the Query Agent — the conversational interface to a memory vault.

The memory vault contains structured memories about a person, extracted from their emails.
Memories are organized by type: decisions, people, commitments.
Preferences, topics of interest, and communication style are captured within person files.

YOUR ROLE: Answer questions about the person using their memory vault.

YOUR PROCESS:
1. First, read the vault index (get_vault_index) to understand what's available
2. Search for relevant memories using search_vault
3. Read specific memories using read_memory for detailed answers
4. Synthesize a natural, conversational answer

RESPONSE STYLE:
- Speak about the user in second person: "You tend to prefer..."
- Always cite which memories support your answer
- If the vault doesn't contain relevant info, say so honestly
- Connect related insights when possible
- Be specific — quote evidence from memories
"""

        # ── Tool Definitions ───────────────────────────────────
        # All five tools are READ-ONLY — they retrieve data from the
        # vault but never modify it.
        self.tools = [
            {
                "name": "get_vault_index",
                "description": "Read the master vault index — a table of all memories with one-line descriptions. Use this first to see what's available.",
                "input_schema": {"type": "object", "properties": {}}
                # No input parameters needed — it just reads the index file
            },
            {
                "name": "search_vault",
                "description": "Search across all memories using text matching. Returns matching memories with a snippet of context around the match.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for (case-insensitive)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_memory",
                "description": "Read the full content of a specific memory file, including its YAML frontmatter and markdown body.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filepath": {
                            "type": "string",
                            "description": "Path relative to vault root (e.g., 'people/sarah-chen-a1b2.md')"
                        }
                    },
                    "required": ["filepath"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all memories with basic info (title, type, date, tags). Optionally filter by memory type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": MEMORY_TYPES,
                            "description": "Filter to only this type (optional)"
                        }
                    }
                }
            },
            {
                "name": "get_vault_stats",
                "description": "Get summary counts — how many memories exist in each category.",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        Run the requested read-only tool and return the result.

        All tools here ONLY READ from the vault — they never modify it.
        """

        if tool_name == "get_vault_index":
            # Read and return the full index file as text
            return get_vault_index()

        elif tool_name == "search_vault":
            # Search all memories for the query text
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "read_memory":
            # Read one specific memory file
            result = read_memory(tool_args['filepath'])
            return json.dumps(result, indent=2)

        elif tool_name == "list_memories":
            # List memories, optionally filtered by type
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "get_vault_stats":
            # Return counts per category
            stats = get_vault_stats()
            return json.dumps(stats, indent=2)

        # Unknown tool — raise an error
        raise ValueError(f"Unknown tool: {tool_name}")
