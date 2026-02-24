# agents/base_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "blueprint" for all AI agents in our system. Every agent
# (Email Reader, Memory Writer, Query Agent, Action Agent) inherits from
# this class, which means they all share this common logic.
#
# The key thing this file implements is the "AGENTIC LOOP":
#   1. We send a message to the LLM (AI model)
#   2. The LLM thinks and might say: "I need to use a tool first"
#   3. We run the tool and send the result back to the LLM
#   4. The LLM thinks again — maybe uses another tool, or gives a final answer
#   5. We return the LLM's final text answer
#
# MULTI-PROVIDER SUPPORT:
#   This file supports two LLM providers:
#     1. OpenRouter (default) — uses the OpenAI-compatible API format.
#        Can route to many models (Kimi K2.5, GPT-4, etc.)
#     2. Anthropic (fallback) — direct access to Claude models.
#   If OpenRouter fails, the system automatically falls back to Anthropic.
#
#   The tricky part: OpenRouter uses OpenAI's message format (tool_calls,
#   finish_reason, JSON string arguments), while our agent loop was built
#   for Anthropic's format (content blocks, stop_reason, parsed dict input).
#   We solve this with an "adapter" — wrapper classes that make OpenAI
#   responses look like Anthropic responses, so the run() method doesn't
#   need to change at all.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

import os
import json
import re
import time
import random

# Anthropic SDK (fallback provider)
from anthropic import Anthropic, APIStatusError

# OpenAI SDK (used for OpenRouter, which has an OpenAI-compatible API)
from openai import OpenAI


# ── PROVIDER SETTINGS ───────────────────────────────────────────────────
# Import from config so all settings live in one place.

from config.settings import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, MAX_TOKENS,
)

# Determine which provider is available.
# OpenRouter is preferred (primary); Anthropic is the fallback.
USE_OPENROUTER = bool(OPENROUTER_API_KEY)
USE_ANTHROPIC = bool(ANTHROPIC_API_KEY)


# ── SET UP LLM CLIENTS ─────────────────────────────────────────────────

# OpenRouter client (primary) — uses the OpenAI SDK pointed at OpenRouter's URL.
openrouter_client = None
if USE_OPENROUTER:
    openrouter_client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

# Anthropic client (fallback) — the original client.
anthropic_client = None
if USE_ANTHROPIC:
    anthropic_client = Anthropic()

# Log which providers are active at startup.
if USE_OPENROUTER:
    print(f"[LLM] Primary provider: OpenRouter ({OPENROUTER_MODEL})")
if USE_ANTHROPIC:
    label = "Fallback" if USE_OPENROUTER else "Primary"
    print(f"[LLM] {label} provider: Anthropic ({ANTHROPIC_MODEL})")
if not USE_OPENROUTER and not USE_ANTHROPIC:
    print("[LLM] WARNING: No LLM API key configured! Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY in .env")


# ── ADAPTER CLASSES ─────────────────────────────────────────────────────
# These make OpenAI-format responses look like Anthropic-format responses,
# so the agentic loop (run method) doesn't need to know which provider
# generated the response. This is the "adapter pattern."

class _Block(dict):
    """
    A universal content block that mimics Anthropic's TextBlock / ToolUseBlock.

    Anthropic responses contain a list of "blocks" in response.content.
    Each block has a .type ("text" or "tool_use") and type-specific attributes.
    This class recreates that interface for OpenAI responses.

    Inherits from dict so it's JSON-serializable (Anthropic's SDK encoder
    can handle dicts natively). Attribute access (block.type, block.text)
    is supported via __getattr__ for compatibility with the agentic loop.
    """
    def __init__(self, block_type, **kwargs):
        super().__init__(type=block_type, **kwargs)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"_Block has no attribute '{name}'")


def _sanitize_tool_id(tool_id):
    """
    Sanitize a tool call ID to be compatible with all providers.

    Anthropic requires tool_use IDs to match ^[a-zA-Z0-9_-]+$ but some
    providers (e.g., Kimi K2.5) generate IDs like "add_numbers:0" with colons.
    We replace invalid characters with underscores.
    """
    return re.sub(r'[^a-zA-Z0-9_-]', '_', tool_id)


class _ContentList(list):
    """
    A list subclass that can carry metadata about the original OpenAI message.

    When we adapt an OpenAI response into Anthropic-style content blocks,
    we lose provider-specific fields like Kimi K2.5's `reasoning` field.
    By storing the raw OpenAI message dict on the list itself,
    _messages_to_openai() can replay the exact original message instead
    of reconstructing it from the blocks.
    """
    pass


class _AdaptedResponse:
    """
    Makes an OpenAI chat completion response look like an Anthropic response.

    Anthropic response has:
        .stop_reason  — "end_turn" or "tool_use"
        .content      — list of _Block objects (text and/or tool_use)

    OpenAI response has:
        .choices[0].finish_reason — "stop" or "tool_calls"
        .choices[0].message.content — text string or None
        .choices[0].message.tool_calls — list of tool call objects or None

    This class bridges the gap.
    """
    def __init__(self, openai_response):
        choice = openai_response.choices[0]
        message = choice.message

        # Convert finish_reason: OpenAI → Anthropic
        if choice.finish_reason == "tool_calls":
            self.stop_reason = "tool_use"
        else:
            self.stop_reason = "end_turn"

        # Build the content blocks list (Anthropic format)
        # Use _ContentList so we can carry the raw OpenAI message as metadata
        self.content = _ContentList()

        # Store the full message as a plain dict for later replay in
        # _messages_to_openai(). model_dump() preserves extra fields like
        # Kimi K2.5's `reasoning` and `reasoning_details` that the Pydantic
        # model doesn't have as typed attributes.
        msg_dict = message.model_dump()

        # Sanitize tool IDs in the stored dict too, so they stay consistent
        # with the _Block IDs used by run() for tool_results.
        if msg_dict.get("tool_calls"):
            for tc_dict in msg_dict["tool_calls"]:
                tc_dict["id"] = _sanitize_tool_id(tc_dict["id"])

        self.content._openai_message_dict = msg_dict

        # Add text block if there's text content
        if message.content:
            self.content.append(_Block("text", text=message.content))

        # Convert tool calls from OpenAI format to Anthropic-like blocks
        if message.tool_calls:
            for tc in message.tool_calls:
                # OpenAI stores arguments as a JSON string; Anthropic uses a parsed dict
                try:
                    parsed_input = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    parsed_input = {}

                # Sanitize tool ID — some providers (Kimi K2.5) use characters
                # like ":" that Anthropic rejects.
                safe_id = _sanitize_tool_id(tc.id)

                self.content.append(_Block(
                    "tool_use",
                    id=safe_id,
                    name=tc.function.name,
                    input=parsed_input,
                ))


# ── FORMAT CONVERSION HELPERS ───────────────────────────────────────────

def _tools_to_openai(anthropic_tools):
    """
    Convert Anthropic tool definitions to OpenAI format.

    Anthropic:  {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:     {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    if not anthropic_tools:
        return []
    openai_tools = []
    for tool in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            }
        })
    return openai_tools


def _messages_to_openai(anthropic_messages):
    """
    Convert Anthropic-format conversation history to OpenAI format.

    The tricky cases:
    1. Assistant messages with content blocks (text + tool_use) → single message
       with content string + tool_calls array.
    2. User messages containing tool_results → split into separate "tool" role messages.
    3. Regular user text messages → pass through unchanged.
    """
    openai_msgs = []

    for msg in anthropic_messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            if isinstance(content, str):
                # Simple text message — pass through
                openai_msgs.append({"role": "user", "content": content})

            elif isinstance(content, list):
                # Could be tool results or mixed content
                tool_results = []
                text_parts = []

                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_results.append(item)
                    elif isinstance(item, dict):
                        text_parts.append(str(item.get("content", item)))
                    else:
                        text_parts.append(str(item))

                # Emit tool results as separate "tool" role messages
                for tr in tool_results:
                    openai_msgs.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": str(tr.get("content", "")),
                    })

                # Emit any remaining text as a user message
                if text_parts and not tool_results:
                    openai_msgs.append({"role": "user", "content": "\n".join(text_parts)})

        elif role == "assistant":
            if isinstance(content, str):
                openai_msgs.append({"role": "assistant", "content": content})

            elif isinstance(content, list):
                # Fast path: if this content came from an OpenAI response (via
                # _AdaptedResponse), replay the raw message dict directly. This
                # preserves provider-specific fields like Kimi K2.5's `reasoning`
                # and `reasoning_details` that don't exist in Anthropic's format.
                raw_dict = getattr(content, '_openai_message_dict', None)
                if raw_dict is not None:
                    # Start from the raw dict — it already has content, tool_calls,
                    # reasoning, reasoning_details, etc.
                    rebuilt = {"role": "assistant"}
                    for key, value in raw_dict.items():
                        if key == "role":
                            continue  # We set role ourselves
                        if value is not None:
                            rebuilt[key] = value
                    openai_msgs.append(rebuilt)
                    continue

                # Slow path: reconstruct from Anthropic-native content blocks
                text_parts = []
                tool_calls = []

                for block in content:
                    block_type = getattr(block, 'type', None)
                    if block_type == "text":
                        text_parts.append(block.text)
                    elif block_type == "tool_use":
                        # block.input is a dict (both Anthropic and our _Block)
                        tool_calls.append({
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            }
                        })

                assistant_msg = {"role": "assistant"}
                assistant_msg["content"] = "\n".join(text_parts) if text_parts else None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                openai_msgs.append(assistant_msg)

    return openai_msgs


# ── THE BASE AGENT CLASS ──────────────────────────────────────────────

class BaseAgent:
    """
    The shared foundation for all AI agents.

    Every agent has three things it must define:
        1. system_prompt — A text instruction telling the LLM what role to play
        2. tools        — A list of tools the agent can use
        3. execute_tool — The code that actually RUNS a tool when the LLM asks

    And every agent inherits one key ability from this class:
        - run()  — The agentic loop that sends messages, handles tool calls,
                   and returns the final answer
    """

    def __init__(self):
        self.system_prompt = "You are a helpful assistant."
        self.tools = []
        self.conversation_history = []

        # Optional callback for retry progress (e.g., for SSE streaming).
        # Signature: on_retry(attempt: int, max_retries: int, delay: float)
        self.on_retry = None

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Run a tool and return its result. Subclasses MUST override this."""
        raise NotImplementedError("Subclasses must implement execute_tool")

    # ── LLM CALL METHODS ─────────────────────────────────────────────

    def _call_openrouter(self):
        """
        Call the LLM via OpenRouter (OpenAI-compatible API) with retry logic.

        Converts our Anthropic-format tools and messages to OpenAI format,
        makes the API call, then wraps the response so it looks like an
        Anthropic response (using _AdaptedResponse).
        """
        from config.settings import API_MAX_RETRIES, API_RETRY_BASE_DELAY

        # Convert formats
        openai_tools = _tools_to_openai(self.tools)
        openai_messages = [{"role": "system", "content": self.system_prompt}]
        openai_messages.extend(_messages_to_openai(self.conversation_history))

        # Build the API call kwargs
        kwargs = {
            "model": OPENROUTER_MODEL,
            "messages": openai_messages,
            "max_tokens": MAX_TOKENS,
        }
        # Only include tools if the agent has any
        if openai_tools:
            kwargs["tools"] = openai_tools

        for attempt in range(API_MAX_RETRIES):
            try:
                response = openrouter_client.chat.completions.create(**kwargs)
                # Wrap in adapter so it looks like an Anthropic response
                return _AdaptedResponse(response)

            except Exception as e:
                # Check for retryable HTTP errors (rate limit, server overload)
                status_code = getattr(e, 'status_code', None)
                is_retryable = status_code in (429, 502, 503, 529) if status_code else False
                has_retries_left = attempt < API_MAX_RETRIES - 1

                if is_retryable and has_retries_left:
                    base_delay = API_RETRY_BASE_DELAY * (2 ** attempt)
                    jitter = base_delay * 0.25 * (2 * random.random() - 1)
                    delay = base_delay + jitter

                    print(f"   [RETRY] OpenRouter {status_code} error, waiting {delay:.1f}s "
                          f"(attempt {attempt + 1}/{API_MAX_RETRIES})")

                    if self.on_retry:
                        self.on_retry(attempt + 1, API_MAX_RETRIES, delay)

                    time.sleep(delay)
                else:
                    raise

        raise RuntimeError("OpenRouter retry loop exited unexpectedly")

    def _call_anthropic(self):
        """
        Call the LLM via the Anthropic API with retry logic.

        This is the original implementation — sends messages in Anthropic's
        native format and returns the raw Anthropic response object.
        """
        from config.settings import API_MAX_RETRIES, API_RETRY_BASE_DELAY

        for attempt in range(API_MAX_RETRIES):
            try:
                return anthropic_client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=MAX_TOKENS,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=self.conversation_history,
                )

            except APIStatusError as e:
                is_retryable = e.status_code in (429, 529)
                has_retries_left = attempt < API_MAX_RETRIES - 1

                if is_retryable and has_retries_left:
                    base_delay = API_RETRY_BASE_DELAY * (2 ** attempt)
                    jitter = base_delay * 0.25 * (2 * random.random() - 1)
                    delay = base_delay + jitter

                    print(f"   [RETRY] Anthropic {e.status_code} error, waiting {delay:.1f}s "
                          f"(attempt {attempt + 1}/{API_MAX_RETRIES})")

                    if self.on_retry:
                        self.on_retry(attempt + 1, API_MAX_RETRIES, delay)

                    time.sleep(delay)
                else:
                    raise

        raise RuntimeError("Anthropic retry loop exited unexpectedly")

    def _call_llm(self):
        """
        Call the LLM with automatic provider fallback.

        Strategy:
          1. If OpenRouter is configured, try it first.
          2. If OpenRouter fails and Anthropic is available, fall back.
          3. If only Anthropic is configured, use it directly.

        Both providers return responses in the same shape (Anthropic format)
        thanks to the _AdaptedResponse wrapper, so the run() method doesn't
        need to know which provider answered.
        """
        if USE_OPENROUTER and openrouter_client:
            try:
                return self._call_openrouter()
            except Exception as e:
                if USE_ANTHROPIC and anthropic_client:
                    print(f"   [FALLBACK] OpenRouter failed ({e}). Switching to Anthropic.")
                    return self._call_anthropic()
                else:
                    raise

        if USE_ANTHROPIC and anthropic_client:
            return self._call_anthropic()

        raise RuntimeError(
            "No LLM provider available. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY in .env"
        )

    # ── THE AGENTIC LOOP ─────────────────────────────────────────────

    def run(self, user_message: str, max_tool_rounds: int = 10) -> str:
        """
        THE AGENTIC LOOP — the heart of every agent.

        Sends a message to the LLM and handles the back-and-forth of tool
        usage until the LLM produces a final text answer.

        Flow:
        1. Add the user's message to conversation history
        2. Send the full conversation + available tools to the LLM
        3. The LLM responds with one of two things:
           a) "tool_use" — it wants to call a tool first
              → We run the tool, send the result back, and loop
           b) Final text — it has an answer
              → We return it
        4. Safety limit: max_tool_rounds prevents infinite loops
        """
        # Step 1: Add the user's message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Step 2-3: The loop
        for round_num in range(max_tool_rounds):

            # Call the LLM (with automatic provider fallback)
            response = self._call_llm()

            # Check: Does the LLM want to use a tool?
            if response.stop_reason == "tool_use":

                # Add the LLM's response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"   [TOOL] Calling tool: {block.name}")

                        try:
                            result = self.execute_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result),
                            })
                        except Exception as e:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True,
                            })

                # Send tool results back to the LLM
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

            else:
                # The LLM gave a final text answer
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text

                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                return final_text

        # Safety net
        return "Agent reached maximum tool rounds without completing."

    def reset(self):
        """Clear the conversation history for a fresh start."""
        self.conversation_history = []
