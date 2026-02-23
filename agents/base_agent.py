# agents/base_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "blueprint" for all AI agents in our system. Every agent
# (Email Reader, Memory Writer, Query Agent) inherits from this class,
# which means they all share this common logic.
#
# The key thing this file implements is the "AGENTIC LOOP":
#   1. We send a message to Claude (the AI)
#   2. Claude thinks and might say: "I need to use a tool first"
#   3. We run the tool and send the result back to Claude
#   4. Claude thinks again — maybe uses another tool, or gives a final answer
#   5. We return Claude's final text answer
#
# This loop is what makes an "agent" different from a simple chatbot.
# A chatbot just responds. An agent can USE TOOLS to take actions —
# like reading emails, searching files, or writing data.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "os" lets us read environment variables (like the API key)
import os

# "time" lets us pause execution (for retry delays)
import time

# "random" is used to add jitter (randomness) to retry delays
import random

# "Anthropic" is the official Python client for talking to Claude.
# It handles sending messages to Claude's API and receiving responses.
# "APIStatusError" is raised when the API returns an error HTTP status code
# (like 429 rate-limited or 529 overloaded).
from anthropic import Anthropic, APIStatusError


# ── SET UP THE CLAUDE CLIENT ──────────────────────────────────────────

# Create a single Anthropic client that all agents will share.
# It automatically reads the "ANTHROPIC_API_KEY" from your environment
# variables (set in your .env file). No need to pass the key explicitly.
client = Anthropic()

# "MODEL" is which version of Claude we'll use.
# "claude-sonnet-4-20250514" is a great balance of intelligence and speed.
# All agents in our system use the same model for consistency.
MODEL = "claude-sonnet-4-20250514"


# ── THE BASE AGENT CLASS ──────────────────────────────────────────────

class BaseAgent:
    """
    The shared foundation for all AI agents.

    A "class" in Python is like a blueprint or template. When we create
    an EmailReaderAgent, it's built FROM this BaseAgent blueprint, meaning
    it automatically gets all the abilities defined here.

    Every agent has three things it must define:
        1. system_prompt — A text instruction telling Claude what role to play
        2. tools        — A list of tools (functions) the agent can use
        3. execute_tool — The code that actually RUNS a tool when Claude asks

    And every agent inherits one key ability from this class:
        - run()  — The agentic loop that sends messages, handles tool calls,
                   and returns the final answer
    """

    def __init__(self):
        """
        Initialize the base agent with default values.

        "__init__" is a special Python method called a "constructor."
        It runs automatically whenever a new agent is created.
        Think of it as the setup step when you first open an app.
        """
        # "self.system_prompt" tells Claude what persona/role to adopt.
        # Each subclass (EmailReaderAgent, etc.) will override this with
        # a specific prompt for its job. This is just the default.
        self.system_prompt = "You are a helpful assistant."

        # "self.tools" is a list of tool definitions (schemas) that tell
        # Claude what tools are available and how to use them.
        # Each tool schema includes: name, description, and input parameters.
        # Subclasses override this with their specific tools.
        self.tools = []

        # "self.conversation_history" keeps track of all messages exchanged
        # between the user/orchestrator and Claude during this session.
        # This gives Claude "memory" within a single conversation.
        self.conversation_history = []

        # "self.on_retry" is an optional callback that gets called before
        # each retry wait. Callers (like the orchestrator) can set this to
        # surface retry progress to the UI (e.g., "Retrying in 8s...").
        # Signature: on_retry(attempt: int, max_retries: int, delay: float)
        self.on_retry = None

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        Run a tool and return its result.

        This is a "placeholder" method. Subclasses MUST override it
        with their own implementation that actually does something.
        If a subclass forgets to override it, this will crash with
        NotImplementedError — a helpful reminder.

        Args:
            tool_name: The name of the tool to run (e.g., "read_emails")
            tool_args: The arguments to pass to the tool (e.g., {"max_results": 50})

        Returns:
            The tool's output as a string.
        """
        raise NotImplementedError("Subclasses must implement execute_tool")

    def _call_claude(self, on_retry=None) -> object:
        """
        Call the Claude API with automatic retry for transient errors.

        When the API is overloaded (529) or rate-limited (429), this method
        waits and retries with exponential backoff + jitter instead of crashing.

        Exponential backoff means: wait 2s, then 4s, then 8s, then 16s, etc.
        Jitter adds randomness (±25%) so multiple retries don't all fire at
        the same moment — this prevents a "thundering herd" effect.

        Args:
            on_retry: Optional callback(attempt, max_retries, delay) called
                     before each retry wait. Lets callers surface retry progress
                     (e.g., to SSE stream or console).

        Returns:
            The Claude API response object.

        Raises:
            APIStatusError: If all retries are exhausted or a non-retryable error occurs.
        """
        # Import retry settings from config (avoids circular import at module level)
        from config.settings import API_MAX_RETRIES, API_RETRY_BASE_DELAY

        for attempt in range(API_MAX_RETRIES):
            try:
                return client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=self.conversation_history,
                )

            except APIStatusError as e:
                # Only retry on transient errors:
                #   429 = rate limited (too many requests)
                #   529 = overloaded (server at capacity)
                is_retryable = e.status_code in (429, 529)
                has_retries_left = attempt < API_MAX_RETRIES - 1

                if is_retryable and has_retries_left:
                    # Exponential backoff with jitter:
                    # Base: 2s → 4s → 8s → 16s → 32s → 64s → 128s
                    # Jitter: ±25% randomness to avoid thundering herd
                    base_delay = API_RETRY_BASE_DELAY * (2 ** attempt)
                    jitter = base_delay * 0.25 * (2 * random.random() - 1)
                    delay = base_delay + jitter

                    print(f"   [RETRY] API {e.status_code} error, waiting {delay:.1f}s "
                          f"(attempt {attempt + 1}/{API_MAX_RETRIES})")

                    # Notify caller about the retry (for SSE progress, etc.)
                    if on_retry:
                        on_retry(attempt + 1, API_MAX_RETRIES, delay)

                    time.sleep(delay)
                else:
                    # Non-retryable error or out of retries — let it propagate
                    raise

        # Should never reach here (the loop either returns or raises),
        # but just in case:
        raise RuntimeError("Retry loop exited unexpectedly")

    def run(self, user_message: str, max_tool_rounds: int = 10) -> str:
        """
        THE AGENTIC LOOP — the heart of every agent.

        This method sends a message to Claude and handles the back-and-forth
        of tool usage until Claude produces a final text answer.

        Here's the flow, step by step:

        1. Add the user's message to conversation history
        2. Send the full conversation + available tools to Claude
        3. Claude responds with one of two things:
           a) "tool_use" — Claude wants to call a tool first
              → We run the tool, send the result back, and go to step 2
           b) Final text — Claude has an answer
              → We return it
        4. Safety limit: if we've done 10 rounds of tool calls without
           getting a final answer, we stop (prevents infinite loops)

        Args:
            user_message:    What the user (or orchestrator) is asking.
            max_tool_rounds: Maximum number of tool-call rounds allowed.
                            Default is 10 — more than enough for any task.

        Returns:
            str: Claude's final text response.
        """

        # ── Step 1: Add the user's message to history ──────────
        # We keep the full conversation so Claude has context about
        # what was said before (within this session).
        self.conversation_history.append({
            "role": "user",       # This message is from the "user"
            "content": user_message  # The actual text
        })

        # ── Step 2-3: The loop ─────────────────────────────────
        # We loop up to "max_tool_rounds" times. Each iteration is
        # one round-trip with Claude.
        for round_num in range(max_tool_rounds):

            # ── Call Claude (with automatic retry) ────────────
            # _call_claude handles transient API errors (429/529)
            # with exponential backoff, so we don't need try/except here.
            # Pass self.on_retry so callers can surface retry progress.
            response = self._call_claude(on_retry=self.on_retry)

            # ── Check: Does Claude want to use a tool? ─────────
            # "stop_reason" tells us WHY Claude stopped generating.
            # "tool_use" means Claude wants to call one or more tools
            # before giving a final answer.
            if response.stop_reason == "tool_use":

                # Add Claude's response (which contains tool_use blocks)
                # to the conversation history so Claude remembers what it did
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content  # May contain text + tool_use blocks
                })

                # ── Execute each tool call ─────────────────────
                # Claude might ask for multiple tools in one response.
                # We loop through all the "blocks" in Claude's response
                # and handle each tool_use block.
                tool_results = []

                for block in response.content:
                    # Check if this block is a tool call
                    if block.type == "tool_use":
                        print(f"   [TOOL] Calling tool: {block.name}")

                        try:
                            # Run the tool using the subclass's execute_tool method.
                            # "block.name" is the tool name (e.g., "read_emails")
                            # "block.input" is the arguments dict (e.g., {"max_results": 50})
                            result = self.execute_tool(block.name, block.input)

                            # Package the result in the format Claude expects
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,  # Links this result to the tool call
                                "content": str(result)     # The tool's output as text
                            })

                        except Exception as e:
                            # If the tool crashes, tell Claude about the error
                            # so it can try a different approach or report it.
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True  # Flag this as an error result
                            })

                # ── Send tool results back to Claude ───────────
                # Tool results go in a "user" message (that's how Claude's
                # API works — tool results are sent as a user message).
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results
                })

                # Now the loop continues — Claude will see the tool results
                # and decide whether to use another tool or give a final answer.

            else:
                # ── Claude gave a final text answer ────────────
                # "stop_reason" is NOT "tool_use", which means Claude is
                # done thinking and has produced its final response.

                # Extract the text from Claude's response blocks.
                # A response can contain multiple blocks (text, images, etc.)
                # but we only want the text ones.
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):  # Check if this block has text
                        final_text += block.text

                # Add Claude's response to history (for future reference)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Return the final answer!
                return final_text

        # ── Safety net ─────────────────────────────────────────
        # If we've gone through max_tool_rounds without getting a final
        # answer, something is probably stuck in a loop. Return a warning.
        return "Agent reached maximum tool rounds without completing."

    def reset(self):
        """
        Clear the conversation history for a fresh start.

        Call this between separate tasks so the agent doesn't get
        confused by old context from a previous conversation.
        """
        self.conversation_history = []
