# mcp_servers/memory_server.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is an MCP server that wraps our Memory Vault tools. It lets any
# MCP-compatible AI agent discover and use our vault operations:
# writing memories, searching, reading, listing, and getting stats.
#
# Like gmail_server.py, this is the "production-ready" MCP version.
# Our tutorial agents call vault.py directly (simpler for learning).
# This file shows how to expose vault operations as an MCP server.
#
# Run standalone: python -m mcp_servers.memory_server
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

import sys
import json
import asyncio
from pathlib import Path

# Add project root to Python's import path
sys.path.insert(0, str(Path(__file__).parent.parent))

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import our memory vault functions
from memory.vault import (
    initialize_vault,  # Creates the folder structure
    write_memory,      # Creates a new memory file
    search_vault,      # Searches across all memories
    read_memory,       # Reads one specific memory file
    list_memories,     # Lists all memories (optionally by type)
    get_vault_index,   # Reads the master index file
    get_vault_stats,   # Gets counts per memory type
    MEMORY_TYPES       # The list of valid memory categories
)

# Create the MCP server with a descriptive name
server = Server("memory-vault-server")


# ── TOOL LISTING ───────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Advertise all six memory vault tools to connecting clients.

    Each tool has a name, description, and input schema that tells
    the AI agent what arguments it accepts.
    """
    return [
        # Tool 1: Write a new memory
        Tool(
            name="write_memory",
            description="Write a new typed memory file to the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "memory_type": {"type": "string", "enum": MEMORY_TYPES},
                    "content": {"type": "string"},
                    "priority": {"type": "string", "enum": ["🔴", "🟡", "🟢"], "default": "🟡"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "related_to": {"type": "array", "items": {"type": "string"}},
                    "source_emails": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "memory_type", "content"]
            }
        ),

        # Tool 2: Search across all memories
        Tool(
            name="search_vault",
            description="Search across all memories using text matching.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        ),

        # Tool 3: Read one specific memory file
        Tool(
            name="read_memory",
            description="Read a specific memory file in full.",
            inputSchema={
                "type": "object",
                "properties": {"filepath": {"type": "string"}},
                "required": ["filepath"]
            }
        ),

        # Tool 4: List all memories (optionally filtered by type)
        Tool(
            name="list_memories",
            description="List all memories, optionally filtered by type.",
            inputSchema={
                "type": "object",
                "properties": {"memory_type": {"type": "string", "enum": MEMORY_TYPES}}
            }
        ),

        # Tool 5: Read the master index
        Tool(
            name="get_vault_index",
            description="Read the master vault index (table of contents).",
            inputSchema={"type": "object", "properties": {}}
        ),

        # Tool 6: Get statistics
        Tool(
            name="get_vault_stats",
            description="Get summary statistics about the vault.",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


# ── TOOL EXECUTION ─────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle tool calls from MCP clients.

    Routes each tool name to the appropriate vault function.
    """

    if name == "write_memory":
        filepath = write_memory(
            title=arguments['title'],
            memory_type=arguments['memory_type'],
            content=arguments['content'],
            priority=arguments.get('priority', '🟡'),
            tags=arguments.get('tags', []),
            related_to=arguments.get('related_to', []),
            source_emails=arguments.get('source_emails', []),
        )
        return [TextContent(type="text", text=f"Memory written to: {filepath}")]

    elif name == "search_vault":
        results = search_vault(arguments['query'])
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "read_memory":
        result = read_memory(arguments['filepath'])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "list_memories":
        results = list_memories(arguments.get('memory_type'))
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "get_vault_index":
        return [TextContent(type="text", text=get_vault_index())]

    elif name == "get_vault_stats":
        stats = get_vault_stats()
        return [TextContent(type="text", text=json.dumps(stats, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


# ── SERVER STARTUP ─────────────────────────────────────────────────────

async def main():
    """Start the MCP server: initialize vault, then listen on stdio."""
    # Make sure the vault folder structure exists before serving
    initialize_vault()

    # Start listening for MCP messages on stdin/stdout
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)

if __name__ == "__main__":
    asyncio.run(main())
