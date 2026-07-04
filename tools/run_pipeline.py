#!/usr/bin/env python3
"""
Speed-to-Lead pipeline orchestrator for [Company].
Runs all 7 steps in sequence and displays results.

Usage:
  python3 tools/run_pipeline.py             # Full run (requires Gmail OAuth)
  python3 tools/run_pipeline.py --dry-run   # Skip Gmail + Slack, use existing raw_signals.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

LINE = "━" * 49
QUEUE_PATH = "outputs/triage_queue.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def run_tool(script, label, step, total):
    """Run a tool script as a subprocess. Returns (success, summary_line)."""
    print(f"\n[{step}/{total}] {label}")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )
    summary = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if result.returncode != 0:
        err = result.stderr.strip()
        print(f"      ✗ FAILED: {err or 'non-zero exit'}")
        return False, summary
    print(f"      ✓ {summary}" if summary else "      ✓ Done")
    return True, summary


def fmt_compliance(compliance):
    if isinstance(compliance, list):
        return ", ".join(compliance)
    return str(compliance)


def fmt_sla(signal):
    if signal.get("is_crack"):
        h = signal.get("overdue_minutes", 0) / 60
        return f"[{signal.get('crack_severity', '?')} — {h:.1f}h overdue]"
    m = signal.get("minutes_remaining", 0)
    if m < 60:
        return f"SLA: {int(m)} min remaining"
    return f"SLA: {m / 60:.1f}h remaining"


SPECIALTY_LABELS = {
    "family_medicine_gp": "Family Medicine GP",
    "mental_health": "Mental Health",
    "medical_specialist": "Medical Specialist",
    "enterprise_health_system": "Enterprise / Health System",
    "practice_manager": "Practice Manager",
    "nurse_np": "Nurse / NP",
    "allied_health": "Allied Health",
    "dentist": "Dentist",
    "veterinarian": "Veterinarian",
    "unknown": "Unknown",
}


def fmt_specialty(profile):
    return SPECIALTY_LABELS.get(profile, profile.replace("_", " ").title())


def display_queue(queue):
    """Print the formatted triage queue."""
    hot = [s for s in queue if not s.get("is_crack")]
    cracks = [s for s in queue if s.get("is_crack")]

    counter = 1

    if hot:
        print(f"\n{LINE}")
        print(f"  HOT SIGNALS — ACT NOW")
        print(f"{LINE}\n")
        for signal in hot:
            draft_note = "Draft ready → .tmp/response_drafts.json" if signal.get("has_draft") else "No draft"
            specialty = fmt_specialty(signal.get("specialty_profile", "unknown"))
            print(f"  [{counter}]  {signal['signal_type']}")
            print(f"       {signal.get('sender_name', '?')} · {specialty} · {signal.get('geography', '?')}")
            snippet = signal.get("body_snippet", "")[:90]
            print(f"       \"{snippet}\"")
            print(f"       {fmt_sla(signal)}")
            print(f"       EHR: {signal.get('ehr_likely', 'Unknown')} · Compliance: {fmt_compliance(signal.get('compliance', []))}")
            print(f"       Top objection: {signal.get('top_objection', 'N/A')}")
            print(f"       {draft_note}")
            print()
            counter += 1
    else:
        print(f"\n{LINE}")
        print(f"  HOT SIGNALS")
        print(f"{LINE}\n")
        print(f"  No in-SLA signals at this time.\n")

    if cracks:
        print(f"{LINE}")
        print(f"  CRACKS — ALREADY OVERDUE")
        print(f"{LINE}\n")
        for signal in cracks:
            draft_note = "Draft generated → .tmp/response_drafts.json" if signal.get("has_draft") else "No draft"
            specialty = signal.get("specialty_profile", "unknown").replace("_", " ").title()
            crack_label = signal.get("crack_type", signal["signal_type"])
            print(f"  [{counter}]  {crack_label}  {fmt_sla(signal)}")
            print(f"       {signal.get('sender_name', '?')} · {specialty} · {signal.get('geography', '?')}")
            print(f"       ACTION: Review draft and send immediately")
            print(f"       {draft_note}")
            print()
            counter += 1


def main():
    parser = argparse.ArgumentParser(description="Speed-to-Lead pipeline for [Company]")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip Gmail + Slack API calls, use existing .tmp/raw_signals.json")
    args = parser.parse_args()

    start_time = time.time()

    # Header
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    print(f"\n{LINE}")
    print(f"  SPEED-TO-LEAD — [COMPANY]")
    print(f"  {now_str}")
    print(LINE)

    total_steps = 8

    # Step 1: Scan Gmail
    if args.dry_run:
        raw = load_json(".tmp/raw_signals.json", [])
        count = len(raw) if isinstance(raw, list) else 0
        print(f"\n[1/{total_steps}] Scanning Gmail inbox (last 48h)...")
        print(f"      ↷ Dry run — using .tmp/raw_signals.json ({count} signal{'s' if count != 1 else ''})")
    else:
        run_tool("tools/scan_inbox.py", "Scanning Gmail inbox (last 48h)...", 1, total_steps)

    # Step 2: Scan Instantly
    if args.dry_run:
        print(f"\n[2/{total_steps}] Scanning Instantly replies...")
        print(f"      ↷ Dry run — skipping Instantly scan")
    else:
        run_tool("tools/scan_instantly.py", "Scanning Instantly replies...", 2, total_steps)

    # Step 3: Enrich leads
    ok, _ = run_tool("tools/enrich_lead.py", "Enriching leads...", 3, total_steps)
    if not ok:
        print("\nPipeline aborted at step 3.", file=sys.stderr)
        sys.exit(1)

    # Step 4: Score urgency
    ok, _ = run_tool("tools/score_urgency.py", "Scoring urgency + detecting cracks...", 4, total_steps)
    if not ok:
        print("\nPipeline aborted at step 4.", file=sys.stderr)
        sys.exit(1)

    # Step 5: Draft responses
    ok, _ = run_tool("tools/draft_response.py", "Drafting responses...", 5, total_steps)
    if not ok:
        print("\nPipeline aborted at step 5.", file=sys.stderr)
        sys.exit(1)

    # Step 6: Build queue
    ok, _ = run_tool("tools/build_queue.py", "Building priority queue...", 6, total_steps)
    if not ok:
        print("\nPipeline aborted at step 6.", file=sys.stderr)
        sys.exit(1)

    # Step 7: Notify Slack (falls back to terminal if SLACK_BOT_TOKEN not set)
    run_tool("tools/notify_slack.py", "Notifying Slack...", 7, total_steps)

    # Step 8: Pre-call briefings (silently skips if no demos are imminent)
    run_tool("tools/briefing.py", "Checking pre-call briefings...", 8, total_steps)

    # Display queue
    queue = load_json(QUEUE_PATH, [])
    display_queue(queue)

    # Footer
    elapsed = time.time() - start_time
    print(f"{LINE}")
    print(f"  Run complete in {elapsed:.0f}s")
    if not args.dry_run:
        print(f"  Slack bot: python3 tools/slack_bot.py (run separately)")
    print(LINE)
    print()


if __name__ == "__main__":
    main()
