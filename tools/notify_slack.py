#!/usr/bin/env python3
"""
Sends hot signal alerts and crack warnings to Slack #speed-to-lead.
Uses an Incoming Webhook URL (SLACK_WEBHOOK_URL in .env).
Falls back to terminal output if SLACK_WEBHOOK_URL is not set.

Usage: python3 tools/notify_slack.py --queue outputs/triage_queue.json
Input:  outputs/triage_queue.json + .tmp/response_drafts.json

Slack webhook setup (2 minutes):
  1. Go to api.slack.com/apps → Create New App → From scratch
  2. Incoming Webhooks → toggle On → Add New Webhook to Workspace
  3. Pick #speed-to-lead → Copy the webhook URL → paste into .env as SLACK_WEBHOOK_URL
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

QUEUE_PATH = "outputs/triage_queue.json"
DRAFTS_PATH = ".tmp/response_drafts.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def fmt_compliance(compliance):
    if isinstance(compliance, list):
        return ", ".join(compliance)
    return str(compliance)


def format_hot_signal(signal, has_draft):
    first_name = signal.get("first_name", signal.get("sender_name", "Unknown"))
    sla_min = round(signal.get("minutes_remaining", 0))
    draft_line = f'Draft ready — ask: "show draft for {first_name}"' if has_draft else "No draft yet"
    return (
        f"🔴 HOT SIGNAL — ACT NOW\n"
        f"{'━' * 22}\n"
        f"{signal['signal_type']}\n"
        f"{signal.get('sender_name', '?')} · "
        f"{signal.get('specialty_profile', '?').replace('_', ' ').title()} · "
        f"{signal.get('geography', '?')}\n"
        f"\"{signal.get('body_snippet', '')[:100]}\"\n\n"
        f"⏱ {sla_min} min before SLA breach\n"
        f"🏥 EHR: {signal.get('ehr_likely', 'Unknown')}\n"
        f"⚖️  Compliance: {fmt_compliance(signal.get('compliance', []))}\n"
        f"💬 Top objection: {signal.get('top_objection', 'N/A')}\n\n"
        f"{draft_line}\n"
        f"{'━' * 22}"
    )


def format_crack(signal, has_draft):
    overdue_h = signal.get("overdue_minutes", 0) / 60
    draft_line = "Draft generated — review and send immediately." if has_draft else "No draft yet."
    first_name = signal.get("first_name", signal.get("sender_name", "Unknown"))
    return (
        f"⚠️  CRACK DETECTED — OVERDUE\n"
        f"{'━' * 22}\n"
        f"{signal.get('crack_type', signal['signal_type'])} "
        f"[{signal.get('crack_severity', '?')} — {overdue_h:.1f}h overdue]\n"
        f"{signal.get('sender_name', '?')} · "
        f"{signal.get('specialty_profile', '?').replace('_', ' ').title()} · "
        f"{signal.get('geography', '?')}\n"
        f"\"{signal.get('body_snippet', '')[:100]}\"\n\n"
        f"{draft_line}\n"
        f'Ask: "show draft for {first_name}"\n'
        f"{'━' * 22}"
    )


def post_to_slack(text, webhook_url):
    """Post a message to Slack via incoming webhook. Returns True on success."""
    try:
        import urllib.request

        payload = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  Slack post error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=QUEUE_PATH)
    args = parser.parse_args()

    queue = load_json(args.queue, [])
    drafts = load_json(DRAFTS_PATH, {})

    if not queue:
        msg = "✓ Pipeline ran — no new signals in the last 48h. All clear."
        print(msg)
        return

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    use_slack = bool(webhook_url and not webhook_url.startswith("https://hooks.slack.com/services/T00"))

    hot = [s for s in queue if not s.get("is_crack")]
    cracks = [s for s in queue if s.get("is_crack")]

    messages = []
    for signal in hot:
        messages.append(format_hot_signal(signal, signal.get("has_draft", False)))
    for signal in cracks:
        messages.append(format_crack(signal, signal.get("has_draft", False)))

    sent = 0
    for msg in messages:
        if use_slack:
            ok = post_to_slack(msg, webhook_url)
            if ok:
                sent += 1
            else:
                print(msg)
                print()
        else:
            print(msg)
            print()

    if use_slack:
        print(f"{sent} alert{'s' if sent != 1 else ''} sent to #speed-to-lead")
    else:
        print(f"{len(messages)} alert{'s' if len(messages) != 1 else ''} printed (set SLACK_WEBHOOK_URL to post to Slack)")


if __name__ == "__main__":
    main()
