#!/usr/bin/env python3
"""
Calculates SLA status, detects cracks, and assigns priority ranks to enriched signals.
Input:  .tmp/enriched_signals.json
Output: .tmp/scored_signals.json
API:    None
"""

import json
import os
import sys
from datetime import datetime, timezone

CONFIG_PATH = "config/config.json"
INPUT_PATH = ".tmp/enriched_signals.json"
OUTPUT_PATH = ".tmp/scored_signals.json"

CRACK_TYPES = {
    "DEMO_REQUEST": "DEMO_REQUEST_COLD",
    "INBOUND_TRIAL_SIGNUP": "DEMO_REQUEST_COLD",
    "ENTERPRISE_INBOUND": "ENTERPRISE_DROPPED",
    "REFERRAL_INBOUND": "REFERRAL_DROPPED",
    "INTERESTED_REPLY_UNACTIONED": "INTERESTED_NO_DRAFT",
}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def crack_severity(overdue_minutes):
    if overdue_minutes < 30:
        return "LOW"
    elif overdue_minutes < 120:
        return "MEDIUM"
    else:
        return "HIGH"


def get_priority_rank(signal_type, is_crack, severity):
    if not is_crack:
        if signal_type in ("DEMO_REQUEST", "ENTERPRISE_INBOUND", "INBOUND_TRIAL_SIGNUP"):
            return 1
        else:
            return 2
    return {"LOW": 3, "MEDIUM": 4, "HIGH": 5}.get(severity, 5)


def score_signal(signal, sla_map):
    received_str = signal["received_at"]
    received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    elapsed_minutes = (now - received_at).total_seconds() / 60
    sla_minutes = sla_map.get(signal["signal_type"], 60)
    minutes_remaining = sla_minutes - elapsed_minutes
    is_crack = elapsed_minutes > sla_minutes
    overdue_minutes = max(0.0, elapsed_minutes - sla_minutes)

    severity = crack_severity(overdue_minutes) if is_crack else None
    crack_type = CRACK_TYPES.get(signal["signal_type"]) if is_crack else None
    rank = get_priority_rank(signal["signal_type"], is_crack, severity)

    scored = signal.copy()
    scored.update({
        "elapsed_minutes": round(elapsed_minutes, 1),
        "sla_minutes": sla_minutes,
        "minutes_remaining": round(minutes_remaining, 1),
        "overdue_minutes": round(overdue_minutes, 1),
        "is_crack": is_crack,
        "crack_type": crack_type,
        "crack_severity": severity,
        "priority_rank": rank,
    })
    return scored


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found — run enrich_lead.py first", file=sys.stderr)
        sys.exit(1)

    config = load_json(CONFIG_PATH)
    signals = load_json(INPUT_PATH)
    sla_map = config["sla_minutes"]

    scored = [score_signal(s, sla_map) for s in signals]
    save_json(OUTPUT_PATH, scored)

    hot = sum(1 for s in scored if not s["is_crack"])
    cracks = sum(1 for s in scored if s["is_crack"])
    crack_word = "crack" if cracks == 1 else "cracks"
    print(f"{hot} hot signal{'s' if hot != 1 else ''} | {cracks} {crack_word} found")


if __name__ == "__main__":
    main()
