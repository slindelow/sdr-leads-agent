#!/usr/bin/env python3
"""
1v1 Slack Bot for SDR lead queries.
Uses Socket Mode — requires SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env.

Setup (see workflows/slack_interface.md for full instructions):
  1. api.slack.com/apps → Create New App → Socket Mode
  2. Socket Mode → App-Level Token (scope: connections:write) → SLACK_APP_TOKEN
  3. Bot Token Scopes: chat:write, im:write, im:history
  4. Event Subscriptions → message.im
  5. Install to workspace → SLACK_BOT_TOKEN

Run: python3 tools/slack_bot.py

Example queries:
  "show draft for Rachel"
  "any hot leads right now?"
  "what's our SLA status?"
  "what do I need to know about Dr. Patel?"
  "who replied interested today?"
"""

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

QUEUE_PATH = "outputs/triage_queue.json"
DRAFTS_PATH = ".tmp/response_drafts.json"
SCORED_PATH = ".tmp/scored_signals.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def build_context():
    """Load current pipeline data from disk on every query (always fresh)."""
    queue = load_json(QUEUE_PATH, [])
    drafts = load_json(DRAFTS_PATH, {})
    scored = load_json(SCORED_PATH, [])
    return queue, drafts, scored


def build_system_prompt(queue, drafts, scored):
    queue_json = json.dumps(queue, indent=2)
    drafts_json = json.dumps(drafts, indent=2)
    scored_json = json.dumps(scored, indent=2)

    return f"""You are an AI assistant for an SDR (Sales Development Representative) at [Company] — an AI clinical documentation platform.

Your job is to answer the SDR's natural language questions about their leads, email drafts, and pipeline status using the context data below.

## Response Format
1. Direct answer — 1–3 lines
2. Context card if relevant (specialty, EHR, compliance, top objection)
3. Suggested action

Keep responses concise and actionable. No preamble.

## Rules
- "show draft for X": match sender by first name (case insensitive). Return the full draft verbatim — To, Subject, then the full Body. If no draft exists, say so.
- "SLA status" / "who's overdue": list all signals, show minutes_remaining (negative = overdue). Sort worst first.
- "hot leads": signals where is_crack is false and minutes_remaining > 0, ranked by priority_rank.
- "who replied interested" / "interested today": signals where signal_type contains INTERESTED or body_snippet suggests interest.
- Lead context card format: Name · Specialty · Geography | EHR: X | Compliance: Y | Top objection: Z
- If the SDR asks something you can't answer from the data, say so in one line.
- Do not make up information not present in the context.

## Current Pipeline Data

### Triage Queue
{queue_json}

### Email Drafts
{drafts_json}

### Scored Signals (full enrichment)
{scored_json}
"""


def answer_query(user_message: str) -> str:
    """Send query to Claude Haiku with current pipeline context, return response text."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "ANTHROPIC_API_KEY not set in .env — cannot query Claude."

    try:
        import anthropic
    except ImportError:
        return "anthropic package not installed. Run: pip install anthropic"

    queue, drafts, scored = build_context()
    system_prompt = build_system_prompt(queue, drafts, scored)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def main():
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")

    if not bot_token or not app_token:
        print("SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set — Slack bot unavailable.")
        print("See workflows/slack_interface.md for setup instructions.")
        sys.exit(1)

    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        print("slack-bolt not installed. Run: pip install slack-bolt")
        sys.exit(1)

    app = App(token=bot_token)

    @app.event("message")
    def handle_message(body, say):
        event = body.get("event", {})
        # Ignore message subtypes (bot_message, channel_join, message_changed, etc.)
        if event.get("subtype"):
            return
        # Ignore bot messages
        if event.get("bot_id"):
            return
        user_text = event.get("text", "").strip()
        if not user_text:
            return
        print(f"[query] {user_text}")
        response = answer_query(user_text)
        print(f"[response] {response[:120]}...")
        say(response)

    print("Slack bot started — DM the bot to query leads and drafts.")
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
