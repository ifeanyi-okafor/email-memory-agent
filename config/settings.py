# config/settings.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "control panel" for the entire project. Every setting that
# might change — file paths, API keys, model names — lives here in one
# place. That way, if you ever need to change something, you change it
# here instead of hunting through 10 different files.
#
# Think of it like the settings page on your phone — one place for
# everything.
# ============================================================================

# "os" is a built-in Python module that lets us talk to the operating system.
# We use it here to read "environment variables" — secret values like API
# keys that we store outside our code for security.
import os

# "Path" is a helper from Python's "pathlib" module that makes working with
# file and folder paths easier and safer across Windows, Mac, and Linux.
from pathlib import Path


# ── FILE PATHS ─────────────────────────────────────────────────────────
# These tell our code where to find important files and folders.

# "PROJECT_ROOT" is the top-level folder of our project.
# "__file__" is a special Python variable meaning "this current file" (settings.py).
# ".parent" means "go up one folder". We go up twice:
#   settings.py → config/ → email-memory-agent/ (that's our root)
PROJECT_ROOT = Path(__file__).parent.parent

# "VAULT_ROOT" is where all our memory files will be stored.
# It's a folder called "vault" inside our project.
VAULT_ROOT = PROJECT_ROOT / "vault"

# "CONFIG_DIR" is where configuration files live (this folder).
CONFIG_DIR = PROJECT_ROOT / "config"

# "CREDENTIALS_PATH" is where Google expects to find the OAuth credentials
# file you downloaded from Google Cloud Console.
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"

# "TOKEN_PATH" is where we save the Gmail login token after you authenticate.
# Once saved, you won't need to log in again (until the token expires).
TOKEN_PATH = CONFIG_DIR / "token.pickle"


# ── LLM (Large Language Model) SETTINGS ────────────────────────────────
# These control which AI model our agents use.

# "ANTHROPIC_API_KEY" is your secret key for using Claude.
# We read it from an environment variable (set in your .env file) so it
# never appears in the code itself — that's a security best practice.
# The "or empty string" part means: if the key isn't set, use "" (blank).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# "MODEL" is the specific Claude model we use. "claude-sonnet-4-20250514"
# is a good balance of intelligence and speed. Think of it like choosing
# between economy and first class — Sonnet is business class.
MODEL = "claude-sonnet-4-20250514"

# "MAX_TOKENS" is the maximum length of each AI response.
# 4096 tokens is roughly 3,000 words — plenty for our use case.
MAX_TOKENS = 4096


# ── GMAIL SETTINGS ─────────────────────────────────────────────────────
# These control how we interact with Gmail.

# "GMAIL_SCOPES" defines what permissions we're asking for.
# "gmail.readonly" means: we can READ emails but NEVER modify, delete,
# or send anything. This is the safest permission level.
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# "DEFAULT_MAX_EMAILS" is how many emails to fetch if the user doesn't specify.
DEFAULT_MAX_EMAILS = 500

# "DEFAULT_DAYS_BACK" is how far back in time to look for emails.
DEFAULT_DAYS_BACK = 180

# "EMAIL_BATCH_SIZE" is how many emails to send to Claude per batch.
# Each batch gets its own agent run with a fresh context window, so this
# controls the token budget per batch. 10 emails ≈ 10K tokens of input,
# well within Claude's limits.
EMAIL_BATCH_SIZE = 10

# ── RETRY SETTINGS ──────────────────────────────────────────────────
# These control how the system retries when the Claude API is overloaded
# or rate-limited. Uses exponential backoff: wait 1s, 2s, 4s, 8s, 16s.

# Maximum number of retries before giving up on a single API call.
# With base delay 2s and exponential backoff, 8 retries gives waits of:
# 2s, 4s, 8s, 16s, 32s, 64s, 128s = ~4 minutes of total wait time.
API_MAX_RETRIES = 8

# Base delay in seconds for the first retry. Doubles each attempt.
API_RETRY_BASE_DELAY = 2.0


# ── MEMORY VAULT SETTINGS ─────────────────────────────────────────────
# These define the types (categories) of memories we can create.
# Each type gets its own folder in the vault.

# "MEMORY_TYPES" is a list of all valid memory categories.
# When the AI analyzes your emails, it sorts what it finds into these
# buckets — just like organizing photos into albums.
MEMORY_TYPES = [
    'decisions',    # Choices you've made ("chose React over Vue")
    'people',       # People you interact with ("Sarah — CTO at Acme")
    'commitments',  # Promises and deadlines ("review PRs by Friday")
]
