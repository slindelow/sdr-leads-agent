#!/usr/bin/env python3
"""
Assembles the prioritized triage queue, updates the dedup registry, and saves JSON.
Prints a one-line summary to stdout (captured by run_pipeline.py).
Input:  .tmp/scored_signals.json + .tmp/response_drafts.json
Output: outputs/triage_queue.json + .tmp/processed_signal_ids.json
"""

import json
import os
import sys

SCORED_PATH = ".tmp/scored_signals.json"
DRAFTS_PATH = ".tmp/response_drafts.json"
OUTPUT_PATH = "outputs/triage_queue.json"
DEDUP_PATH = ".tmp/processed_signal_ids.json"
CONTEXT_PATH = ".tmp/lead_context.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def sort_key(signal):
    """Sort by priority_rank, then by urgency within rank."""
    rank = signal.get("priority_rank", 99)
    if signal.get("is_crack"):
        # Most overdue first within cracks
        return (rank, -signal.get("overdue_minutes", 0))
    else:
        # Least time remaining first within hot signals
        return (rank, signal.get("minutes_remaining", 9999))


def main():
    if not os.path.exists(SCORED_PATH):
        print(f"ERROR: {SCORED_PATH} not found — run score_urgency.py first", file=sys.stderr)
        sys.exit(1)

    scored = load_json(SCORED_PATH, [])
    drafts = load_json(DRAFTS_PATH, {})

    queue = sorted(scored, key=sort_key)

    # Update dedup registry
    existing_ids = load_json(DEDUP_PATH, [])
    if not isinstance(existing_ids, list):
        existing_ids = []
    updated_ids = list(set(existing_ids + [s["signal_id"] for s in queue]))
    save_json(DEDUP_PATH, updated_ids)

    # Attach draft reference to each queue item
    for item in queue:
        sid = item["signal_id"]
        item["has_draft"] = sid in drafts

    save_json(OUTPUT_PATH, queue)

    # Update lead context — preserves existing demo_scheduled_at and briefing_sent
    existing_context = load_json(CONTEXT_PATH, {})
    if not isinstance(existing_context, dict):
        existing_context = {}
    for item in queue:
        sid = item["signal_id"]
        if sid not in existing_context:
            existing_context[sid] = {
                "demo_scheduled_at": None,
                "briefing_sent": False,
            }
        # Always refresh lead data, but never overwrite scheduling state
        existing_context[sid].update({k: v for k, v in item.items()
                                       if k not in ("demo_scheduled_at", "briefing_sent")})
    save_json(CONTEXT_PATH, existing_context)

    hot = sum(1 for s in queue if not s["is_crack"])
    cracks = sum(1 for s in queue if s["is_crack"])
    print(f"Saved to {OUTPUT_PATH} ({hot} hot, {cracks} crack{'s' if cracks != 1 else ''})")


if __name__ == "__main__":
    main()
