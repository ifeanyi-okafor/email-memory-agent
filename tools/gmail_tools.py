# tools/gmail_tools.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "email fetcher." It connects to your Gmail account, downloads
# your emails, and converts them into simple Python data that our AI agents
# can read and analyze.
#
# It does THREE things:
#   1. Logs into Gmail using OAuth (a secure login system)
#   2. Fetches emails matching your criteria (date range, filters, etc.)
#   3. Converts each email into a simple dictionary (like a contact card)
#
# IMPORTANT: This file has NO artificial intelligence in it.
# It's pure "plumbing" — getting data from point A to point B.
# The AI agents in the "agents/" folder do the smart analysis.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────
# These are libraries (pre-written code) that we need. Think of them like
# apps on your phone — each one does a specific job.

# "os" lets us interact with the operating system (read files, etc.)
import os

# "json" lets us work with JSON data (a common data format, like a
# structured text file that computers love to read)
import json

# "base64" lets us decode encoded text. Gmail sends email bodies as
# base64-encoded strings (a way to safely transmit text over the internet).
# We need to decode them back into readable text.
import base64

# "pickle" lets us save Python objects to a file and load them back later.
# We use it to save the Gmail login token so you don't have to log in
# every time you run the app.
import pickle

# "datetime" and "timedelta" help us work with dates and time ranges.
# We use them to calculate "30 days ago" for filtering emails.
from datetime import datetime, timedelta

# "Path" makes file path handling easy and cross-platform.
from pathlib import Path

# "parseaddr" is a helper that splits "John Doe <john@example.com>"
# into two parts: the name ("John Doe") and the email ("john@example.com").
from email.utils import parseaddr

# ── GOOGLE API IMPORTS ─────────────────────────────────────────────────
# These are Google's official libraries for talking to Gmail.

# "Request" is used to refresh expired login tokens (like auto-renewing
# a library card before it expires).
from google.auth.transport.requests import Request

# "Credentials" represents your Gmail login session.
from google.oauth2.credentials import Credentials

# "InstalledAppFlow" handles the OAuth login process — it opens your
# browser, shows Google's consent screen, and brings back a token.
from google_auth_oauthlib.flow import InstalledAppFlow

# "build" creates a Gmail API "service" object — the thing we use to
# actually fetch emails. Think of it like opening the Gmail app.
from googleapiclient.discovery import build


# ── CONSTANTS ──────────────────────────────────────────────────────────
# These are values that never change while the program runs.

# "SCOPES" tells Google what permissions we want.
# "gmail.readonly" = we can READ emails but NEVER send, delete, or modify.
# This is the minimum permission we need and the safest option.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# "TOKEN_PATH" is where we save the login token after you authenticate.
# It's a file called "token.pickle" in the config/ folder.
TOKEN_PATH = Path('config/token.pickle')

# "CREDENTIALS_PATH" is where Google's OAuth credentials file should be.
# You download this file from Google Cloud Console (see the tutorial).
CREDENTIALS_PATH = Path('config/credentials.json')


# ── AUTHENTICATION ─────────────────────────────────────────────────────

def is_authenticated() -> bool:
    """
    Check if we already have a valid Gmail login token.

    This function does NOT log you in — it just checks if a saved token
    exists and is still usable. The web frontend calls this on page load
    to decide whether to show "Connect Gmail" or "Gmail Connected."

    HOW IT WORKS:
    1. Check if the token file exists on disk
    2. If yes, load it and check if it's still valid (or refreshable)
    3. Return True or False

    Returns:
        bool: True if we have a usable token, False if not.
    """
    # Step 1: Does the token file even exist?
    if not TOKEN_PATH.exists():
        # No token file = never authenticated. Return False.
        return False

    # Step 2: Try to load and validate the token
    try:
        # Open the token file and load the saved credentials
        with open(TOKEN_PATH, 'rb') as f:
            creds = pickle.load(f)

        # A token is "usable" if:
        # - It's still valid (not expired), OR
        # - It's expired BUT has a "refresh token" (a special token that
        #   lets us get a new one without re-authenticating)
        return creds and (creds.valid or (creds.expired and creds.refresh_token))

    except Exception:
        # If anything goes wrong reading the file, treat it as not authenticated
        return False


def get_gmail_service():
    """
    Log into Gmail and return a "service" object we can use to fetch emails.

    This is the main authentication function. Here's what happens:

    FIRST TIME (no saved token):
        1. Opens your web browser to Google's login page
        2. You sign in and click "Allow" to grant read-only access
        3. Google sends back a token (like a temporary password)
        4. We save that token to config/token.pickle for next time

    SUBSEQUENT TIMES (saved token exists):
        1. Load the saved token from disk
        2. If it's expired, silently refresh it (no browser needed)
        3. Ready to go!

    Returns:
        A Gmail API "service" object — think of this as an open connection
        to Gmail that lets us send commands like "fetch my emails."
    """
    # "creds" will hold our login credentials. Start as None (nothing).
    creds = None

    # ── Try to load a saved token ──────────────────────────────
    # Check if we previously saved a token from a past login
    if TOKEN_PATH.exists():
        # Open the file in "read binary" mode ('rb') because pickle
        # files are binary (not plain text)
        with open(TOKEN_PATH, 'rb') as token_file:
            # "pickle.load" reconstructs the Python object we saved earlier
            creds = pickle.load(token_file)

    # ── Validate or refresh the token ──────────────────────────
    # Check if we have valid credentials. If not, we need to fix that.
    if not creds or not creds.valid:

        # Case A: Token exists but expired, and we have a refresh token.
        # This is like renewing your library card — quick and automatic.
        if creds and creds.expired and creds.refresh_token:
            print("[*] Refreshing expired Gmail token...")
            # "refresh" contacts Google and gets a fresh token silently
            creds.refresh(Request())

        # Case B: No token at all (or no refresh token). We need to do
        # the full login process with the browser.
        else:
            # First, make sure the credentials.json file exists
            if not CREDENTIALS_PATH.exists():
                # If it doesn't exist, raise an error with helpful instructions
                raise FileNotFoundError(
                    f"❌ Gmail credentials not found at {CREDENTIALS_PATH}\n"
                    "   Download from Google Cloud Console → APIs & Services → Credentials\n"
                    "   See tutorial Part 3 for detailed instructions."
                )

            print("[*] Opening browser for Gmail authentication...")
            print("   (You'll only need to do this once)")

            # "InstalledAppFlow" reads our credentials.json and creates an
            # OAuth flow — it knows how to talk to Google's login system
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),  # Path to our credentials file
                SCOPES                   # What permissions we're requesting
            )

            # "run_local_server" does the magic:
            # 1. Starts a tiny temporary web server on your computer
            # 2. Opens your browser to Google's consent page
            # 3. After you click "Allow", Google redirects back to that
            #    tiny server with the token
            # "port=0" means "pick any available port automatically"
            creds = flow.run_local_server(port=0)

        # ── Save the token for next time ───────────────────────
        # Create the config/ folder if it doesn't exist yet
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Save the credentials to disk using pickle
        with open(TOKEN_PATH, 'wb') as token_file:
            pickle.dump(creds, token_file)

        print("[OK] Gmail authentication successful!")

    # ── Build and return the Gmail service ─────────────────────
    # "build" creates a Gmail API service using our credentials.
    # Parameters:
    #   'gmail'  = which Google API to use (Gmail)
    #   'v1'     = which version of the API
    #   credentials = our login token
    return build('gmail', 'v1', credentials=creds)


# ── FETCH EMAILS ───────────────────────────────────────────────────────

def fetch_emails(max_results: int = 150, query: str = '',
                 days_back: int = 60) -> list[dict]:
    """
    Fetch emails from Gmail and return them as a list of simple dictionaries.

    Think of this function as telling Gmail: "Give me my recent emails,
    and format each one as a neat card with the subject, sender, date,
    and body text."

    Args:
        max_results: The maximum number of emails to fetch. Default is 50.
                     Setting this higher means more data but slower processing.

        query:       A Gmail search filter — same syntax you'd type in Gmail's
                     search bar. Examples:
                       "from:boss@company.com"   — emails from your boss
                       "subject:project update"  — emails about projects
                       "is:important"            — emails Gmail flagged as important
                       "label:work"              — emails with the "work" label

        days_back:   How many days back to look. Default is 60 (two months).
                     "7" would mean just the last week.

    Returns:
        A list of dictionaries. Each dictionary represents one email:
        {
            'id': 'abc123',           ← Gmail's unique ID for this email
            'thread_id': 'def456',    ← ID of the email thread (conversation)
            'subject': 'Hello!',      ← The email's subject line
            'from': 'Jane <j@co.com>',← Full "from" field
            'from_email': 'j@co.com', ← Just the email address
            'from_name': 'Jane',      ← Just the person's name
            'to': 'you@gmail.com',    ← Who the email was sent to
            'date': 'Mon, 18 Feb...', ← When it was sent
            'snippet': 'Hey, just...',← Gmail's short preview text
            'body': 'Full text...',   ← The complete email body
            'labels': ['INBOX', ...]  ← Gmail labels on this email
        }
    """

    # Step 1: Log into Gmail (or use existing session)
    # "service" is our connection to Gmail — we'll use it to send requests
    service = get_gmail_service()

    # Step 2: Build the time filter
    # Calculate the date that is "days_back" days ago from today
    # and format it as "YYYY/MM/DD" which Gmail's search understands
    after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

    # Start with "after:2026/01/19" to only get recent emails
    full_query = f'after:{after_date}'

    # If the user specified an additional filter, add it to the query
    # For example: "is:important after:2026/01/19"
    if query:
        full_query = f'{query} {full_query}'

    print(f"[FETCH] Fetching emails (query: '{full_query}', max: {max_results})...")

    # Step 3: Ask Gmail for a list of email IDs matching our query
    # This doesn't download the full emails yet — just their IDs.
    # It's like getting a list of tracking numbers before opening packages.
    results = service.users().messages().list(
        userId='me',           # 'me' means the currently logged-in user
        q=full_query,          # Our search query
        maxResults=max_results  # How many to return at most
    ).execute()  # ".execute()" actually sends the request to Gmail

    # "messages" is a list of {id, threadId} dictionaries.
    # If no emails match, it might be empty or missing entirely.
    messages = results.get('messages', [])

    # If no emails found, return an empty list
    if not messages:
        print("   No emails found matching criteria.")
        return []

    print(f"   Found {len(messages)} emails. Fetching details...")

    # Step 4: Fetch the full details of each email
    # Now we loop through each ID and download the complete email.
    # "emails" will be our final list of email dictionaries.
    emails = []

    for msg_ref in messages:
        try:
            # Fetch the full email using its ID
            # "format='full'" means we want headers AND body content
            msg = service.users().messages().get(
                userId='me',
                id=msg_ref['id'],  # The unique ID from step 3
                format='full'       # Get everything (headers + body)
            ).execute()

            # Parse the raw Gmail data into a clean, simple dictionary
            # (see the _parse_message function below)
            email_data = _parse_message(msg)

            # If parsing succeeded, add this email to our list
            if email_data:
                emails.append(email_data)

        except Exception as e:
            # If something goes wrong with one email, skip it and continue
            # with the rest. We don't want one bad email to stop everything.
            print(f"   [WARN] Error fetching message {msg_ref['id']}: {e}")
            continue

    print(f"[OK] Successfully fetched {len(emails)} emails")

    # Return the final list of email dictionaries
    return emails


# ── EMAIL PARSING ──────────────────────────────────────────────────────

def _parse_message(msg: dict) -> dict | None:
    """
    Convert a raw Gmail API message into a clean, simple dictionary.

    Gmail's raw format is deeply nested and confusing. This function
    flattens it into a simple structure that's easy to work with.

    The underscore prefix "_" in the name is a Python convention meaning
    "this is a private/internal function" — it's only meant to be called
    by other functions in this file, not from outside.

    Args:
        msg: The raw message dictionary from Gmail's API

    Returns:
        A clean dictionary with the email's key fields, or None if parsing fails.
    """

    # ── Extract headers ────────────────────────────────────────
    # Gmail stores email headers (subject, from, to, date) as a list of
    # {name: ..., value: ...} pairs deep inside the response.
    # We need to dig them out.
    headers = msg.get('payload', {}).get('headers', [])

    # Convert the list of headers into a simple dictionary.
    # We only care about certain headers (subject, from, to, date, cc, bcc).
    header_dict = {}
    for h in headers:
        # Convert header name to lowercase for consistent matching
        name = h['name'].lower()
        if name in ('subject', 'from', 'to', 'date', 'cc', 'bcc'):
            header_dict[name] = h['value']

    # ── Parse the "From" field ─────────────────────────────────
    # The "from" field often looks like: "John Doe <john@example.com>"
    # "parseaddr" splits this into name and email address separately.
    from_name, from_email = parseaddr(header_dict.get('from', ''))

    # ── Extract the email body ─────────────────────────────────
    # The body might be plain text, HTML, or nested in multipart sections.
    # "_extract_body" handles all these cases (see below).
    body = _extract_body(msg.get('payload', {}))

    # ── Build and return the clean dictionary ──────────────────
    return {
        'id': msg['id'],                                        # Gmail's unique ID
        'thread_id': msg['threadId'],                            # Conversation thread ID
        'subject': header_dict.get('subject', '(no subject)'),   # Subject line (or default)
        'from': header_dict.get('from', ''),                     # Full "from" field
        'from_email': from_email,                                # Just the email address
        'from_name': from_name or from_email,                    # Name, or email if no name
        'to': header_dict.get('to', ''),                         # Who it was sent to
        'date': header_dict.get('date', ''),                     # When it was sent
        'snippet': msg.get('snippet', ''),                       # Gmail's short preview
        'body': body[:1000],                                     # Body text (truncated to 1000 chars)
        'labels': msg.get('labelIds', [])                        # Gmail labels (INBOX, etc.)
    }


def _extract_body(payload: dict) -> str:
    """
    Dig through Gmail's nested message structure to find the plain text body.

    Emails can be structured in several ways:
      - SIMPLE: The body is right there in the payload
      - MULTIPART: The body is nested inside "parts" (text, HTML, attachments)
      - NESTED MULTIPART: Parts inside parts inside parts

    We prefer plain text (text/plain) over HTML (text/html) because it's
    cleaner for our AI to analyze.

    Args:
        payload: The "payload" section of a Gmail message

    Returns:
        The email body as a plain text string.
    """

    # ── Case 1: Simple message ─────────────────────────────────
    # Check if the body data is directly in the payload
    if payload.get('body', {}).get('data'):
        # Gmail encodes the body as "base64url" — a safe way to transmit
        # binary data as text. We need to decode it back to regular text.
        return base64.urlsafe_b64decode(
            payload['body']['data']
        ).decode('utf-8', errors='replace')
        # "errors='replace'" means: if there's a character we can't decode,
        # replace it with a ? instead of crashing

    # ── Case 2: Multipart message ──────────────────────────────
    # If no direct body, look through the "parts" list
    parts = payload.get('parts', [])

    # We'll collect both plain text and HTML, but prefer plain text
    text_body = ''
    html_body = ''

    for part in parts:
        # "mimeType" tells us what kind of content this part is
        mime_type = part.get('mimeType', '')

        if mime_type == 'text/plain' and part.get('body', {}).get('data'):
            # This part is plain text — decode it
            text_body = base64.urlsafe_b64decode(
                part['body']['data']
            ).decode('utf-8', errors='replace')

        elif mime_type == 'text/html' and part.get('body', {}).get('data'):
            # This part is HTML — decode it (fallback if no plain text)
            html_body = base64.urlsafe_b64decode(
                part['body']['data']
            ).decode('utf-8', errors='replace')

        elif mime_type.startswith('multipart/'):
            # This part itself contains more parts — go deeper (recursion!)
            # "Recursion" means a function calling itself, like opening a
            # box that contains another box that contains another box.
            nested = _extract_body(part)
            if nested:
                text_body = text_body or nested

    # Return plain text if we found it, otherwise HTML, otherwise empty string
    return text_body or html_body or ''
