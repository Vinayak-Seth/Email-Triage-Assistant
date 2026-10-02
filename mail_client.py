"""Read-only Gmail access over IMAP using an app password.

Nothing is sent, deleted, moved, or marked as read (mailbox opened read-only, BODY.PEEK).
"""
import email
import imaplib
import os
import re
from email.header import decode_header, make_header
from email.message import Message
from html import unescape

HOST = "imap.gmail.com"
MAX_BODY_CHARS = 2000  # keeps prompts small and cheap


def credentials() -> tuple[str, str]:
    """Credentials come from .env / environment only, never from Streamlit Cloud secrets."""
    return os.getenv("GMAIL_ADDRESS", "").strip(), os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value or ""))).strip()


def _body(msg: Message) -> str:
    """Prefer text/plain; fall back to crudely stripped HTML."""
    html_text = ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/plain":
            return text
        html_text = html_text or text
    html_text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html_text)
    return unescape(re.sub(r"<[^>]+>", " ", html_text))


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()[:MAX_BODY_CHARS]


def fetch_recent(limit: int = 10, unread_only: bool = False) -> list[dict]:
    """Newest-first list of {'from', 'subject', 'body'} from the Gmail inbox."""
    address, password = credentials()
    with imaplib.IMAP4_SSL(HOST) as imap:
        imap.login(address, password)
        imap.select("INBOX", readonly=True)
        _, data = imap.search(None, "UNSEEN" if unread_only else "ALL")
        ids = data[0].split()[-limit:][::-1]
        emails = []
        for msg_id in ids:
            _, parts = imap.fetch(msg_id, "(BODY.PEEK[])")
            msg = email.message_from_bytes(parts[0][1])
            emails.append({
                "from": _decode(msg.get("From")),
                "subject": _decode(msg.get("Subject")) or "(no subject)",
                "body": _clean(_body(msg)),
            })
    return emails
