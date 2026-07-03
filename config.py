"""
Configuration for the Gmail -> Anthropic pipeline.
Edit the values below before running main.py
"""

# ----------------------------------------------------------------------
# 1. ALLOWLIST: only emails FROM these addresses will be processed.
#    Matching is case-insensitive and checks if the address appears
#    in the email's "From" header.
# ----------------------------------------------------------------------
ALLOWED_SENDERS = [
    "manoj20pass@gmail.com"
    # add more allowed sender emails here
]

# ----------------------------------------------------------------------
# 2. FIXED PROMPT TEMPLATE
#    {email_body} will be replaced with the extracted email text.
# ----------------------------------------------------------------------
PROMPT_TEMPLATE = """I've received the following email/message. Please explain all the technical terms, specifications, and jargon mentioned in it — purely from a technical/engineering standpoint, without adding any organizational, business, or contextual framing (i.e., ignore who sent it, why, or what department is involved).
For each technical term or specification found in the message, explain:

What it means
Why it's technically relevant to the request
Any standard units, ranges, or industry-standard values associated with it
How it relates to the other technical terms in the same message (if applicable)

Keep the explanation structured (numbered/headed), concise per term, and skip anything that isn't technical (like greetings, names, or approval requests).
---
{email_body}
---

Please summarize the email and identify any action items."""

# ----------------------------------------------------------------------
# 3. ANTHROPIC SETTINGS
# ----------------------------------------------------------------------
GEMINI_MODEL = "models/gemini-2.5-flash"
GEMINI_MAX_TOKENS = 8192
# API key is read from the GEMINI_API_KEY environment variable.
# Do NOT hardcode your key here.

# ----------------------------------------------------------------------
# 4. POLLING / STATE
# ----------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 60          # how often to check for new emails
GMAIL_QUERY = ""                    # optional extra Gmail search filter, e.g. "in:inbox"
STATE_FILE = "state.json"           # tracks last seen message internalDate
OUTPUT_CSV = "output.csv"           # results saved here

# ----------------------------------------------------------------------
# 5. GMAIL OAUTH FILES
# ----------------------------------------------------------------------
GMAIL_CREDENTIALS_FILE = "credentials.json"  # downloaded from Google Cloud Console
GMAIL_TOKEN_FILE = "token.json"              # auto-created after first login
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
