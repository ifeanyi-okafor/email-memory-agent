# web/app.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the web server — the "bridge" between your browser and the
# AI agents. When you click buttons or type questions in the web
# interface, those actions arrive here as HTTP requests. This file
# figures out what you want, calls the right agent, and sends the
# result back to your browser.
#
# ENDPOINTS (URLs your browser can call):
#   GET  /api/auth/status     → Check if Gmail is connected
#   POST /api/auth/google     → Start the Gmail login process
#   GET  /api/stream/build    → Run email→memory pipeline with live progress
#   GET  /api/stream/refresh  → Run Action Agent with live progress
#   POST /api/query           → Ask a question about your vault
#   GET  /api/stats           → Memory counts per category
#   GET  /api/memories        → List all memories
#   GET  /api/memory/{path}   → Read one specific memory file
#   GET  /api/search          → Search all memories by text
#   GET  /                    → Serve the web interface (index.html)
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────
import os
import sys
import json
import asyncio
import queue
import threading
from pathlib import Path
from contextlib import asynccontextmanager

# FastAPI framework imports
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

# Add project root to Python's path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Our project imports
from orchestrator import Orchestrator
from memory.vault import (
    get_vault_stats, list_memories, read_memory,
    search_vault, initialize_vault, MEMORY_TYPES,
    get_processed_email_ids, save_processed_email_ids
)
from tools.gmail_tools import (
    get_gmail_service, is_authenticated, TOKEN_PATH, CREDENTIALS_PATH, SCOPES
)


# ── GLOBAL STATE ───────────────────────────────────────────────────────
# "orchestrator" is our singleton agent manager.
# Created once at startup, shared across all requests.
orchestrator = None

# Build state — tracks whether a build pipeline is running so that
# page refreshes can reconnect to the progress instead of restarting.
# Protected by a threading.Lock for thread-safe reads/writes.
import time as _time
_build_lock = threading.Lock()
build_state = {
    "status": "idle",       # idle | running | complete | error
    "stage": "",            # current pipeline stage
    "message": "",          # human-readable status message
    "step": "",             # e.g. "2/5"
    "started_at": None,     # epoch timestamp
    "finished_at": None,    # epoch timestamp
    "stats": None,          # vault stats on completion
    "source": "",           # "auto" or "manual"
}


# ── SERVER STARTUP ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run setup code when the server starts.
    
    Creates the vault folders and the Orchestrator (which creates
    all three AI agents). The "yield" pauses here while the server
    runs. Everything before yield = startup, everything after = shutdown.
    """
    global orchestrator
    initialize_vault()
    orchestrator = Orchestrator()
    print("\n[OK] Email Memory Agent web server ready!")
    print("   Open http://localhost:8000 in your browser\n")
    yield


# Create the FastAPI app
app = FastAPI(
    title="Email Memory Agent",
    description="Multi-agent system that builds a memory of you from your emails",
    lifespan=lifespan
)

# Serve static files (the frontend's HTML/CSS/JS)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── REQUEST BODY MODELS ───────────────────────────────────────────────
# These define what data the frontend sends in each request.

class BuildRequest(BaseModel):
    """Data for triggering a memory build."""
    days_back: int = 60
    max_emails: int = 150
    gmail_query: str = ""

class QueryRequest(BaseModel):
    """Data for asking a question."""
    question: str


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.get("/api/auth/status")
async def auth_status():
    """
    Check whether Gmail is already authenticated.
    
    The frontend calls this on page load to show the right UI:
      - No credentials.json → "Download credentials" message
      - Has credentials but no token → "Connect Gmail" button
      - Authenticated → "Gmail Connected" badge
    """
    return {
        "authenticated": is_authenticated(),
        "credentials_exist": CREDENTIALS_PATH.exists()
    }


@app.post("/api/auth/google")
async def auth_google():
    """
    Trigger the Gmail OAuth login flow.
    
    Opens a browser tab for Google consent. Once approved,
    saves the token to disk. Uses POST (not GET) because it
    creates state (the token file).
    """
    # Check that credentials file exists
    if not CREDENTIALS_PATH.exists():
        raise HTTPException(
            status_code=400,
            detail="Gmail credentials.json not found. Download from Google Cloud Console."
        )
    
    # Already authenticated? Just confirm.
    if is_authenticated():
        return {"status": "already_authenticated", "message": "Gmail is already connected."}
    
    # Run OAuth in a background thread (it blocks waiting for browser)
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_oauth_flow)
        return {"status": "success", "message": "Gmail connected successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth failed: {str(e)}")


def _run_oauth_flow():
    """
    Run Google OAuth flow (blocking). Opens browser, waits for approval,
    saves token. Runs in a background thread so the server doesn't freeze.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    import pickle
    
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, 'wb') as token_file:
        pickle.dump(creds, token_file)


@app.post("/api/auth/logout")
async def auth_logout():
    """
    Log out by deleting the Gmail OAuth token.

    After this, is_authenticated() will return False, and the
    frontend will show the login page again.
    """
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    return {"status": "success", "message": "Logged out successfully"}


@app.get("/api/auth/user-info")
async def auth_user_info():
    """
    Return basic info about the authenticated Gmail account.

    The frontend uses this to display the user's email address
    in the sidebar and logout header.
    """
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _get_user_profile)
        return info
    except Exception:
        return {"email": "", "authenticated": True}


def _get_user_profile():
    """Fetch Gmail profile info (blocking). Runs in a background thread."""
    service = get_gmail_service()
    profile = service.users().getProfile(userId='me').execute()
    return {"email": profile.get("emailAddress", ""), "authenticated": True}


# ============================================================================
# FRONTEND ENDPOINT
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main web interface (index.html)."""
    return FileResponse(str(static_dir / "index.html"))


# ============================================================================
# BUILD STATE ENDPOINT — Check pipeline status without starting a build
# ============================================================================

@app.get("/api/build/status")
async def get_build_status():
    """
    Return the current build pipeline state.

    The frontend polls this on page load to decide whether to start a
    new build or display the status of a running/completed one.
    """
    with _build_lock:
        return dict(build_state)


# ============================================================================
# BUILD ENDPOINT — Live progress via SSE
# ============================================================================

@app.get("/api/stream/build")
async def stream_build(
    days_back: int = 30,
    max_emails: int = 50,
    gmail_query: str = ""
):
    """
    Run the email→memory pipeline with live progress updates via SSE.

    SSE = Server-Sent Events. The browser connects and receives events:
        data: {"stage": "email_reader", "status": "started", "message": "..."}
        data: {"stage": "complete", "stats": {...}}

    HOW IT WORKS:
    1. Pipeline runs in a BACKGROUND THREAD
    2. Progress events go into a QUEUE (thread-safe mailbox)
    3. An async generator reads from queue and yields SSE events
    4. FastAPI streams those events to the browser in real-time

    CONCURRENCY GUARD:
    Only one build can run at a time. If a build is already running,
    returns a 409 Conflict so the frontend can poll /api/build/status instead.
    """
    # Prevent concurrent builds
    with _build_lock:
        if build_state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="A build is already in progress."
            )
        # Mark build as running
        build_state.update({
            "status": "running",
            "stage": "starting",
            "message": "Starting pipeline...",
            "step": "",
            "started_at": _time.time(),
            "finished_at": None,
            "stats": None,
            "source": "auto" if gmail_query == "" and days_back == 180 else "manual",
        })

    # Thread-safe queue: pipeline thread puts events in, SSE stream reads them out
    event_queue = queue.Queue()

    def _update_build_state(event):
        """Update the global build_state from a pipeline progress event."""
        with _build_lock:
            build_state["stage"] = event.get("stage", build_state["stage"])
            build_state["message"] = event.get("message", build_state["message"])

            # Compute step ratio from stage
            stage_order = ["fetching", "email_reader", "memory_writer",
                           "graph_rebuild", "action_agent", "reconciliation"]
            stage_key = event.get("stage", "")
            if stage_key in stage_order:
                idx = stage_order.index(stage_key)
                total = len(stage_order)
                build_state["step"] = f"{idx + 1}/{total}"

            if event.get("stage") == "complete":
                build_state["status"] = "complete"
                build_state["finished_at"] = _time.time()
                build_state["stats"] = event.get("stats")
                build_state["step"] = f"{len(stage_order)}/{len(stage_order)}"

            if event.get("stage") == "error":
                build_state["status"] = "error"
                build_state["finished_at"] = _time.time()

    def run_pipeline():
        """
        Run the batched email→memory pipeline in a background thread.

        Uses orchestrator.build_memory() with a progress callback that
        pushes events into the SSE queue AND updates global build_state.
        """
        try:
            def on_progress(event):
                _update_build_state(event)
                event_queue.put(event)

            orchestrator.build_memory(
                user_input="Build my memory from emails",
                progress_callback=on_progress,
                max_emails=max_emails,
                days_back=days_back,
                gmail_query=gmail_query
            )

        except Exception as e:
            error_event = {"stage": "error", "status": "error", "message": str(e)}
            _update_build_state(error_event)
            event_queue.put(error_event)
        finally:
            event_queue.put(None)  # Sentinel: signals "stream is done"

    async def event_generator():
        """
        Async generator that reads events from the queue and yields
        them as SSE-formatted strings to the browser.
        """
        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: event_queue.get(timeout=0.5)
                )
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if event is None:
                break

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# REFRESH ENDPOINT — Run Action Agent with live progress via SSE
# ============================================================================

@app.get("/api/stream/refresh")
async def stream_refresh():
    """
    Run the Action Agent with live progress updates via SSE.

    Scans the full vault and knowledge graph to generate/update
    action items with Eisenhower classification.
    """
    event_queue = queue.Queue()

    def run_refresh():
        try:
            def on_progress(event):
                event_queue.put(event)

            orchestrator.refresh_actions(
                user_input="Refresh and prioritize action items",
                progress_callback=on_progress
            )
        except Exception as e:
            event_queue.put({"stage": "error", "status": "error", "message": str(e)})
        finally:
            event_queue.put(None)

    async def event_generator():
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()

        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: event_queue.get(timeout=0.5)
                )
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if event is None:
                break

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# QUERY ENDPOINT — Ask questions about the vault
# ============================================================================

@app.post("/api/query")
async def query_memory(req: QueryRequest):
    """
    Ask a question about the user's memory vault.

    The frontend sends a POST request with {"question": "Who do I email most?"}
    and we return {"answer": "Based on your emails, you communicate most with..."}.

    The Query Agent (Agent 3) does the heavy lifting — it searches the vault,
    reads relevant memories, and synthesizes a conversational answer.
    """
    # Reject empty questions
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Run the Query Agent in a background thread.
    # The agent calls Claude (which is a blocking HTTP request), so we
    # use run_in_executor to keep the web server responsive.
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, orchestrator.query_memory, req.question)
    return {"answer": result}


# ============================================================================
# VAULT BROWSING ENDPOINTS — Read vault data directly
# ============================================================================

@app.get("/api/stats")
async def get_stats():
    """
    Get vault statistics — how many memories exist in each category.

    Returns: {"total": 15, "by_type": {"decisions": 3, "people": 5, ...}}
    """
    stats = get_vault_stats()
    return {
        "total": stats.get("total", 0),
        # Build a dict of just the type counts (exclude "total")
        "by_type": {k: v for k, v in stats.items() if k != "total"}
    }


@app.get("/api/memories")
async def get_memories(memory_type: str = None):
    """
    List all memories with basic info (title, type, date, tags).

    Optional query parameter "memory_type" filters to one category.
    Example: GET /api/memories?memory_type=people
    """
    # Validate the memory type if provided
    if memory_type and memory_type not in MEMORY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {MEMORY_TYPES}")

    # Get the list of memories from the vault
    memories = list_memories(memory_type)
    return {"memories": memories, "count": len(memories)}


@app.get("/api/memory/{memory_type}/{filename}")
async def get_memory_file(memory_type: str, filename: str):
    """
    Read a specific memory file — returns both YAML metadata and markdown content.

    The URL path contains the memory type and filename:
    Example: GET /api/memory/people/sarah-chen-a1b2.md

    Returns: {"frontmatter": {...}, "content": "...", "filepath": "..."}
    """
    filepath = f"{memory_type}/{filename}"
    result = read_memory(filepath)

    if result is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@app.get("/api/search")
async def search_memories(q: str = ""):
    """
    Search across all memories by text (case-insensitive).

    Example: GET /api/search?q=morning+meetings

    Returns matching memories with a snippet of context around the match.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query required")

    results = search_vault(q)
    return {"results": results, "count": len(results)}
