# tools/email_filter.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the "email noise filter." It sits BETWEEN the email fetcher
# (gmail_tools.py) and the Email Reader Agent, acting as a bouncer that
# decides which emails are worth spending LLM tokens on.
#
# It does TWO things:
#   1. Classifies a single email as "signal" (worth processing) or "noise"
#      (newsletters, receipts, notifications, cold outreach)
#   2. Splits a batch of emails into signal and noise lists
#
# IMPORTANT: This file has NO artificial intelligence in it.
# It's pure heuristics — keyword matching, regex patterns, and label checks.
# The goal is to filter out obvious noise BEFORE we send emails to the LLM,
# saving tokens and reducing vault clutter.
# ============================================================================

# ── IMPORTS ────────────────────────────────────────────────────────────
import re


# ── NOISE LABELS ──────────────────────────────────────────────────────
# Gmail automatically sorts emails into categories using these label IDs.
# If an email has one of these labels, it's almost certainly not a
# person-to-person conversation worth analyzing.

NOISE_LABELS = {
    'CATEGORY_PROMOTIONS',   # Marketing emails, deals, ads
    'CATEGORY_SOCIAL',       # Social network notifications (LinkedIn, Facebook)
    'CATEGORY_UPDATES',      # Automated updates (shipping, statements, receipts)
    'CATEGORY_FORUMS',       # Mailing lists, group discussions
    'SPAM',                  # Gmail's spam filter already flagged it
    'TRASH',                 # User already threw it away
}


# ── AUTOMATED SENDER PATTERNS ────────────────────────────────────────
# These are common "from" address prefixes used by automated systems.
# A real human almost never sends from "noreply@..." or "notifications@..."
# We compile them into a single regex for fast matching.

AUTOMATED_SENDER_PATTERNS = [
    r'noreply@', r'no-reply@', r'notifications@', r'notify@',
    r'mailer-daemon@', r'bounce@', r'donotreply@', r'do-not-reply@',
    r'automated@', r'alerts@', r'digest@', r'updates@',
    r'newsletter@', r'news@', r'info@', r'marketing@',
    r'promo@', r'support@', r'helpdesk@', r'billing@',
    r'receipts@', r'orders@', r'shipping@', r'subscriptions@',
]

# Combine all patterns into one regex with | (OR) for efficiency.
# re.IGNORECASE makes it match "NoReply@" and "NOREPLY@" too.
# The negative lookbehind (?<![a-zA-Z]) ensures we don't match mid-word,
# e.g. "anews@company.com" should NOT match the "news@" pattern.
_AUTOMATED_SENDER_RE = re.compile(
    r'(?<![a-zA-Z])(?:' + '|'.join(AUTOMATED_SENDER_PATTERNS) + r')',
    re.IGNORECASE
)


# ── TRANSACTIONAL SUBJECT PATTERNS ───────────────────────────────────
# These subject line fragments indicate automated transactional emails
# (order confirmations, receipts, shipping updates, etc.).
# Nobody needs an AI to remember that their package shipped.

TRANSACTIONAL_SUBJECT_PATTERNS = [
    r'order\s+confirm',        # "Order confirmed", "Order confirmation"
    r'your\s+receipt',         # "Your receipt from..."
    r'invoice\s+#',            # "Invoice #12345"
    r'shipping\s+confirm',     # "Shipping confirmation"
    r'delivery\s+notif',       # "Delivery notification"
    r'password\s+reset',       # "Password reset request"
    r'verify\s+your',          # "Verify your email address"
    r'your\s+statement',       # "Your monthly statement"
    r'account\s+alert',        # "Account alert: suspicious login"
    r'subscription\s+renew',   # "Subscription renewal notice"
]

_TRANSACTIONAL_SUBJECT_RE = re.compile(
    '|'.join(TRANSACTIONAL_SUBJECT_PATTERNS),
    re.IGNORECASE
)


# ── NEWSLETTER BODY MARKERS ──────────────────────────────────────────
# If the email body contains these phrases, it's almost certainly a
# mass-mailed newsletter or marketing email. Real person-to-person
# emails don't have "unsubscribe" links or "manage subscriptions" footers.

NEWSLETTER_BODY_MARKERS = [
    r'unsubscribe',
    r'opt[\s._-]?out',              # "opt out", "opt-out", "opt_out"
    r'email\s+preferences',
    r'manage\s+subscriptions',
    r'view\s+in\s+browser',
]

_NEWSLETTER_BODY_RE = re.compile(
    '|'.join(NEWSLETTER_BODY_MARKERS),
    re.IGNORECASE
)


# ── PUBLIC API ────────────────────────────────────────────────────────

def classify_email(email: dict) -> str:
    """
    Classify a single email as 'signal' or 'noise' using heuristics.

    This is a pure keyword/label/regex classifier — no LLM calls.
    It checks four layers of filters in order (first match wins):

      1. Gmail noise labels (PROMOTIONS, SOCIAL, SPAM, etc.)
      2. Automated sender patterns (noreply@, notifications@, etc.)
      3. Transactional subject patterns (order confirm, password reset, etc.)
      4. Newsletter body markers (unsubscribe, opt out, etc.)

    If none of the noise checks trigger, the email is considered signal.

    Args:
        email: A dictionary with optional keys: 'from', 'subject', 'body', 'labels'.
               Missing keys default to empty string/list (the function won't crash).

    Returns:
        'signal' if the email looks like a real person-to-person conversation.
        'noise' if it matches any automated/transactional/newsletter pattern.
    """

    # ── Extract fields safely ─────────────────────────────────────
    # Use .get() with defaults so missing keys don't cause crashes.
    # This is important because emails from different sources may have
    # different fields available.
    sender = email.get('from', '') or ''
    subject = email.get('subject', '') or ''
    body = email.get('body', '') or ''
    labels = email.get('labels', []) or []

    # ── Check 1: Gmail noise labels ───────────────────────────────
    # This is the cheapest check — just set intersection.
    # Gmail already did the hard work of categorizing these emails.
    if set(labels) & NOISE_LABELS:
        return 'noise'

    # ── Check 2: Automated sender patterns ────────────────────────
    # Look for telltale automated sender prefixes in the "from" field.
    if _AUTOMATED_SENDER_RE.search(sender):
        return 'noise'

    # ── Check 3: Transactional subject patterns ───────────────────
    # Check if the subject line matches common transactional patterns.
    if _TRANSACTIONAL_SUBJECT_RE.search(subject):
        return 'noise'

    # ── Check 4: Newsletter body markers ──────────────────────────
    # Check the body for mass-email footers like "unsubscribe".
    if _NEWSLETTER_BODY_RE.search(body):
        return 'noise'

    # ── Default: signal ───────────────────────────────────────────
    # If no noise patterns matched, this email is worth processing.
    return 'signal'


def filter_emails(emails: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split a list of emails into signal and noise buckets.

    This is the batch version of classify_email(). Use it to pre-filter
    a whole inbox fetch before sending emails to the Email Reader Agent.

    Args:
        emails: A list of email dictionaries (same format as classify_email).

    Returns:
        A tuple of (signal_emails, noise_emails) — two separate lists.
        Every email from the input appears in exactly one of the two lists.
    """
    signal = []
    noise = []

    for email in emails:
        if classify_email(email) == 'signal':
            signal.append(email)
        else:
            noise.append(email)

    return signal, noise
