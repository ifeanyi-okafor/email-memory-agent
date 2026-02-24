# agents/reconciliation_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# The Reconciliation Agent compares open action items from the vault against
# sent Gmail messages to determine which actions have been addressed.
#
# It uses a hybrid approach:
#   1. Heuristic matching — subject/recipient overlap (fast, free)
#   2. LLM analysis — for items the heuristic can't resolve (accurate, costs API)
#   3. Expiry check — past-deadline items marked as expired
#
# Status values: active, closed, expired
# ============================================================================

import json
from datetime import datetime

from agents.base_agent import BaseAgent


# -- HEURISTIC MATCHING ----------------------------------------------------

def heuristic_match(action: dict, sent_emails: list[dict]) -> dict | None:
    """
    Try to match an action item against sent emails using simple heuristics.

    Checks:
    1. Subject overlap: does any sent email subject match a source_email?
    2. Recipient overlap: does any sent email go to someone in related_to?

    Args:
        action:      Dict with 'source_emails' and 'related_to' lists.
        sent_emails: List of dicts with 'subject', 'to', 'date' fields.

    Returns:
        Dict with 'reason' and 'date' if match found, None otherwise.
    """
    source_subjects = [s.lower() for s in (action.get('source_emails') or [])]
    related_entities = [e.lower() for e in (action.get('related_to') or [])]

    for email in sent_emails:
        subject = (email.get('subject') or '').lower()
        recipient = (email.get('to') or '').lower()
        date = email.get('date', '')

        # Check 1: Subject overlap
        for source_subj in source_subjects:
            # Strip Re:, Fwd:, etc. and compare
            clean_source = source_subj.replace('re:', '').replace('fwd:', '').strip()
            clean_sent = subject.replace('re:', '').replace('fwd:', '').strip()
            if clean_source and clean_sent and (
                clean_source in clean_sent or clean_sent in clean_source
            ):
                return {
                    'reason': f"Sent email matching '{email.get('subject', '')}' on {date}",
                    'date': date,
                }

        # Check 2: Recipient matches related_to entity
        for entity in related_entities:
            entity_parts = entity.split()
            if all(part in recipient for part in entity_parts):
                return {
                    'reason': f"Sent email to {email.get('to', '')} on {date}",
                    'date': date,
                }

    return None


def check_expiry(deadline: str | None) -> bool:
    """
    Check if a deadline has passed.

    Args:
        deadline: Date string in YYYY-MM-DD format, or empty/None.

    Returns:
        True if the deadline is strictly in the past, False otherwise.
    """
    if not deadline:
        return False
    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
        return deadline_date < datetime.now().date()
    except (ValueError, TypeError):
        return False


# -- THE RECONCILIATION AGENT ---------------------------------------------

class ReconciliationAgent(BaseAgent):
    """
    Compares open action items against sent emails to update statuses.

    Uses Memory MCP tools (search_vault, read_memory, write_memory) and
    Gmail MCP tools (fetch_sent_emails) to:
    1. Find active action items
    2. Fetch recent sent emails
    3. Match them (heuristic + LLM)
    4. Update statuses in the vault
    """

    def __init__(self):
        super().__init__()
        self.system_prompt = (
            "You are an action item reconciliation agent. Your job is to determine "
            "which action items have been addressed by comparing them against sent emails.\n\n"
            "You will be given:\n"
            "- A list of open action items (with titles, deadlines, related people, source emails)\n"
            "- A list of recently sent emails (with subjects, recipients, dates)\n\n"
            "For each action item, determine if any sent email indicates the action was taken.\n"
            "Be generous in matching — if someone sent an email to the right person about a "
            "related topic, that likely addresses the action item.\n\n"
            "Respond with a JSON array of updates:\n"
            "[\n"
            '  {"filepath": "action_required/filename.md", "status": "closed", '
            '"status_reason": "Sent email to Jake about timeline on 2026-02-22"}\n'
            "]\n\n"
            "Only include items whose status should change. If an item remains active, omit it."
        )

        self.tools = [
            {
                "name": "search_vault",
                "description": "Search across all memories using text matching.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            },
            {
                "name": "read_memory",
                "description": "Read a specific memory file in full.",
                "input_schema": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all memories, optionally filtered by type.",
                "input_schema": {
                    "type": "object",
                    "properties": {"memory_type": {"type": "string"}}
                }
            },
            {
                "name": "write_memory",
                "description": "Update a memory file in the vault. Use to update status fields.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "memory_type": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["active", "closed", "expired"]},
                        "status_reason": {"type": "string"},
                        "status_updated": {"type": "string"},
                        "quadrant": {"type": "string"},
                        "priority_justification": {"type": "string"},
                        "deadline": {"type": "string"},
                        "source_type": {"type": "string"},
                        "source_memories": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "related_to": {"type": "array", "items": {"type": "string"}},
                        "source_emails": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "memory_type", "content"]
                }
            },
            {
                "name": "fetch_sent_emails",
                "description": "Fetch emails the user has SENT. Use to check if user replied to or followed up on action items.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {"type": "integer", "default": 100},
                        "days_back": {"type": "integer", "default": 30}
                    }
                }
            },
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Route tool calls to the appropriate vault/gmail function."""
        from memory.vault import search_vault, read_memory, list_memories, write_memory
        from tools.gmail_tools import fetch_emails

        if tool_name == "search_vault":
            results = search_vault(tool_args['query'])
            return json.dumps(results, indent=2)

        elif tool_name == "read_memory":
            result = read_memory(tool_args['filepath'])
            return json.dumps(result, indent=2)

        elif tool_name == "list_memories":
            results = list_memories(tool_args.get('memory_type'))
            return json.dumps(results, indent=2)

        elif tool_name == "write_memory":
            filepath = write_memory(**tool_args)
            return f"Memory written to: {filepath}"

        elif tool_name == "fetch_sent_emails":
            emails = fetch_emails(
                max_results=tool_args.get('max_results', 100),
                query='in:sent',
                days_back=tool_args.get('days_back', 30),
            )
            return json.dumps(emails, indent=2, default=str)

        raise ValueError(f"Unknown tool: {tool_name}")
