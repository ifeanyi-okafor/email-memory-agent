# agents/email_reader.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is "Agent 1" — the Email Reader. Its one job is to fetch your
# emails from Gmail and analyze them for patterns about YOU.
#
# It does NOT create memory files — that's the Memory Writer's job (Agent 2).
# This separation is called "single responsibility" — each agent does
# exactly one thing, and does it well.
#
# WHAT IT PRODUCES:
# A structured JSON object listing observations like:
#   - "This person prefers morning meetings" (preference)
#   - "Sarah Chen is a frequent collaborator" (person)
#   - "User chose React over Vue" (decision)
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "json" lets us convert Python data to/from JSON format.
# We use it to send email data to Claude as a readable string.
import json

# "sys" and "Path" let us add the project root to Python's search path
# so we can import modules from parent directories.
import sys
from pathlib import Path

# This line adds the project root folder to Python's import search path.
# Without this, Python wouldn't know where to find "agents.base_agent"
# or "tools.gmail_tools" when running this file directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our BaseAgent class — the blueprint all agents inherit from.
# "BaseAgent" gives us the agentic loop (the run() method).
from agents.base_agent import BaseAgent

# Import the "fetch_emails" function from our Gmail tools module.
# This is the actual function that talks to Gmail's API.
from tools.gmail_tools import fetch_emails


# ── THE EMAIL READER AGENT CLASS ──────────────────────────────────────

class EmailReaderAgent(BaseAgent):
    """
    Agent 1: Reads emails and extracts observations about the user.

    This class "inherits from" (is built on top of) BaseAgent.
    That means it automatically gets the agentic loop (run() method).
    It just needs to define three things:
        1. Its system prompt (what role Claude plays)
        2. Its tools (what functions it can call)
        3. How to execute those tools
    """

    def __init__(self):
        """
        Set up the Email Reader Agent with its prompt and tools.

        "super().__init__()" calls the BaseAgent's __init__ first,
        which sets up conversation_history and other defaults.
        Then we override the prompt and tools with our specific ones.
        """
        # Call the parent class's setup first
        super().__init__()

        # ── The System Prompt ──────────────────────────────────
        # This is a detailed instruction telling Claude exactly what
        # role to play and what output format to produce.
        # Think of it as a job description for the AI.
        self.system_prompt = """You are the Email Reader Agent in a multi-agent system.

YOUR ROLE: Fetch emails and produce a structured analysis of what they reveal about the user.

WHEN YOU RECEIVE A REQUEST:
1. If emails are already provided in the message, analyze them directly (skip the tool call).
   If no emails are provided, use the read_emails tool to fetch them from Gmail.
2. Analyze the emails for patterns about the user:
   - Who do they communicate with most? (people)
   - What decisions have they made? (decisions)
   - What commitments/promises are mentioned? (commitments)
   - Preferences, topics of interest, and communication style should be captured
     within the relevant person observation's person_data fields (NOT as standalone observations)

OUTPUT FORMAT — Return a JSON object with this structure:
{
    "emails_processed": 25,
    "date_range": "2026-01-18 to 2026-02-18",
    "observations": [
        {
            "type": "decisions",
            "title": "Chose React over Vue for frontend",
            "content": "In March planning emails, user stated React was selected over Vue for the new dashboard. Cited team familiarity and ecosystem.",
            "priority": "🟡",
            "evidence_emails": ["Re: Frontend stack decision", "Architecture meeting notes"],
            "tags": ["engineering", "frontend"],
            "related_entities": ["product-launch"]
        }
    ]
}

FOR "people" OBSERVATIONS ONLY — include an additional "person_data" object:
{
    "type": "people",
    "title": "Alice Smith — Lead Designer",
    "content": "Lead designer at Acme Corp. Collaborates on product mockups weekly.",
    "priority": "🟡",
    "evidence_emails": ["Re: Design review", "Mockup feedback"],
    "tags": ["design", "collaborator"],
    "related_entities": ["product-launch"],
    "person_data": {
        "full_name": "Alice Park",
        "role": "Lead Designer",
        "organization": "Acme Corp",
        "department": "",
        "email": "alice@acme.com",
        "phone": "",
        "location": "San Francisco, CA",
        "timezone": "PT",
        "linkedin": "",
        "twitter": "",
        "reports_to": "",
        "direct_reports": "",
        "domain_expertise": "UI/UX, design systems, accessibility",
        "communication_preferences": "Prefers Slack, casual tone, async-friendly",
        "scheduling_preferences": "Available Mon-Fri 10am-6pm PT, prefers 30-min calls",
        "working_style": "Detail-oriented, prefers written feedback, data-driven",
        "topics_of_interest": ["design systems", "accessibility", "Figma"],
        "relationship_context": "Weekly design review partner since Q3 2025"
    }
}

GRANULARITY RULES (CRITICAL):
- Create ONE observation per PERSON (not one observation for multiple people)
- Create ONE observation per DECISION (not one observation summarizing multiple decisions)
- Create ONE observation per COMMITMENT/PROMISE (each deadline, follow-up, or promise = separate observation)
- DO NOT create standalone "preferences", "topics", or "communication_style" observations.
  Instead, fold this information into the relevant person's person_data:
  * User's preferences → "Me" person observation's person_data (communication_preferences, scheduling_preferences, working_style)
  * Topics of interest → relevant person's person_data.topics_of_interest
  * Communication patterns → relevant person's person_data (communication_preferences, working_style)
- Minimum 3 observations, but create MORE if distinct entities are found
- Use related_entities to LINK observations together, not to group them

SPECIAL OBSERVATION - "ME" (REQUIRED — MOST IMPORTANT OBSERVATION):
- ALWAYS create ONE observation of type "people" about the USER THEMSELVES (the email account owner)
- Title format: "Me — [Primary Role/Title]" (e.g., "Me — Product Manager" or "Me — Software Engineer")
- This MUST be the MOST DETAILED observation you produce. The user appears in EVERY email,
  so you have the most data about them. Mine ALL emails thoroughly for user information:

  IDENTITY (from signatures, From: fields, email headers):
  * Full name — CRITICAL: extract the user's actual first and last name from the "From:" field
    or email signature. Store it in person_data.full_name (e.g., "John Doe")
  * Email address, role/title, organization
  * Location, timezone (from signatures or scheduling context)
  * Phone number, LinkedIn, Twitter/X (from signatures)

  COMMUNICATION STYLE (aggregate across ALL sent emails):
  * Tone: formal vs casual, direct vs diplomatic
  * Typical email length: short/medium/long
  * Response patterns: quick responder vs batched
  * Sign-off style, greeting patterns, emoji usage
  * Preferred channel hints (e.g., "let's take this to Slack")

  PREFERENCES & WORKING STYLE (inferred from ALL emails):
  * Scheduling preferences: preferred meeting times, days, duration
  * Decision-making style: data-driven, consensus-seeking, fast-mover
  * Feedback style: written, verbal, structured, blunt
  * Tools/platforms mentioned (Slack, Notion, Figma, etc.)

  TOPICS & EXPERTISE (aggregated from ALL email subjects and content):
  * Every distinct project, product, or initiative discussed
  * Recurring themes and domains (AI, product management, design, etc.)
  * Professional interests and focus areas

  RELATIONSHIPS (from email patterns):
  * Key collaborators and how frequently they appear
  * Professional network context

- Include a full "person_data" object with ALL of the above fields populated
- person_data.full_name MUST contain the user's actual first and last name (from the "From:" header or signature)
- relationship_context: "This is the email account owner"
- Priority: 🔴 (critical - this is the primary user file)

TOKEN OPTIMIZATION:
- Keep content BRIEF but information-dense
- Use concise language: "Works with X on Y project" not "The user works with X who is a colleague on the Y project"
- Include only essential details and evidence
- Avoid verbose explanations

TITLE FORMAT RULES:
- For "people": MUST be "FirstName LastName — Role/Relationship" (e.g., "Oji Udezue — Business Partner")
  NOT "Relationship with Person" or "Person is a..."
- For "commitments": Brief action + deadline (e.g., "Review PR #247 by Friday")
- For "decisions": What was decided (e.g., "Chose React over Vue for frontend")

REQUIRED DATA FIELDS:
- For "people" observations: MUST include "person_data" object with ALL available structured fields
  * Extract email, phone, role, organization from signatures and email headers
  * Infer communication preferences, scheduling patterns, working style from email behavior
  * Note topics of interest from email subjects and content
  * Capture relationship context (how user knows this person)
- For "commitments" observations: MUST include date, time, and venue/location if mentioned
- For all observations: Include specific evidence from emails

EXAMPLES:
Always create a "Me" observation first (note: full_name is REQUIRED — extract from From: field or signature):
  { "type": "people", "title": "Me — Senior Product Manager", "content": "Product manager at TechCorp. Based in Austin, TX. Focus on AI/ML products and developer tools.", "priority": "🔴", "tags": ["self", "identity"], "person_data": { "full_name": "John Doe", "role": "Senior Product Manager", "organization": "TechCorp", "email": "john.doe@techcorp.com", "location": "Austin, TX", "timezone": "CT", "domain_expertise": "AI/ML products, developer tools", "topics_of_interest": ["AI/ML", "developer tools", "local tech community"], ... }, ... }

If emails mention Alice (alice@acme.com), Bob (bob@eng.io), and Carol:
  { "type": "people", "title": "Alice Smith — Designer", "content": "Lead designer at Acme. Collaborates on product mockups.", "priority": "🟡", "person_data": { "role": "Lead Designer", "organization": "Acme", "email": "alice@acme.com", "communication_preferences": "Prefers async communication", ... }, ... }
  { "type": "people", "title": "Bob Jones — Engineer", "content": "Senior engineer at Eng.io. Code review partner.", "priority": "🟡", "person_data": { "role": "Senior Engineer", "organization": "Eng.io", "email": "bob@eng.io", "topics_of_interest": ["Rust"], ... }, ... }
  { "type": "people", "title": "Carol Lee — PM", "content": "PM for Q1 launch. Detail-oriented.", "priority": "🟡", "person_data": { "role": "PM", "scheduling_preferences": "Weekly syncs Mondays 10am", "working_style": "Detail-oriented", ... }, ... }

If emails mention multiple commitments:
  { "type": "commitments", "title": "Review PR #247 by Friday", "content": "Promised Bob to review authentication PR by Feb 20, 2026 at 5pm. Remote review.", "priority": "🔴", ... }
  { "type": "commitments", "title": "Austin Meetup Moderation", "content": "Moderating Austin Coding Meetup on February 21, 2026 at 7pm at Capital Factory.", "priority": "🔴", ... }

IMPORTANT RULES:
- Extract AT LEAST 3 observations per batch of emails (create MORE if distinct entities found)
- Every observation must have evidence (which emails support it)
- Use ONLY these types: decisions, people, commitments
- Be specific — "prefers morning meetings" not "has meeting preferences"
- For people: Title = "Name — Role", include email address, role/relationship
- For commitments: Include date, time, venue/location when available
- Capture preferences, topics, and communication style WITHIN person_data fields on person observations
  (e.g., user's preferences go on the "Me" observation; a contact's style goes on their person observation)
- CRITICAL: If a decision/commitment mentions people, create SEPARATE person observations for each person mentioned
"""

        # ── Tool Definitions ───────────────────────────────────
        # "self.tools" is a list of tool schemas that tell Claude what
        # tools are available. Each schema has:
        #   - name: what to call the tool
        #   - description: what the tool does (Claude reads this!)
        #   - input_schema: what arguments the tool accepts
        #
        # This follows the MCP (Model Context Protocol) format —
        # the standard way to describe tools for AI agents.
        self.tools = [
            {
                # The tool's name — Claude uses this to request the tool
                "name": "read_emails",

                # Description — Claude reads this to understand when/how
                # to use the tool. Be clear and specific!
                "description": (
                    "Fetch emails from Gmail. Returns list of emails with "
                    "subject, sender, date, body, and labels."
                ),

                # Input schema — defines what arguments the tool accepts.
                # This follows JSON Schema format (a standard for describing
                # data structures).
                "input_schema": {
                    "type": "object",  # The input is a dictionary/object
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Max emails to fetch (default: 50)",
                            "default": 50
                        },
                        "query": {
                            "type": "string",
                            "description": "Gmail search query (e.g., 'is:important')",
                            "default": ""
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Fetch from last N days (default: 30)",
                            "default": 30
                        }
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        Run a tool when Claude asks for it.

        This method is called by the agentic loop (in BaseAgent.run())
        whenever Claude decides to use a tool. We check which tool
        was requested and call the appropriate function.

        Args:
            tool_name: Which tool Claude wants to use (e.g., "read_emails")
            tool_args: The arguments Claude provided (e.g., {"max_results": 50})

        Returns:
            The tool's output as a string (JSON in this case).
        """
        # Check which tool was requested
        if tool_name == "read_emails":
            # Call our Gmail fetch function with the arguments Claude provided.
            # ".get(key, default)" safely retrieves a value, using the default
            # if the key is missing.
            emails = fetch_emails(
                max_results=tool_args.get('max_results', 50),
                query=tool_args.get('query', ''),
                days_back=tool_args.get('days_back', 30),
            )

            # Convert the list of email dictionaries to a JSON string
            # so Claude can read it. "indent=2" makes it nicely formatted.
            # "default=str" handles any non-serializable values by converting
            # them to strings.
            return json.dumps(emails, indent=2, default=str)

        # If Claude asked for a tool we don't have, raise an error
        raise ValueError(f"Unknown tool: {tool_name}")

    def analyze_batch(self, emails_json: str, batch_num: int, total_batches: int) -> str:
        """
        Analyze a pre-fetched batch of emails without calling the read_emails tool.

        The orchestrator fetches all emails once, splits them into batches,
        and feeds each batch here. This keeps each agent run within Claude's
        token budget regardless of how many total emails the user requested.

        Args:
            emails_json:    JSON string of the email batch (list of email dicts).
            batch_num:      Which batch this is (1-indexed), for context.
            total_batches:  How many batches total, for context.

        Returns:
            str: Claude's JSON observations for this batch.
        """
        # Reset conversation history so each batch gets a fresh context window.
        # Without this, previous batches would accumulate and eventually overflow.
        self.reset()

        prompt = (
            f"You are processing email batch {batch_num} of {total_batches}. "
            f"The emails below have already been fetched — analyze them directly "
            f"without calling the read_emails tool.\n\n"
            f"EMAILS:\n{emails_json}"
        )

        return self.run(prompt)
