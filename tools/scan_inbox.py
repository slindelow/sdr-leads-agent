#!/usr/bin/env python3
"""
Scans Gmail inbox for inbound lead signals (last 48h) using IMAP.
No Google Cloud project required — uses an App Password from myaccount.google.com/apppasswords.

Input:  Gmail IMAP + .tmp/processed_signal_ids.json
Output: .tmp/raw_signals.json

Setup:
  1. Enable 2-factor auth on your Google account
  2. Go to myaccount.google.com/apppasswords
  3. Generate a password → add to .env as GMAIL_APP_PASSWORD
"""

import email as email_lib
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.header import decode_header

from dotenv import load_dotenv
load_dotenv()

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
OUTPUT_PATH = ".tmp/raw_signals.json"
DEDUP_PATH = ".tmp/processed_signal_ids.json"
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
LOOKBACK_HOURS = 48

# Keywords that classify signal types
SIGNAL_PATTERNS = {
    "DEMO_REQUEST": [
        "demo", "walkthrough", "walk-through", "schedule a call",
        "see it in action", "book a time", "show me how", "can we set up",
        "booking demo", "book demo", "request a demo", "schedule demo",
    ],
    "INBOUND_TRIAL_SIGNUP": [
        "welcome to [company]", "trial", "sign up confirmed", "account created",
        "get started with [company]",
    ],
    "ENTERPRISE_INBOUND": [
        "enterprise", "procurement", "health system", "nhs trust", "hospital",
        "cmo ", "cio ", "cmio", "it department", "our team of",
        "across our organisation", "across our organization",
    ],
    "REFERRAL_INBOUND": [
        "referred by", "colleague recommended", "a friend suggested",
        "heard about you from", "recommended [company]",
    ],
    "INTERESTED_REPLY_UNACTIONED": [
        "interested", "sounds good", "tell me more", "let's chat",
        "open to a conversation", "happy to connect", "worth a look",
        "would love to", "can you send", "curious about",
    ],
}

# Only fetch emails mentioning [Company]-related terms
# Requires "[company]" specifically to reduce false positives from newsletters
COMPANY_KEYWORDS = [
    "[company]", "[company]", "ai scribe", "clinical documentation",
    "demo request", "book a demo", "booking demo", "medical transcription",
    "demo", "walkthrough",
]

# Known newsletter/marketing sender domains — skip these entirely
NOISE_DOMAINS = {
    "substack.com", "beehiiv.com", "mailchimp.com", "convertkit.com",
    "hubspot.com", "marketo.com", "sendgrid.net", "klaviyo.com",
    "constantcontact.com", "campaignmonitor.com", "drip.com",
    "zeteo.com", "fitt.co", "medscape.com", "nejm.org",
    "bmj.com", "thelancet.com", "healthcareweekly.com",
    "healthcareitnews.com", "modernhealthcare.com",
}

# Sender name fragments that indicate newsletters or automated mail
NOISE_SENDER_PATTERNS = [
    "newsletter", "digest", "weekly", "daily", "update", "bulletin",
    "noreply", "no-reply", "donotreply", "notifications", "alerts",
    "mailer", "info@", "news@", "hello@", "team@",
]


def is_noise_sender(sender_email: str, sender_name: str) -> bool:
    """Return True if this sender looks like a newsletter or automated mail."""
    email_lower = sender_email.lower()
    name_lower = sender_name.lower()

    # Check domain against blocklist
    domain = email_lower.split("@")[-1] if "@" in email_lower else ""
    if domain in NOISE_DOMAINS:
        return True

    # Check for noise patterns in email address or sender name
    combined = email_lower + " " + name_lower
    if any(pattern in combined for pattern in NOISE_SENDER_PATTERNS):
        return True

    return False


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def decode_mime_header(value):
    """Decode encoded email headers (e.g. =?utf-8?b?...?=)."""
    parts = decode_header(value or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def extract_name(from_header):
    match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if match:
        return match.group(1).strip()
    email_match = re.search(r'[\w.+-]+@', from_header)
    if email_match:
        return email_match.group(0).rstrip("@").replace(".", " ").title()
    return from_header


def extract_email(from_header):
    match = re.search(r'<([\w.+-]+@[\w.-]+)>', from_header)
    if match:
        return match.group(1)
    match = re.search(r'[\w.+-]+@[\w.-]+', from_header)
    return match.group(0) if match else from_header


def get_body(msg):
    """Extract plain text body from an email.message.Message object."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
    else:
        if msg.get_content_type() == "text/plain":
            charset = msg.get_content_charset() or "utf-8"
            try:
                return msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                return ""
    return ""


def detect_signal_type(subject, body):
    combined = (subject + " " + body).lower()
    for signal_type, keywords in SIGNAL_PATTERNS.items():
        if any(kw in combined for kw in keywords):
            return signal_type
    return None


def mentions_company(subject, body):
    combined = (subject + " " + body).lower()
    # Must mention "[company]" or "[company]" directly — broad terms like "demo"
    # alone are not sufficient (catches too many newsletters and marketing emails)
    if "[company]" in combined or "[company]" in combined:
        return True
    # Allow specific compound terms that unambiguously refer to the product
    specific_terms = ["ai scribe", "clinical documentation", "demo request", "book a demo",
                      "booking demo", "medical transcription"]
    return any(kw in combined for kw in specific_terms)


def imap_date_str(dt):
    """Format a datetime as an IMAP SINCE date string (e.g. '07-Apr-2026')."""
    return dt.strftime("%d-%b-%Y")


def main():
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        print(
            "ERROR: GMAIL_EMAIL or GMAIL_APP_PASSWORD not set in .env.\n"
            "  → Go to myaccount.google.com/apppasswords to generate a password.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
    except imaplib.IMAP4.error as e:
        print(f"ERROR: Gmail login failed — {e}", file=sys.stderr)
        print(
            "  → Check GMAIL_EMAIL and GMAIL_APP_PASSWORD in .env\n"
            "  → Make sure IMAP is enabled: mail.google.com → Settings → See all → Forwarding and POP/IMAP",
            file=sys.stderr,
        )
        sys.exit(1)

    mail.select("INBOX")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    since_str = imap_date_str(cutoff)
    _, msg_ids = mail.search(None, f'(SINCE "{since_str}")')

    processed_ids = load_json(DEDUP_PATH, [])
    if not isinstance(processed_ids, list):
        processed_ids = []
    processed_set = set(processed_ids)

    all_ids = msg_ids[0].split() if msg_ids[0] else []
    new_signals = []

    for msg_id_bytes in all_ids:
        msg_id_str = msg_id_bytes.decode()
        signal_id = f"gmail_imap_{msg_id_str}"

        if signal_id in processed_set:
            continue

        _, msg_data = mail.fetch(msg_id_bytes, "(RFC822)")
        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)

        subject = decode_mime_header(msg.get("Subject", ""))
        from_header = decode_mime_header(msg.get("From", ""))
        date_header = msg.get("Date", "")

        sender_email = extract_email(from_header)

        # Skip our own outbound emails (not test signals sent to ourselves)
        # In production, self-sent emails are genuinely not inbound leads
        # Comment this out temporarily if testing by sending yourself emails
        # if GMAIL_EMAIL and sender_email.lower() == GMAIL_EMAIL.lower():
        #     continue

        body = get_body(msg)
        body_snippet = body[:300].strip()

        # Skip newsletters, marketing mail, and known noise senders
        if is_noise_sender(sender_email, extract_name(from_header)):
            continue

        if not mentions_company(subject, body_snippet):
            continue

        signal_type = detect_signal_type(subject, body_snippet)
        if not signal_type:
            continue

        # Parse received_at from Date header
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_header)
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
            received_at_str = received_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            received_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        new_signals.append({
            "signal_id": signal_id,
            "source": "gmail",
            "signal_type": signal_type,
            "sender_name": extract_name(from_header),
            "sender_email": sender_email,
            "subject": subject,
            "body_snippet": body_snippet,
            "received_at": received_at_str,
        })

    mail.logout()

    existing = load_json(OUTPUT_PATH, [])
    if not isinstance(existing, list):
        existing = []
    save_json(OUTPUT_PATH, existing + new_signals)

    print(f"{len(new_signals)} new signal{'s' if len(new_signals) != 1 else ''} detected")


if __name__ == "__main__":
    main()
