#!/usr/bin/env python3
"""
Verifies all connections before the first pipeline run.
Run this once after filling in your .env file.

Usage: python3 tools/check_setup.py
"""

import imaplib
import json
import os
import sys
import urllib.request

from dotenv import load_dotenv
load_dotenv()

OK = "  ✓"
FAIL = "  ✗"
SKIP = "  –"


def check_gmail():
    email = os.getenv("GMAIL_EMAIL", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")

    if not email or not password:
        print(f"{FAIL} Gmail: GMAIL_EMAIL or GMAIL_APP_PASSWORD not set in .env")
        print("       → Get an app password: myaccount.google.com/apppasswords")
        return False

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email, password)
        mail.logout()
        print(f"{OK} Gmail: connected as {email}")
        return True
    except imaplib.IMAP4.error as e:
        print(f"{FAIL} Gmail: login failed — {e}")
        print("       → Check GMAIL_EMAIL and GMAIL_APP_PASSWORD in .env")
        print("       → Ensure IMAP is enabled: Gmail → Settings → See all settings → Forwarding and POP/IMAP")
        print("       → App passwords require 2-factor auth to be enabled on your Google account")
        return False
    except Exception as e:
        print(f"{FAIL} Gmail: connection error — {e}")
        return False


def check_slack():
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")

    if not webhook_url:
        print(f"{SKIP} Slack: SLACK_WEBHOOK_URL not set (alerts will print to terminal)")
        print("       → To enable Slack alerts: api.slack.com/apps → Create App → Incoming Webhooks → Add to Workspace")
        return True  # Not required

    try:
        payload = json.dumps({"text": "✓ Speed-to-Lead connection test — setup verified."}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"{OK} Slack: webhook connected (check #speed-to-lead for the test message)")
                return True
            else:
                print(f"{FAIL} Slack: webhook returned status {resp.status}")
                return False
    except Exception as e:
        print(f"{FAIL} Slack: webhook error — {e}")
        print("       → Check SLACK_WEBHOOK_URL in .env")
        return False


def check_anthropic():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        print(f"{SKIP} Anthropic: ANTHROPIC_API_KEY not set (drafts will use templates)")
        print("       → Get a key: console.anthropic.com")
        return True  # Not required

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        print(f"{OK} Anthropic: API key valid (claude-haiku-4-5-20251001)")
        return True
    except Exception as e:
        print(f"{FAIL} Anthropic: API error — {e}")
        print("       → Check ANTHROPIC_API_KEY in .env")
        return False


def check_config():
    config_path = "config/config.json"
    if os.path.exists(config_path):
        print(f"{OK} Config: config/config.json found")
        return True
    else:
        print(f"{FAIL} Config: config/config.json not found")
        print("       → Make sure you're running this from the project root directory")
        return False


def main():
    print("\nSpeed-to-Lead — Setup Check\n" + "─" * 35)

    results = [
        check_config(),
        check_gmail(),
        check_slack(),
        check_anthropic(),
    ]

    print("─" * 35)
    if all(results):
        print("  All checks passed. Ready to run the pipeline.\n")
        print("  Next step: python3 tools/run_pipeline.py --dry-run")
    else:
        failed = sum(1 for r in results if not r)
        print(f"  {failed} check(s) failed. Fix the issues above and re-run.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
