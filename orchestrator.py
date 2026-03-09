# orchestrator.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "manager" or "traffic controller" of the whole system.
# When a user makes a request, the Orchestrator decides which agent(s)
# to call and in what order.
#
# It handles THREE types of requests:
#
#   1. "BUILD" — The full pipeline: Email Reader → Memory Writer
#      User says: "build my memory from emails"
#      → Orchestrator calls Agent 1 (Email Reader) to fetch & analyze emails
#      → Then passes the results to Agent 2 (Memory Writer) to create files
#
#   2. "QUERY" — A question about the user's memory vault
#      User says: "Who do I email the most?"
#      → Orchestrator calls Agent 3 (Query Agent) to search and answer
#
#   3. "STATS" — Show vault statistics
#      User says: "How many memories do I have?"
#      → Orchestrator reads the vault directly (no agent needed)
#
# Think of it as a project manager who knows each team member's strengths
# and assigns work accordingly.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "json" for data formatting
import json

# "math" for ceiling division (calculating batch counts)
import math

# "Console" and "Panel" from "rich" make terminal output pretty.
# "Console" is a printer that supports colors and formatting.
# "Panel" draws a box around text.
from rich.console import Console
from rich.panel import Panel

# Import all three agent classes
from agents.email_reader import EmailReaderAgent
from agents.memory_writer import MemoryWriterAgent
from agents.query_agent import QueryAgent
from agents.action_agent import ActionAgent
from agents.reconciliation_agent import ReconciliationAgent
from agents.insights_agent import InsightsAgent

# Import vault helper functions
from pathlib import Path
from memory.vault import (
    initialize_vault, get_vault_stats, list_memories,
    get_processed_email_ids, save_processed_email_ids
)
from memory.graph import rebuild_graph

# Import Gmail fetch functions (incremental: list IDs first, then fetch by ID)
from tools.gmail_tools import fetch_emails, list_email_ids, fetch_emails_by_ids

# Import batch size config
from config.settings import EMAIL_BATCH_SIZE

# Create a "console" object for pretty-printing to the terminal.
# The web frontend doesn't see this — it's for the server logs.
console = Console()


# ── THE ORCHESTRATOR CLASS ─────────────────────────────────────────────

class Orchestrator:
    """
    The central coordinator that routes user requests to the right agents.

    It creates and manages all three agents, decides which one(s) to call
    based on the user's request, and handles the data flow between them.
    """

    def __init__(self):
        """
        Set up the Orchestrator: initialize the vault and create all agents.

        This runs once when the web server starts. After this, the
        orchestrator is ready to handle requests.
        """
        # Initialize the vault folder structure (creates folders if needed)
        initialize_vault()

        # Create one instance of each agent.
        # These persist across requests, which means their conversation
        # history stays alive within a session.
        self.email_reader = EmailReaderAgent()    # Agent 1: fetches emails
        self.memory_writer = MemoryWriterAgent()  # Agent 2: writes memories
        self.query_agent = QueryAgent()           # Agent 3: answers questions
        self.action_agent = ActionAgent()      # Agent 4: generates action items
        self.reconciliation_agent = ReconciliationAgent()
        self.insights_agent = InsightsAgent()  # Agent 6: cross-correlation insights

    def route(self, user_input: str) -> str:
        """
        Examine the user's message and decide which handler to invoke.

        This is a simple keyword-based router. It looks for specific words
        in the user's message to determine their intent:
          - Words like "build", "scan", "fetch" → build pipeline
          - Words like "stats", "how many" → show statistics
          - Everything else → treat as a query about the vault

        In a production system, you might use an LLM to classify intent
        more intelligently. But for learning, explicit keyword matching
        is clearer and easier to debug.

        Args:
            user_input: The raw text from the user.

        Returns:
            str: The response to show the user.
        """
        # Convert to lowercase for case-insensitive matching
        user_lower = user_input.lower().strip()

        # ── Check for "build" intent ───────────────────────────
        # If the user mentions any of these words, they want to
        # scan their emails and build/update their memory vault.
        if any(kw in user_lower for kw in [
            'build', 'scan', 'read email', 'fetch email',
            'process email', 'analyze email', 'ingest'
        ]):
            return self.build_memory(user_input)

        # ── Check for "refresh actions" intent ───────────────
        elif any(kw in user_lower for kw in [
            'refresh', 'prioritize', 'actions', 'action items',
            'what needs attention', 'what should i do', 'priorities'
        ]):
            return self.refresh_actions(user_input)

        # ── Check for "reconcile" intent ─────────────────────────
        elif any(kw in user_lower for kw in [
            'reconcile', 'update actions', 'action status',
            'check actions', 'reconcile actions'
        ]):
            return self.reconcile_actions(user_input)

        # ── Check for "dismiss insight" intent ────────────────────
        elif any(kw in user_lower for kw in [
            'dismiss insight', 'dismiss all insights'
        ]):
            return self.dismiss_insights(user_input)

        # ── Check for "insights" intent ──────────────────────────
        elif any(kw in user_lower for kw in [
            'insights', 'patterns', 'what am i missing',
            'cross-correlate', 'connections', 'generate insights'
        ]):
            return self.generate_insights(user_input)

        # ── Check for "deduplicate" intent ──────────────────────
        elif any(kw in user_lower for kw in [
            'deduplicate', 'dedup', 'clean vault', 'fix duplicates'
        ]):
            return self.deduplicate_vault()

        # ── Check for "stats" intent ───────────────────────────
        elif any(kw in user_lower for kw in [
            'stats', 'statistics', 'how many', 'vault info'
        ]):
            return self.show_stats()

        # ── Default: treat as a query ──────────────────────────
        # Any message that isn't a build or stats request is treated
        # as a question about the user's memory vault.
        else:
            return self.query_memory(user_input)

    def build_memory(self, user_input: str, progress_callback=None,
                     max_emails: int = None, days_back: int = None,
                     gmail_query: str = '') -> str:
        """
        Run the full pipeline: Fetch → Batch Analyze → Write Memories.

        This is a THREE-STEP process:
          Step 1: Fetch emails from Gmail directly (fast, one API call)
          Step 2: Split emails into batches and analyze each batch through
                  the Email Reader Agent (keeps each run within token limits)
          Step 3: Send all accumulated observations to the Memory Writer Agent

        The "progress_callback" lets the web frontend show live updates
        for each batch (e.g., "Analyzing batch 2 of 5...").

        Args:
            user_input:        The user's build request (may include filters).
            progress_callback: Optional function(dict) called with progress events.
            max_emails:        Max emails to fetch (overrides config default).
            days_back:         How many days back to look (overrides config default).
            gmail_query:       Gmail search query filter.

        Returns:
            str: A summary of what was created.
        """
        def emit(event):
            """Send a progress event if a callback is registered."""
            if progress_callback:
                progress_callback(event)

        # Use config defaults if not explicitly provided
        from config.settings import DEFAULT_MAX_EMAILS, DEFAULT_DAYS_BACK
        if max_emails is None:
            max_emails = DEFAULT_MAX_EMAILS
        if days_back is None:
            days_back = DEFAULT_DAYS_BACK

        console.print(Panel(
            "[bold]Starting memory build pipeline...[/bold]\n"
            f"   Step 1: Fetch up to {max_emails} emails from last {days_back} days\n"
            f"   Step 2: Analyze in batches of {EMAIL_BATCH_SIZE}\n"
            "   Step 3: Memory Writer -- Create memory files\n"
            "   Step 3.5: Rebuild knowledge graph\n"
            "   Step 4: Action Agent -- Generate prioritized action items\n"
            "   Step 5: Reconciliation Agent -- Update action item statuses\n"
            "   Step 6: Insights Agent -- Cross-correlate vault for patterns",
            title="Pipeline",
            border_style="blue"
        ))

        # ── Step 1: Incremental email scan ────────────────────
        # Phase 1: List just the message IDs (1 cheap API call)
        # Phase 2: Diff against already-processed IDs
        # Phase 3: Fetch full content only for new emails
        console.print("\n[bold cyan]Step 1/5: Scanning for new emails[/bold cyan]")
        emit({
            "stage": "fetching", "status": "started",
            "message": f"Scanning for new emails from last {days_back} days..."
        })

        # Phase 1: Get just the IDs (cheap — no email content fetched)
        all_ids = list_email_ids(
            max_results=max_emails,
            query=gmail_query,
            days_back=days_back
        )

        if not all_ids:
            emit({"stage": "complete", "status": "complete",
                  "message": "No emails found matching criteria.", "stats": get_vault_stats()})
            return "No emails found matching your criteria."

        # Phase 2: Diff against processed IDs to find only new emails
        processed_ids = get_processed_email_ids()
        new_ids = [mid for mid in all_ids if mid not in processed_ids]

        if not new_ids:
            console.print(f"[green]All {len(all_ids)} emails already processed[/green]")
            emit({"stage": "complete", "status": "complete",
                  "message": f"All {len(all_ids)} emails already processed. No new emails to analyze.",
                  "stats": get_vault_stats()})
            return "All fetched emails have already been processed."

        console.print(f"   Scanned {len(all_ids)} IDs, {len(new_ids)} are new")
        emit({
            "stage": "fetching", "status": "in_progress",
            "message": f"Found {len(new_ids)} new emails out of {len(all_ids)} total. Fetching content..."
        })

        # Phase 3: Fetch full content only for new emails (the big savings)
        emails = fetch_emails_by_ids(new_ids)

        if not emails:
            emit({"stage": "complete", "status": "complete",
                  "message": "Failed to fetch any new email content.", "stats": get_vault_stats()})
            return "Failed to fetch new email content. Try again later."

        console.print(f"[green]OK - Fetched {len(emails)} new emails[/green]")
        emit({
            "stage": "fetching", "status": "complete",
            "message": f"Fetched {len(emails)} new emails (skipped {len(all_ids) - len(new_ids)} already processed)"
        })

        # ── Step 2: Batch analyze ────────────────────────────
        # Split emails into batches and run the Email Reader on each.
        # Each batch gets a fresh agent context, so token limits are
        # never exceeded regardless of total email count.
        total_batches = math.ceil(len(emails) / EMAIL_BATCH_SIZE)
        all_observations = []

        console.print(f"\n[bold cyan]Step 2/5: Analyzing in {total_batches} batch(es)[/bold cyan]")
        emit({
            "stage": "email_reader", "status": "started",
            "message": f"Analyzing {len(emails)} emails in {total_batches} batch(es)..."
        })

        failed_batches = []

        # Set up retry callback so the SSE stream shows retry progress.
        # When Claude API returns 429/529, this sends a progress event to
        # the browser instead of silently waiting in the background.
        def on_api_retry(attempt, max_retries, delay):
            emit({
                "stage": "email_reader", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.email_reader.on_retry = on_api_retry

        for batch_idx in range(total_batches):
            # Slice out this batch
            start = batch_idx * EMAIL_BATCH_SIZE
            end = start + EMAIL_BATCH_SIZE
            batch = emails[start:end]
            batch_num = batch_idx + 1

            console.print(f"   Batch {batch_num}/{total_batches} ({len(batch)} emails)...")
            emit({
                "stage": "email_reader", "status": "in_progress",
                "message": f"Analyzing batch {batch_num} of {total_batches} ({len(batch)} emails)..."
            })

            # Serialize the batch to JSON for the agent
            batch_json = json.dumps(batch, indent=2, default=str)

            # Run the Email Reader on this batch (fresh context each time).
            # Wrap in try/except so one failed batch doesn't kill the pipeline —
            # we skip it and continue with the remaining batches.
            try:
                batch_result = self.email_reader.analyze_batch(
                    batch_json, batch_num, total_batches
                )

                all_observations.append(batch_result)
                console.print(f"   [green]OK - Batch {batch_num} complete[/green]")

            except Exception as e:
                failed_batches.append(batch_num)
                console.print(f"   [red]SKIP - Batch {batch_num} failed: {e}[/red]")
                emit({
                    "stage": "email_reader", "status": "in_progress",
                    "message": f"Batch {batch_num} failed (API overloaded), skipping — continuing with remaining batches..."
                })

        # Combine all batch results into one observations block
        combined_observations = "\n\n---\n\n".join(all_observations)

        # Report batch completion (with info about any failures)
        succeeded = total_batches - len(failed_batches)
        if failed_batches:
            skip_msg = f"{succeeded} of {total_batches} batch(es) analyzed ({len(failed_batches)} skipped due to API errors)"
            console.print(f"[yellow]{skip_msg}[/yellow]")
            emit({"stage": "email_reader", "status": "complete", "message": skip_msg})
        else:
            console.print(f"[green]OK - All {total_batches} batch(es) analyzed[/green]")
            emit({"stage": "email_reader", "status": "complete",
                  "message": f"All {total_batches} batch(es) analyzed"})

        # If ALL batches failed, there's nothing for the Memory Writer to process
        if not all_observations:
            error_msg = "All batches failed due to API errors. Please try again later."
            emit({"stage": "error", "status": "error", "message": error_msg})
            return error_msg

        # ── Step 3: Memory Writer ────────────────────────────
        console.print("\n[bold cyan]Step 3/5: Memory Writer Agent[/bold cyan]")
        emit({
            "stage": "memory_writer", "status": "started",
            "message": "Memory Writer Agent is creating vault files..."
        })

        # Reset the Memory Writer for a fresh context and set up retry callback
        self.memory_writer.reset()
        def on_writer_retry(attempt, max_retries, delay):
            emit({
                "stage": "memory_writer", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.memory_writer.on_retry = on_writer_retry

        writer_prompt = (
            "Here are observations about the user extracted from their emails. "
            "These observations come from multiple batches, so you may see "
            "duplicate people (especially 'Me') — merge them when writing. "
            "Process each observation and write it to the memory vault. "
            "Check for existing memories first to avoid duplicates.\n\n"
            f"OBSERVATIONS:\n{combined_observations}"
        )

        writer_result = self.memory_writer.run(writer_prompt)

        console.print("[green]OK - Memory Writer complete[/green]\n")
        emit({
            "stage": "memory_writer", "status": "complete",
            "message": "Memory files created"
        })

        # ── Track newly processed email IDs ───────────────────
        updated_ids = processed_ids | {e['id'] for e in emails}
        save_processed_email_ids(updated_ids)

        # ── Step 3.5: Rebuild knowledge graph ──────────────────
        console.print("\n[bold cyan]Step 3.5/5: Rebuilding knowledge graph[/bold cyan]")
        emit({
            "stage": "graph_rebuild", "status": "started",
            "message": "Rebuilding knowledge graph with new memories..."
        })
        graph = rebuild_graph()
        console.print(f"[green]OK - Graph rebuilt: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges[/green]")
        emit({
            "stage": "graph_rebuild", "status": "complete",
            "message": f"Graph rebuilt: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges"
        })

        # ── Step 4: Action Agent ──────────────────────────────
        console.print("\n[bold cyan]Step 4/5: Action Agent[/bold cyan]")
        action_result = self.refresh_actions(
            "Generate action items from the newly updated vault.",
            progress_callback=progress_callback
        )

        # ── Step 5: Reconcile action items ────────────────────
        console.print("\n[bold cyan]Step 5/5: Reconciling action items[/bold cyan]")
        reconcile_result = self.reconcile_actions(
            "Reconcile action items against sent emails.",
            progress_callback=progress_callback
        )

        # ── Step 6: Generate insights ──────────────────────────
        console.print("\n[bold cyan]Step 6/6: Insights Agent[/bold cyan]")
        insights_result = self.generate_insights(
            "Generate insights from the full vault.",
            progress_callback=progress_callback
        )

        # ── Build summary ────────────────────────────────────
        stats = get_vault_stats()

        summary = f"Memory Build Complete! Vault now contains {stats['total']} memories:\n"
        for mtype, count in stats.items():
            if mtype != 'total' and count > 0:
                summary += f"   {mtype}: {count}\n"
        summary += f"\n{writer_result}"

        emit({"stage": "complete", "status": "complete",
              "message": writer_result, "stats": stats})

        return summary

    def refresh_actions(self, user_input: str, progress_callback=None) -> str:
        """
        Run the Action Agent to scan the full vault and generate/update
        action items with Eisenhower classification.

        This can be triggered standalone ("refresh actions") or as the
        final step of the build pipeline.

        Args:
            user_input:        The user's request.
            progress_callback: Optional function(dict) for SSE progress events.

        Returns:
            str: Summary of action items created/updated.
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Action Agent[/bold cyan] scanning vault for action items...\n")
        emit({
            "stage": "action_agent", "status": "started",
            "message": "Scanning vault and graph for action items..."
        })

        # Reset agent for fresh context
        self.action_agent.reset()

        # Set up retry callback
        def on_action_retry(attempt, max_retries, delay):
            emit({
                "stage": "action_agent", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.action_agent.on_retry = on_action_retry

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')

        prompt = (
            "Scan the entire memory vault and knowledge graph. "
            "Identify all items that require the user's attention. "
            "Create action_required memory files with Eisenhower matrix "
            "classification and justification based on the full vault context. "
            f"Today's date is {today}."
        )

        result = self.action_agent.run(prompt, max_tool_rounds=15)

        console.print("[green]OK - Action Agent complete[/green]\n")
        emit({
            "stage": "action_agent", "status": "complete",
            "message": "Action items generated"
        })

        return result

    def reconcile_actions(self, user_input: str, progress_callback=None) -> str:
        """
        Run the Reconciliation Agent to compare action items against sent emails
        and update statuses (active/closed/expired).
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Reconciliation Agent[/bold cyan] checking action item statuses...\n")
        emit({
            "stage": "reconciliation", "status": "started",
            "message": "Comparing action items against sent emails..."
        })

        self.reconciliation_agent.reset()

        def on_reconcile_retry(attempt, max_retries, delay):
            emit({
                "stage": "reconciliation", "status": "in_progress",
                "message": f"API overloaded — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.reconciliation_agent.on_retry = on_reconcile_retry

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')

        prompt = (
            "Reconcile open action items against sent emails. Steps:\n"
            "1. List all action_required memories\n"
            "2. Fetch sent emails from the last 30 days\n"
            "3. For each active action item, check if any sent email addresses it\n"
            "4. Update status to 'closed' (with reason) if action was taken\n"
            "5. Update status to 'expired' if deadline has passed with no action\n"
            f"Today's date is {today}."
        )

        result = self.reconciliation_agent.run(prompt, max_tool_rounds=15)

        console.print("[green]OK - Reconciliation complete[/green]\n")
        emit({
            "stage": "reconciliation", "status": "complete",
            "message": "Action item statuses updated"
        })

        return result

    def dismiss_insights(self, user_input: str) -> str:
        """
        Dismiss active insights via chat. Supports:
          - "dismiss all insights" — dismisses all active insights
          - "dismiss insight <keyword>" — dismisses insights matching keyword

        Updates the status field in the insight's YAML frontmatter to 'dismissed'.
        """
        import yaml as _yaml

        user_lower = user_input.lower().strip()
        dismiss_all = 'all' in user_lower

        active_insights = [
            m for m in list_memories('insights')
            if (m.get('status') or 'active') == 'active'
        ]

        if not active_insights:
            return "No active insights to dismiss."

        dismissed = []
        for insight in active_insights:
            if not dismiss_all:
                # Check if any keyword from the user's message matches the title
                keywords = user_lower.replace('dismiss insight', '').strip().split()
                if not keywords or not any(
                    kw in (insight.get('title', '') or '').lower()
                    for kw in keywords
                ):
                    continue

            # Update the file
            filepath = Path('vault') / insight['filepath']
            if not filepath.exists():
                continue

            text = filepath.read_text(encoding='utf-8')
            if not text.startswith('---'):
                continue

            parts = text.split('---', 2)
            if len(parts) < 3:
                continue

            try:
                fm = _yaml.safe_load(parts[1]) or {}
            except _yaml.YAMLError:
                continue

            fm['status'] = 'dismissed'
            yaml_str = _yaml.dump(fm, default_flow_style=False, sort_keys=False)
            filepath.write_text(f"---\n{yaml_str.strip()}\n---{parts[2]}", encoding='utf-8')
            dismissed.append(insight.get('title', insight['filepath']))

        if dismissed:
            names = '\n'.join(f"  - {t}" for t in dismissed)
            return f"Dismissed {len(dismissed)} insight(s):\n{names}"
        return "No matching active insights found to dismiss."

    def generate_insights(self, user_input: str, progress_callback=None) -> str:
        """
        Run the Insights Agent to cross-correlate the vault and discover
        hidden relationships, execution gaps, and strategic patterns.

        Creates insight memory files (max 3 per run) that reference
        2+ source memories each.

        Args:
            user_input:        The user's request.
            progress_callback: Optional function(dict) for SSE progress events.

        Returns:
            str: Summary of insights generated.
        """
        def emit(event):
            if progress_callback:
                progress_callback(event)

        console.print("\n[bold cyan]Insights Agent[/bold cyan] cross-correlating vault...\n")
        emit({
            "stage": "insights", "status": "started",
            "message": "Cross-correlating vault for patterns and insights..."
        })

        # Reset agent for fresh context
        self.insights_agent.reset()

        # Set up retry callback
        def on_insights_retry(attempt, max_retries, delay):
            emit({
                "stage": "insights", "status": "in_progress",
                "message": f"API overloaded -- retrying in {delay:.0f}s (attempt {attempt}/{max_retries})..."
            })
        self.insights_agent.on_retry = on_insights_retry

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')

        prompt = (
            "Scan the entire memory vault and knowledge graph. "
            "Cross-correlate across people, decisions, commitments, and action items "
            "to discover non-obvious relationships, execution gaps, and strategic patterns. "
            "Create up to 3 high-quality insight files. "
            "Check existing insights first to avoid duplicates. "
            f"Today's date is {today}."
        )

        result = self.insights_agent.run(prompt, max_tool_rounds=15)

        console.print("[green]OK - Insights Agent complete[/green]\n")
        emit({
            "stage": "insights", "status": "complete",
            "message": "Insights generated"
        })

        return result

    def deduplicate_vault(self) -> str:
        """
        Run the one-time vault deduplication cleanup.

        Scans all memory files, groups duplicates by name/title similarity,
        merges them into the oldest file, and deletes the extras.

        Returns:
            str: Summary of what was merged and deleted.
        """
        from memory.dedup import cleanup_duplicates

        console.print("\n[bold cyan]Vault Deduplication[/bold cyan] scanning for duplicates...\n")

        result = cleanup_duplicates()

        # Rebuild the knowledge graph after deletions
        graph = rebuild_graph()

        if result['deleted'] == 0:
            summary = "No duplicates found. Vault is clean!"
        else:
            summary = (
                f"Dedup complete: merged {result['merged']} group(s), "
                f"removed {result['deleted']} duplicate file(s).\n"
            )
            for mtype, count in result['by_type'].items():
                summary += f"   {mtype}: {count} duplicate(s) removed\n"
            summary += f"\nGraph rebuilt: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges"

        console.print(f"[green]{summary}[/green]\n")
        return summary

    def query_memory(self, user_input: str) -> str:
        """
        Send a question to the Query Agent and return its answer.

        The Query Agent will search the vault, read relevant memories,
        and synthesize a conversational answer.

        Args:
            user_input: The user's question (e.g., "Who do I email most?")

        Returns:
            str: The Query Agent's answer.
        """
        console.print("[bold cyan]Query Agent[/bold cyan] searching vault...\n")

        # Call the Query Agent's agentic loop
        return self.query_agent.run(user_input)

    def show_stats(self) -> str:
        """
        Show a simple text summary of vault statistics.

        This doesn't need an AI agent — it just reads the vault directly.

        Returns:
            str: A formatted string with memory counts per type.
        """
        stats = get_vault_stats()

        output = "Memory Vault Statistics\n\n"
        output += f"Total memories: {stats['total']}\n\n"

        # Build a simple text bar chart for each memory type
        for mtype, count in stats.items():
            if mtype != 'total':
                # Create a visual bar: "######.............." with #=filled, .=empty
                bar = '#' * count + '.' * (20 - min(count, 20))
                output += f"  {mtype:25s} {bar} {count}\n"

        return output
