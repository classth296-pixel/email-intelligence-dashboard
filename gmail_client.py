"""
Gmail API helpers: OAuth2 login, fetching new messages, parsing body text.
"""
import base64
import json
import os
from email.utils import parseaddr

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config


def get_gmail_service():
    """Authenticate via OAuth2 (browser flow on first run, cached after)."""
    creds = None
    if os.path.exists(config.GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            config.GMAIL_TOKEN_FILE, config.GMAIL_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.GMAIL_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {config.GMAIL_CREDENTIALS_FILE}. "
                    "Download OAuth client credentials from Google Cloud Console "
                    "(APIs & Services -> Credentials -> OAuth client ID -> Desktop app) "
                    "and place the file here."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(config.GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def load_state():
    if os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_internal_date": "0", "seen_ids": []}


def save_state(state):
    # keep seen_ids list from growing forever; last 500 is plenty
    state["seen_ids"] = state.get("seen_ids", [])[-500:]
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _extract_body(payload):
    """Recursively pull plain text (preferred) or HTML body from a Gmail payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

    if "parts" in payload:
        # First pass: look for text/plain
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        # Second pass: fall back to text/html, then recurse into nested parts
        for part in payload["parts"]:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    return _strip_html(html)
            if "parts" in part:
                result = _extract_body(part)
                if result:
                    return result

    if mime_type == "text/html" and body_data:
        html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        return _strip_html(html)

    return ""


def _strip_html(html):
    """Very basic HTML tag stripper (no external deps required)."""
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_new_messages(service, state):
    """
    Fetch messages newer than state['last_internal_date'].
    Returns list of dicts: {id, sender_email, sender_raw, subject, body, internal_date}
    """
    query = config.GMAIL_QUERY.strip()
    results = service.users().messages().list(
        userId="me", q=query if query else None, maxResults=50
    ).execute()

    message_refs = results.get("messages", [])
    new_messages = []
    seen_ids = set(state.get("seen_ids", []))
    last_internal_date = int(state.get("last_internal_date", "0"))
    max_internal_date = last_internal_date

    for ref in message_refs:
        msg_id = ref["id"]
        if msg_id in seen_ids:
            continue

        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        internal_date = int(msg.get("internalDate", "0"))
        if internal_date <= last_internal_date:
            # already processed in a previous poll (or older mail)
            seen_ids.add(msg_id)
            continue

        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        sender_raw = headers.get("from", "")
        sender_name, sender_email = parseaddr(sender_raw)
        subject = headers.get("subject", "(no subject)")
        body = _extract_body(msg["payload"])

        new_messages.append({
            "id": msg_id,
            "sender_email": sender_email.lower(),
            "sender_raw": sender_raw,
            "subject": subject,
            "body": body,
            "internal_date": internal_date,
        })

        seen_ids.add(msg_id)
        max_internal_date = max(max_internal_date, internal_date)

    # sort oldest -> newest so processing order makes sense
    new_messages.sort(key=lambda m: m["internal_date"])

    state["last_internal_date"] = str(max_internal_date)
    state["seen_ids"] = list(seen_ids)

    return new_messages
