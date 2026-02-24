# mcp_servers/gmail_server.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is an MCP (Model Context Protocol) server that wraps our Gmail
# tools in the MCP standard. It allows any MCP-compatible AI client to
# discover and call our Gmail functions.
#
# Think of MCP like a USB port — it's a standard plug that lets any
# device (AI agent) connect to any peripheral (tool). This server IS
# the peripheral: it advertises "I can read emails" and waits for
# agents to call it.
#
# HOW IT WORKS:
#   1. Agent connects → asks "what tools do you have?"
#   2. Server responds: "I have read_emails — here's what it does"
#   3. Agent says: "Call read_emails with max_results=50"
#   4. Server calls our gmail_tools.fetch_emails() and returns results
#
# YOU DON'T NEED TO RUN THIS FILE for the tutorial to work.
# Our agents call gmail_tools.py directly (simpler for learning).
# This file shows how to expose those same tools as an MCP server
# for when you're ready to use real MCP transport.
#
# Run standalone: python -m mcp_servers.gmail_server
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "sys" and "Path" for project path setup
import sys
import json
import asyncio
from pathlib import Path

# Add the project root to Python's path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# "Server" is the MCP server class from the official MCP Python SDK.
# It handles the protocol details (JSON-RPC messages, etc.).
from mcp.server import Server

# "stdio_server" provides the stdio transport — communication via
# standard input/output (stdin/stdout). This is the simplest transport:
# the agent starts this server as a subprocess and talks to it via pipes.
from mcp.server.stdio import stdio_server

# "Tool" and "TextContent" are MCP data types.
# "Tool" describes a tool's name, description, and input schema.
# "TextContent" wraps text data to return from a tool call.
from mcp.types import Tool, TextContent

# Import our actual Gmail function
from tools.gmail_tools import fetch_emails

# Create the MCP server instance with a name.
# This name identifies the server when agents connect to it.
server = Server("gmail-server")


# ── TOOL LISTING ───────────────────────────────────────────────────────
# This function is called when an agent asks "what tools do you have?"
# The "@server.list_tools()" decorator registers it as the tool lister.

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Advertise our available tools to any connecting MCP client.

    This is called once when an agent first connects and asks
    "what tools do you have?" We return a list of Tool objects,
    each describing one function the agent can call.

    Returns:
        A list of Tool objects with names, descriptions, and schemas.
    """
    return [
        Tool(
            name="read_emails",
            description=(
                "Fetch emails from the user's Gmail inbox. "
                "Returns a list of emails with subject, sender, date, and body."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum emails to fetch (default: 50)",
                        "default": 50
                    },
                    "query": {
                        "type": "string",
                        "description": "Gmail search query",
                        "default": ""
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch from last N days (default: 30)",
                        "default": 30
                    }
                }
            }
        ),
        Tool(
            name="fetch_sent_emails",
            description=(
                "Fetch emails the user has SENT (from their Sent Mail folder). "
                "Use this to check if the user replied to or followed up on something."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum sent emails to fetch (default: 100)",
                        "default": 100
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch sent emails from last N days (default: 30)",
                        "default": 30
                    }
                }
            }
        ),
    ]


# ── TOOL EXECUTION ─────────────────────────────────────────────────────
# This function is called when an agent says "call this tool with these args."
# The "@server.call_tool()" decorator registers it as the tool executor.

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle an incoming tool call from an MCP client.

    The MCP protocol routes tool calls here. We match on the tool name
    and execute the appropriate function.

    Args:
        name:      Which tool to call (e.g., "read_emails")
        arguments: The arguments the agent provided

    Returns:
        A list of TextContent objects containing the tool's output.
    """
    if name == "read_emails":
        # Call our Gmail fetch function with the provided arguments
        emails = fetch_emails(
            max_results=arguments.get('max_results', 50),
            query=arguments.get('query', ''),
            days_back=arguments.get('days_back', 30),
        )

        # Wrap the results as TextContent (MCP's standard format)
        return [TextContent(
            type="text",
            text=json.dumps(emails, indent=2, default=str)
        )]

    elif name == "fetch_sent_emails":
        emails = fetch_emails(
            max_results=arguments.get('max_results', 100),
            query='in:sent',
            days_back=arguments.get('days_back', 30),
        )
        return [TextContent(
            type="text",
            text=json.dumps(emails, indent=2, default=str)
        )]

    # If the agent asked for a tool we don't have, raise an error
    raise ValueError(f"Unknown tool: {name}")


# ── SERVER STARTUP ─────────────────────────────────────────────────────

async def main():
    """
    Start the MCP server on stdio transport.

    "stdio_server()" creates a transport that reads from stdin and
    writes to stdout. The agent (client) starts this script as a
    subprocess and communicates via those pipes.
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


# This block runs only when you execute the file directly
# (not when it's imported as a module).
if __name__ == "__main__":
    asyncio.run(main())
