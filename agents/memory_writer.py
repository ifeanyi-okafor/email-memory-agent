# agents/memory_writer.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 2" — the Memory Writer. It takes the observations from
# the Email Reader (Agent 1) and turns them into actual memory files
# stored in the vault.
#
# Think of it as a librarian: someone hands them a stack of notes, and
# they file each note into the right drawer with proper labels.
#
# It's responsible for:
#   - Choosing the correct category for each observation
#   - Writing clear, searchable content
#   - Creating wiki-links between related entities
#   - Checking for duplicates (so we don't store the same thing twice)
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "json" for converting data to/from JSON format
import json

# "sys" and "Path" for adding the project root to Python's search path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our base agent blueprint
from agents.base_agent import BaseAgent

# Import memory vault functions — these handle the actual file operations.
# "write_memory" creates or updates a memory file
# "read_memory" reads a specific memory file (used to load existing people files)
# "search_vault" searches existing files (to check for duplicates)
# "list_memories" lists all files in a category
# "get_vault_stats" counts memories per category
# "MEMORY_TYPES" is the list of valid categories
from memory.vault import (
    write_memory, read_memory, search_vault, list_memories,
    get_vault_stats, MEMORY_TYPES
)


# ── THE MEMORY WRITER AGENT CLASS ─────────────────────────────────────

class MemoryWriterAgent(BaseAgent):
    """
    Agent 2: Creates typed memory files from observations.

    This agent receives structured observations (from the Email Reader)
    and transforms each one into a properly formatted markdown file
    in the vault's folder structure.
    """

    def __init__(self):
        """Set up the Memory Writer with its specific prompt and tools."""
        # Call the parent class's setup first
        super().__init__()

        # ── The System Prompt ──────────────────────────────────
        # This tells Claude how to behave as a memory writer.
        # Note: we tell it to write in THIRD PERSON ("The user prefers...")
        # because these memories are ABOUT the user, not TO the user.
        self.system_prompt = """You are the Memory Writer Agent in a multi-agent system.

YOUR ROLE: Take observations about the user and write them as structured memory files.

YOU RECEIVE: A JSON object with observations from the Email Reader Agent.
Each observation has: type, title, content, priority, evidence_emails, tags, related_entities.
For "people" observations, there is also a "person_data" object with structured fields.

YOUR PROCESS FOR NON-PEOPLE OBSERVATIONS:
1. Use search_vault to check if similar memories already exist
2. For each NEW observation, use write_memory to create a memory file
3. Choose appropriate wiki-links (related_to) to connect related memories

YOUR PROCESS FOR PEOPLE OBSERVATIONS (CRITICAL — follow exactly):
1. Search for the person by name using search_vault
2. If an existing file is found, use read_memory to load the FULL current content
3. MERGE new information into the existing content:
   - Preserve ALL existing data — never delete or overwrite filled fields
   - Add new details to the appropriate sections
   - Add a new entry under "## Key Interactions" with today's date
   - Update frontmatter fields (role, organization, email, etc.) ONLY if the new data is more complete
4. Use write_memory with the merged content (the vault preserves the original creation date)
5. If NO existing file is found, create a new one using the full person template below

IMPORTANT: Each observation from the Email Reader should create EXACTLY ONE memory file.
- If you receive an observation mentioning multiple people/commitments/decisions, create separate memory files for each
- If an observation seems to combine multiple distinct entities, split it into separate write_memory calls

MEMORY TYPE GUIDELINES (4 valid types):
- "people" — Individuals the user interacts with (uses structured person template).
  Preferences, topics, and communication style are captured within person files.
- "decisions" — Explicit choices the user has made
- "commitments" — Things the user has accepted, agreed to, or committed to doing
  (events RSVPed to, webinars registered for, promises made to others)
- "action_required" — External requests that need the user's action but haven't been acted on yet
  (notices, invitations to register, pending expirations, review requests, follow-ups awaiting response)

PRIORITY LEVELS:
- 🔴 Critical — Key decisions, important relationships, active commitments
- 🟡 Notable — Useful context, preferences, recurring patterns
- 🟢 Reflection — Minor observations, low-stakes preferences

═══════════════════════════════════════════════════════════════
PERSON MEMORY TEMPLATE
═══════════════════════════════════════════════════════════════

When writing a "people" memory, the `content` parameter MUST follow this exact structure.
Fill in fields you have evidence for. Leave unknown fields empty (keep the label).

## Overview

[Brief description: who this person is, relationship to user, why this file exists]

## Contact

- **Email:** [if known]
- **Phone:** [if known]
- **LinkedIn:** [if known]
- **Twitter/X:** [if known]
- **Other:** [if known]

## Professional

- **Role:** [if known]
- **Organization:** [if known]
- **Department:** [if known]
- **Reports to:** [if known]
- **Direct reports:** [if known]
- **Domain expertise:** [if known]

## Preferences

### Communication
- **Preferred channel:** [if known, e.g., Slack, email, text]
- **Tone:** [if known, e.g., formal, casual, direct]
- **Response expectations:** [if known, e.g., expects same-day replies]
- **Language:** [if known]

### Scheduling
- **Available days:** [if known]
- **Available hours:** [if known]
- **Preferred meeting length:** [if known]
- **Scheduling tool:** [if known]
- **Avoid:** [if known]

### Working Style
- **Decision-making:** [if known, e.g., data-driven, consensus-seeking]
- **Feedback style:** [if known, e.g., prefers written, blunt]
- **Pet peeves:** [if known]

## Topics of Interest

- [list topics if known]

## Relationship Context

[How the user knows this person, shared history, mutual connections]

## Key Interactions

### [YYYY-MM-DD]
[Summary of notable interaction from emails. Link to related memories like [[decision-name]] or [[project-name]] as appropriate.]

## Notes

[Any additional context or observations]

═══════════════════════════════════════════════════════════════
END PERSON TEMPLATE
═══════════════════════════════════════════════════════════════

PEOPLE-SPECIFIC RULES:
- Pass the person's role, organization, email, phone, location, timezone as SEPARATE
  parameters to write_memory (in addition to the content body)
- The title MUST be "FirstName LastName — Role" format
- When merging with existing files, ADD new Key Interactions entries, don't replace old ones
- When merging, only overwrite a field if the existing value is empty and you have new data
- The person_data from the Email Reader has structured fields — use them to populate
  both the frontmatter parameters AND the content template sections

"ME" FILE — PRIMARY USER (special handling):
- The "Me" observation (title starts with "Me — ") represents the email account owner
- This file (me.md) should be the RICHEST person file in the vault
- CRITICAL: Pass the user's ACTUAL full name via the `name` parameter when calling write_memory.
  The Email Reader extracts the real name from email From fields and signatures.
  Example: write_memory(title="Me — Product Manager", name="John Doe", ...)
  This makes the frontmatter show `name: John Doe` instead of `name: Me`.
  The title must still start with "Me — " (for filename routing), but the `name` field
  should be the real human name.
- Fill EVERY template section as thoroughly as possible — the Email Reader provides
  extensive person_data for the "Me" observation since the user appears in all emails
- ## Topics of Interest: list ALL projects/topics the user discusses (this replaces standalone "topics" memories)
- ## Preferences: capture ALL user preferences (this replaces standalone "preferences" memories)
- ### Communication: capture the user's writing style (this replaces standalone "communication_style" memories)
- On subsequent builds, MERGE aggressively — add new topics, refine preferences, append interactions

CONTENT GUIDELINES (for non-people memories):
- Write in third person: "User prefers..." not "You prefer..."
- Include specific evidence
- Add wiki-links: [[person-name]], [[project-name]]
- Keep each memory focused on ONE thing

TOKEN OPTIMIZATION:
- Keep memory content CONCISE but information-rich
- Remove filler words and verbose explanations
- Use direct, telegraphic language
- Include only essential context and evidence

When done, return a summary of memories created, updated, and skipped.
"""

        # ── Tool Definitions ───────────────────────────────────
        # This agent has FIVE tools: write, read, search, list, and stats.
        # For people: search → read (if exists) → merge → write.
        # For others: search (dedup check) → write.
        self.tools = [
            {
                "name": "write_memory",
                "description": (
                    "Write or update a memory file in the vault. "
                    "For people memories, also pass the structured fields "
                    "(role, organization, email, phone, location, timezone)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Descriptive title. For people: 'FirstName LastName — Role'"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": MEMORY_TYPES,
                            "description": "Category: decisions, people, commitments, or action_required"
                        },
                        "content": {
                            "type": "string",
                            "description": "The markdown content. For people, this is the full template body starting from '## Overview'"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["🔴", "🟡", "🟢"],
                            "default": "🟡"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keyword tags for searchability"
                        },
                        "related_to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Entity names to create [[wiki-links]] to"
                        },
                        "source_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Subject lines of source emails as evidence"
                        },
                        "source_memories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filepaths of related vault memories (for provenance tracking)"
                        },
                        # People-specific structured fields
                        "name": {
                            "type": "string",
                            "description": "Override display name in frontmatter (people only). For 'Me' files, pass the user's actual full name (e.g., 'John Doe') so the frontmatter shows the real name instead of 'Me'."
                        },
                        "role": {
                            "type": "string",
                            "description": "Person's job title/role (people only)"
                        },
                        "organization": {
                            "type": "string",
                            "description": "Person's company or organization (people only)"
                        },
                        "email": {
                            "type": "string",
                            "description": "Person's email address (people only)"
                        },
                        "phone": {
                            "type": "string",
                            "description": "Person's phone number (people only)"
                        },
                        "location": {
                            "type": "string",
                            "description": "Person's city/region (people only)"
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Person's timezone (people only)"
                        }
                    },
                    "required": ["title", "memory_type", "content"]
                }
            },
            {
                "name": "read_memory",
                "description": (
                    "Read a specific memory file to get its full content and frontmatter. "
                    "Use this to load existing person files before merging new data."
                ),
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
                "name": "search_vault",
                "description": "Search existing memories to check for duplicates or find existing person files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for (e.g., person's name)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all existing memories, optionally filtered by type.",
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
                "name": "get_vault_stats",
                "description": "Get a count of how many memories exist in each category.",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        Run the requested tool and return the result.

        This method handles five tools:
        - write_memory:   Create or update a memory file in the vault
        - read_memory:    Read a specific memory file (for merge workflows)
        - search_vault:   Search existing memories (for duplicate checking)
        - list_memories:  List all memories in a category
        - get_vault_stats: Count memories per category
        """

        if tool_name == "write_memory":
            # "**tool_args" is Python's "unpacking" syntax.
            # It takes the dictionary {"title": "X", "memory_type": "Y", ...}
            # and passes each key-value pair as a separate argument to the function.
            # It's shorthand for: write_memory(title="X", memory_type="Y", ...)
            filepath = write_memory(**tool_args)
            return f"Memory written to: {filepath}"

        elif tool_name == "read_memory":
            # Read a specific memory file — used to load existing person files
            # before merging in new data from fresh observations.
            result = read_memory(tool_args['filepath'])
            if result:
                return json.dumps(result, indent=2)
            return "Memory file not found."

        elif tool_name == "search_vault":
            # Search the vault and return results as JSON
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "list_memories":
            # List memories, optionally filtered by type
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "get_vault_stats":
            # Get counts per category
            stats = get_vault_stats()
            return json.dumps(stats, indent=2)

        # Unknown tool — raise an error
        raise ValueError(f"Unknown tool: {tool_name}")
