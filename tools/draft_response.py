#!/usr/bin/env python3
"""
Generates email drafts for inbound signals.
Uses Claude Haiku if ANTHROPIC_API_KEY is set; falls back to templates if not.
Checks existing drafts first — never regenerates a draft that already exists.
Input:  .tmp/scored_signals.json
Output: .tmp/response_drafts.json  (dict keyed by signal_id)
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

CONFIG_PATH = "config/config.json"
INPUT_PATH = ".tmp/scored_signals.json"
OUTPUT_PATH = ".tmp/response_drafts.json"
BRAND_PATH = "references/brand-context.md"
VOICE_PATH = "references/voice-guide.md"

SPECIALTY_CONTEXT_LINES = {
    "family_medicine_gp": (
        "notes generated before the patient leaves the room, "
        "referral letters drafted in seconds, billing codes from one consult."
    ),
    "mental_health": (
        "therapy session documentation without breaking clinical presence or eye contact."
    ),
    "medical_specialist": (
        "custom templates for {specialty} documentation — structured the way you already write notes."
    ),
    "enterprise_health_system": (
        "HIPAA-compliant with BAA available, integrates with Epic and Athenahealth. "
        "Happy to include IT and compliance teams."
    ),
    "practice_manager": (
        "scales across a practice team — shared templates, EHR integration, documentation standards."
    ),
    "nurse_np": (
        "mobile app for nursing workflows — handover notes, care plans, community settings."
    ),
    "allied_health": (
        "reduces documentation time across disciplines — structured notes in the format you already use."
    ),
    "dentist": (
        "reduces chair-side documentation — clinical notes, referral letters, treatment plans."
    ),
    "veterinarian": (
        "reduces consultation documentation time — clinical notes and referral letters drafted automatically."
    ),
    "unknown": (
        "reduces documentation time — most clinicians see results in the first consult."
    ),
}


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def read_file(path):
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None


def get_specialty_label(specialty):
    return specialty.replace("_", " ").replace("family medicine gp", "family medicine").title()


def generate_template_draft(signal, config):
    """Build a template-based draft without any API call."""
    first_name = signal.get("first_name", "there")
    specialty = signal.get("specialty_profile", "unknown")
    signal_type = signal.get("signal_type", "")
    subject = signal.get("subject", "")
    compliance = signal.get("compliance", [])
    calendar_link = os.getenv(
        "COMPANY_CALENDAR_LINK",
        config.get("calendar_link", "{{COMPANY_CALENDAR_LINK}}")
    )

    if signal_type == "ENTERPRISE_INBOUND":
        compliance_str = ", ".join(compliance) if isinstance(compliance, list) else str(compliance)
        body = (
            f"Hi {first_name},\n\n"
            f"Thanks for reaching out. Happy to walk through how [Company] works at the health system level.\n\n"
            f"We're compliant with {compliance_str} and can have our legal team turn around a BAA quickly.\n\n"
            f"Here's a link to book a time: {calendar_link}\n\n"
            f"The [Company] Team"
        )
    else:
        context_line = SPECIALTY_CONTEXT_LINES.get(specialty, SPECIALTY_CONTEXT_LINES["unknown"])
        if "{specialty}" in context_line:
            context_line = context_line.replace("{specialty}", get_specialty_label(specialty))
        body = (
            f"Hi {first_name},\n\n"
            f"{context_line}\n\n"
            f"Here's a link to book a time: {calendar_link}\n\n"
            f"15 minutes is enough to see the full workflow.\n\n"
            f"The [Company] Team"
        )

    return {
        "signal_id": signal["signal_id"],
        "to": signal.get("sender_email", ""),
        "subject": f"Re: {subject}",
        "body": body,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "template",
    }


def generate_claude_draft(signal, config, brand_text, voice_text):
    """Generate a draft using Claude Haiku. Falls back to template on error."""
    try:
        import anthropic

        first_name = signal.get("first_name", "there")
        specialty = signal.get("specialty_profile", "unknown")
        signal_type = signal.get("signal_type", "")
        body_snippet = signal.get("body_snippet", "")
        compliance = signal.get("compliance", [])
        ehr = signal.get("ehr_likely", "their EHR")
        calendar_link = os.getenv(
            "COMPANY_CALENDAR_LINK",
            config.get("calendar_link", "{{COMPANY_CALENDAR_LINK}}")
        )
        compliance_str = ", ".join(compliance) if isinstance(compliance, list) else str(compliance)

        system_prompt = f"""You are writing outbound SDR emails for [Company].

Brand identity and tone:
{brand_text}

Voice, DOs/DON'Ts, and exact product terminology:
{voice_text}

Hard rules:
- No emoji, no urgency language, no superlatives
- Sign-off: "The [Company] Team" exactly
- Max 5 sentences in body
- Lead with clinical outcome, not product feature
- Greeting: "Hi {{firstName}}," — never "Dear Dr."
- Keep it calm and clinical
"""

        user_prompt = f"""Write a first-touch reply to this inbound signal.

Signal type: {signal_type}
Sender: {first_name}
Specialty: {specialty}
Body snippet: "{body_snippet}"
EHR: {ehr}
Compliance: {compliance_str}
Calendar link: {calendar_link}

Return ONLY the email body (no subject line, no metadata). Start with "Hi {first_name},"
"""

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        body = message.content[0].text.strip()

        return {
            "signal_id": signal["signal_id"],
            "to": signal.get("sender_email", ""),
            "subject": f"Re: {signal.get('subject', '')}",
            "body": body,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "claude-haiku",
        }

    except Exception as e:
        print(f"  Claude API error for {signal.get('signal_id')}: {e} — falling back to template",
              file=sys.stderr)
        return generate_template_draft(signal, config)


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found — run score_urgency.py first", file=sys.stderr)
        sys.exit(1)

    config = load_json(CONFIG_PATH)
    signals = load_json(INPUT_PATH)

    existing_drafts = load_json(OUTPUT_PATH)
    if not isinstance(existing_drafts, dict):
        existing_drafts = {}
    drafts = dict(existing_drafts)

    use_claude = bool(os.getenv("ANTHROPIC_API_KEY"))
    brand_text = read_file(BRAND_PATH) if use_claude else None
    voice_text = read_file(VOICE_PATH) if use_claude else None
    method = "claude-haiku" if use_claude else "template"

    new_count = 0
    for signal in signals:
        sid = signal["signal_id"]
        if sid in drafts:
            continue  # already exists, skip

        if use_claude and brand_text and voice_text:
            draft = generate_claude_draft(signal, config, brand_text, voice_text)
        else:
            draft = generate_template_draft(signal, config)

        drafts[sid] = draft
        new_count += 1

    save_json(OUTPUT_PATH, drafts)
    print(f"{new_count} drafts generated via {method} ({len(drafts)} total)")


if __name__ == "__main__":
    main()
