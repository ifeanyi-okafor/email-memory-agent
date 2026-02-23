# main.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "start button" for the entire application. When you run
# "python main.py" in your terminal, this file launches the web server
# that powers the Memory Vault web interface.
#
# It does three things:
#   1. Loads your API key from the .env file
#   2. Checks that the API key is set (exits with a helpful error if not)
#   3. Starts the FastAPI web server using uvicorn
#
# After running, you open http://localhost:8000 in your browser to use
# the app.
#
# USAGE:
#   python main.py                  → Start on port 8000 (default)
#   python main.py --port 3000      → Start on a different port
#   python main.py --host 0.0.0.0   → Make accessible from other devices
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────

# "os" lets us read environment variables (like the API key)
import os

# "sys" lets us exit the program with an error code
import sys

# "argparse" is Python's built-in tool for parsing command-line arguments.
# It lets us support flags like "--port 3000" and "--host 0.0.0.0".
import argparse


# ── LOAD ENVIRONMENT VARIABLES ─────────────────────────────────────────

# "python-dotenv" reads the .env file in the project root and loads its
# contents as environment variables. This is how we safely manage secrets
# like API keys — they go in .env (which is never committed to git).
#
# We wrap this in try/except because dotenv might not be installed yet
# (the user might be running this before pip install).
try:
    from dotenv import load_dotenv
    load_dotenv()  # Read .env file and set environment variables
except ImportError:
    # If dotenv isn't installed, that's OK — the user might have set
    # the environment variable manually (via "export" in their terminal).
    pass


# ── CHECK FOR API KEY ──────────────────────────────────────────────────

# The Anthropic API key is REQUIRED — without it, our agents can't call
# Claude. Check that it's set before doing anything else.
#
# "os.environ.get('ANTHROPIC_API_KEY')" tries to read the environment
# variable. If it's not set, it returns None (which is "falsy" in Python).
if not os.environ.get('ANTHROPIC_API_KEY'):
    # Print a helpful error message and exit with code 1 (= error)
    print("Error: ANTHROPIC_API_KEY not set.")
    print("   Create a .env file with: ANTHROPIC_API_KEY=sk-ant-your-key")
    print("   Or run: export ANTHROPIC_API_KEY=sk-ant-your-key")
    sys.exit(1)


# ── MAIN FUNCTION ──────────────────────────────────────────────────────

def main():
    """
    Parse command-line arguments and start the web server.

    This function:
    1. Reads --port and --host flags from the command line
    2. Prints a nice startup banner
    3. Launches uvicorn to serve our FastAPI app
    """

    # ── Parse command-line arguments ───────────────────────────
    # "ArgumentParser" creates a command-line argument parser.
    # It automatically generates help text (try: python main.py --help)
    parser = argparse.ArgumentParser(
        description="Email Memory Agent — Build a memory of yourself from your emails"
    )

    # "--port" flag: which port number to run the server on.
    # Default is 8000, so the app will be at http://localhost:8000
    parser.add_argument(
        '--port', type=int, default=8000,
        help="Port to run the web server on (default: 8000)"
    )

    # "--host" flag: which network interface to bind to.
    # "127.0.0.1" (default) means only accessible from this computer.
    # "0.0.0.0" means accessible from other devices on your network.
    parser.add_argument(
        '--host', type=str, default='127.0.0.1',
        help="Host to bind to. Use 0.0.0.0 for network access (default: 127.0.0.1)"
    )

    # Parse the arguments (reads sys.argv behind the scenes)
    args = parser.parse_args()

    # ── Check that uvicorn is installed ────────────────────────
    # Uvicorn is the ASGI server that actually runs our FastAPI app.
    # Think of FastAPI as the app and uvicorn as the server that hosts it.
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    # ── Print a startup banner ─────────────────────────────────
    print()
    print("  ===========================================")
    print("        Email Memory Agent                  ")
    print("        Multi-Agent System with MCP         ")
    print("  ===========================================")
    print(f"   http://{args.host}:{args.port}              ")
    print("   Press Ctrl+C to stop                     ")
    print("  ===========================================")
    print()

    # ── Start the web server ───────────────────────────────────
    # "uvicorn.run" starts the server.
    # "web.app:app" tells uvicorn: "import the 'app' object from web/app.py"
    # "reload=False" means don't auto-restart when files change
    #   (set to True during development for convenience)
    # "log_level" controls how much detail appears in the terminal
    uvicorn.run(
        "web.app:app",       # Import path to our FastAPI application
        host=args.host,      # Network interface to bind to
        port=args.port,      # Port number to listen on
        reload=False,        # Don't auto-reload on file changes
        log_level="info"     # Show info-level logs (requests, startup, etc.)
    )


# ── ENTRY POINT ────────────────────────────────────────────────────────
# This "if" block runs only when you execute the file directly:
#   python main.py         ← this runs main()
#   import main            ← this does NOT run main()
#
# It's a Python convention that prevents the main function from running
# accidentally if someone imports this file as a module.

if __name__ == "__main__":
    main()
