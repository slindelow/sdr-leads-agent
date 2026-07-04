#!/usr/bin/env python3
"""
Fires pre-call briefings to Slack 15–30 minutes before a scheduled demo.

Reads .tmp/lead_context.json — a dict keyed by signal_id.
Each lead record may have:
  demo_scheduled_at: ISO timestamp (UTC) — set when demo is booked
  briefing_sent: false — set to true after briefing posts

Usage:
  python3 tools/briefing.py           # checks for upcoming demos and fires
  python3 tools/briefing.py --list    # show all leads with scheduled demos

Setting a demo time (manually until calendar integration):
  Edit .tmp/lead_context.json and set demo_scheduled_at to an ISO timestamp.
  Example: "demo_scheduled_at": "2026-04-08T14:30:00Z"
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()

CONTEXT_PATH = ".tmp/lead_context.json"
DRAFTS_PATH = ".tmp/response_drafts.json"

BRIEFING_WINDOW_MIN = 15    # fire briefing at most N minutes before the call
BRIEFING_WINDOW_MAX = 30    # don't fire if call is more than N minutes away

SPECIALTY_CONTEXT_LINES = {
    "family_medicine_gp": "notes generated before the patient leaves the room, referral letters drafted in seconds.",
    "mental_health": "session documentation without breaking clinical presence or eye contact.",
    "medical_specialist": "custom templates — structured the way you already write notes.",
    "enterprise_health_system": "HIPAA-compliant with BAA available, integrates with Epic and Athenahealth.",
    "practice_manager": "scales across a practice team — shared templates, EHR integration.",
    "nurse_np": "mobile app for nursing workflows — handover notes, care plans, community settings.",
    "allied_health": "reduces documentation time across disciplines.",
    "dentist": "reduces chair-side documentation — clinical notes, referral letters, treatment plans.",
    "veterinarian": "reduces consultation documentation time — clinical notes drafted automatically.",
    "unknown": "reduces documentation time — most clinicians see results in the first consult.",
}


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def fmt_compliance(compliance):
    if isinstance(compliance, list):
        return ", ".join(compliance)
    return str(compliance)


def minutes_until(ts_str: str) -> float:
    """Return minutes until the given ISO timestamp. Negative = already past."""
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    delta = dt - datetime.now(timezone.utc)
    return delta.total_seconds() / 60


def format_briefing(lead: dict, drafts: dict, minutes_away: float) -> str:
    name = lead.get("sender_name", "Unknown")
    specialty = lead.get("specialty_profile", "unknown").replace("_", " ").title()
    geography = lead.get("geography", "?")
    company = lead.get("apollo_company") or lead.get("sender_email", "").split("@")[-1]
    ehr = lead.get("ehr_likely", "Unknown")
    compliance = fmt_compliance(lead.get("compliance", []))
    objection = lead.get("top_objection", "What happens to patient data?")
    signal_type = lead.get("signal_type", "?")
    subject = lead.get("subject", "?")
    elapsed_h = lead.get("elapsed_minutes", 0) / 60

    context_line = SPECIALTY_CONTEXT_LINES.get(
        lead.get("specialty_profile", "unknown"),
        SPECIALTY_CONTEXT_LINES["unknown"]
    )

    has_draft = lead.get("signal_id") in drafts
    draft_line = "DRAFT EMAIL SENT: ✓" if has_draft else "DRAFT EMAIL SENT: ✗ — generate one now"

    mins_str = f"{int(minutes_away)} minutes"

    return (
        f"📋 PRE-CALL BRIEFING — in {mins_str}\n"
        f"{'━' * 35}\n"
        f"{name} · {specialty}\n"
        f"{company} · {geography}\n\n"
        f"SIGNAL THAT STARTED THIS:\n"
        f"{signal_type} — \"{subject}\"\n"
        f"Received: {elapsed_h:.1f}h ago\n\n"
        f"WHAT TO KNOW:\n"
        f"• Specialty: {specialty}\n"
        f"• EHR: {ehr}\n"
        f"• Compliance: {compliance}\n\n"
        f"TOP OBJECTION TO EXPECT:\n"
        f"\"{objection}\"\n"
        f"→ Lead with: {context_line}\n\n"
        f"{draft_line}\n"
        f"{'━' * 35}"
    )


def post_to_slack(text: str, webhook_url: str) -> bool:
    import urllib.request
    try:
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
    parser.add_argument("--list", action="store_true", help="List all leads with scheduled demos")
    args = parser.parse_args()

    context = load_json(CONTEXT_PATH, {})
    drafts = load_json(DRAFTS_PATH, {})

    if not context:
        print("No lead context found. Run the pipeline first.")
        return

    scheduled = {
        sid: lead for sid, lead in context.items()
        if lead.get("demo_scheduled_at")
    }

    if args.list:
        if not scheduled:
            print("No demos scheduled. Set demo_scheduled_at in .tmp/lead_context.json.")
            return
        print(f"{'Signal ID':<20} {'Name':<25} {'Scheduled At':<25} {'Briefing Sent'}")
        print("-" * 90)
        for sid, lead in scheduled.items():
            mins = minutes_until(lead["demo_scheduled_at"])
            direction = f"in {int(mins)}m" if mins > 0 else f"{int(-mins)}m ago"
            print(f"{sid:<20} {lead.get('sender_name', '?'):<25} {lead['demo_scheduled_at']:<25} "
                  f"{'✓' if lead.get('briefing_sent') else direction}")
        return

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    use_slack = bool(webhook_url and not webhook_url.startswith("https://hooks.slack.com/services/T00"))

    fired = 0
    for sid, lead in scheduled.items():
        if lead.get("briefing_sent"):
            continue

        mins = minutes_until(lead["demo_scheduled_at"])

        if BRIEFING_WINDOW_MIN <= mins <= BRIEFING_WINDOW_MAX:
            briefing = format_briefing(lead, drafts, mins)

            if use_slack:
                ok = post_to_slack(briefing, webhook_url)
                if ok:
                    print(f"  Briefing sent for {lead.get('sender_name', sid)} ({int(mins)}m away)")
                    context[sid]["briefing_sent"] = True
                    fired += 1
                else:
                    print(briefing)
            else:
                print(briefing)
                context[sid]["briefing_sent"] = True
                fired += 1

    if fired:
        save_json(CONTEXT_PATH, context)
        print(f"{fired} pre-call briefing{'s' if fired != 1 else ''} sent")
    else:
        print("No demos in the next 15–30 minutes. Nothing to brief.")


if __name__ == "__main__":
    main()
