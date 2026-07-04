#!/usr/bin/env python3
"""
Generates realistic sample lead signals for demo/dry-run purposes.
Timestamps are relative to now() so the demo always shows a good mix:
  - 2 hot signals (within SLA)
  - 1 signal about to breach SLA
  - 1 low crack (slightly overdue)
  - 1 high crack (way overdue)

Output: .tmp/raw_signals.json
Usage:  python3 tools/generate_sample_data.py
        python3 tools/run_pipeline.py --dry-run
"""

import json
import os
from datetime import datetime, timezone, timedelta

OUTPUT_PATH = ".tmp/raw_signals.json"


def make_ts(minutes_ago: int) -> str:
    """Return ISO timestamp for N minutes ago (UTC)."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


SAMPLE_SIGNALS = [
    {
        "signal_id": "sample_001",
        "source": "sample",
        "signal_type": "DEMO_REQUEST",
        "sender_name": "Dr. Rachel Kim",
        "sender_email": "rachel.kim@northshoregp.com.au",
        "subject": "Demo request – [Company] AI scribe",
        "body_snippet": (
            "Hi team, I came across [Company] and would love to see a demo. "
            "I'm a GP in a 3-doctor practice in Brisbane and we're drowning in notes — "
            "a 10-minute consult turns into 20 minutes of admin. "
            "Can we book a walkthrough this week? Happy to loop in our practice manager too."
        ),
        # Hot signal — 10 min ago, SLA is 30 min
        "received_at": None,
        "_minutes_ago": 10,
    },
    {
        "signal_id": "sample_002",
        "source": "sample",
        "signal_type": "ENTERPRISE_INBOUND",
        "sender_name": "James Park",
        "sender_email": "j.park@sydneyhealthgroup.com.au",
        "subject": "AI documentation evaluation – Sydney Health Group",
        "body_snippet": (
            "Hi, I'm the CMIO at Sydney Health Group — we have 120 clinicians across 4 sites. "
            "We're evaluating AI clinical documentation tools for our entire organisation and "
            "[Company] came up in our procurement review. I'd like to understand your enterprise pricing, "
            "compliance posture, and integration with our existing IT setup. "
            "Can we arrange a conversation with your enterprise team?"
        ),
        # Hot enterprise — 15 min ago, SLA is 30 min
        "received_at": None,
        "_minutes_ago": 15,
    },
    {
        "signal_id": "sample_003",
        "source": "sample",
        "signal_type": "INTERESTED_REPLY_UNACTIONED",
        "sender_name": "Dr. Sarah Mitchell",
        "sender_email": "s.mitchell@mindwellclinic.co.uk",
        "subject": "Re: [Company] — AI documentation for mental health",
        "body_snippet": (
            "Thanks for reaching out. I'm actually quite interested in this — "
            "patient consent for recording and data handling are my main concerns "
            "but I'd love to hear more about how [Company] handles that. "
            "Open to a conversation if you can tell me more about the UK GDPR compliance side."
        ),
        # About to breach — 55 min ago, SLA is 60 min
        "received_at": None,
        "_minutes_ago": 55,
    },
    {
        "signal_id": "sample_004",
        "source": "sample",
        "signal_type": "REFERRAL_INBOUND",
        "sender_name": "Mark Thompson",
        "sender_email": "m.thompson@sunrisefamilyclinic.com.au",
        "subject": "Referred by Dr. Chen – [Company] enquiry",
        "body_snippet": (
            "Hi, a colleague of mine — Dr. Chen from Bayside Medical — recommended [Company] to me. "
            "I manage a practice of 5 GPs in Melbourne and we're looking to reduce admin burden. "
            "She said the bulk billing workflow was particularly useful. Happy to connect."
        ),
        # Low crack — 50 min ago, SLA is 45 min (5 min overdue)
        "received_at": None,
        "_minutes_ago": 50,
    },
    {
        "signal_id": "sample_005",
        "source": "sample",
        "signal_type": "DEMO_REQUEST",
        "sender_name": "Dr. Aisha Patel",
        "sender_email": "apatel@heartcare-chicago.com",
        "subject": "Demo request – cardiology group",
        "body_snippet": (
            "Hi, I saw a colleague using [Company] during rounds yesterday and it looked incredibly useful. "
            "I'd like to request a demo for our cardiology group — 8 physicians. "
            "We currently use Epic and I'm curious how the integration works. "
            "Can we schedule something for next week?"
        ),
        # High crack — 3.5 hours ago, SLA is 30 min (way overdue)
        "received_at": None,
        "_minutes_ago": 210,
    },
]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    signals = []
    for s in SAMPLE_SIGNALS:
        signal = {k: v for k, v in s.items() if not k.startswith("_")}
        signal["received_at"] = make_ts(s["_minutes_ago"])
        signals.append(signal)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(signals, f, indent=2)

    print(f"{len(signals)} sample signals written to {OUTPUT_PATH}")
    print()
    print("  sample_001  Dr. Rachel Kim       DEMO_REQUEST          (hot — 10 min ago)")
    print("  sample_002  James Park           ENTERPRISE_INBOUND    (hot — 15 min ago)")
    print("  sample_003  Dr. Sarah Mitchell   INTERESTED_REPLY      (⚠ breaching — 55 min ago)")
    print("  sample_004  Mark Thompson        REFERRAL_INBOUND      (crack — 50 min ago)")
    print("  sample_005  Dr. Aisha Patel      DEMO_REQUEST          (HIGH crack — 3.5h ago)")
    print()
    print("Next: python3 tools/run_pipeline.py --dry-run")


if __name__ == "__main__":
    main()
