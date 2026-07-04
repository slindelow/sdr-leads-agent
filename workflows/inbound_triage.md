# Workflow: Inbound Triage Pipeline

## Objective
Scan all inbound lead signals (Gmail + Instantly), enrich with healthcare context, score urgency, generate draft responses, and output a prioritized action queue. Complete this within 5 minutes of the trigger.

## When to Run
- On demand: `python3 tools/run_pipeline.py`
- Dry run (no API calls): `python3 tools/run_pipeline.py --dry-run`
- Scheduled: every 15 minutes via cron (Phase 5)

## Required Inputs
- Gmail OAuth token at `.credentials/gmail_token.json` (skip in dry-run)
- `config/config.json` — SLA rules, compliance map, EHR map
- `references/brand-context.md` and `references/voice-guide.md` — required for draft generation

## Step-by-Step

### Step 1 — Scan Gmail inbox
**Tool:** `tools/scan_inbox.py`
**Output:** `.tmp/raw_signals.json`

Fetches emails received in the last 48 hours where [Company] is the _recipient_ (not sender). Classifies each email into a signal type based on keywords (see Section 5 of PLANNING.md). Skips any signal_id already in `.tmp/processed_signal_ids.json`.

Signal types: `DEMO_REQUEST`, `INBOUND_TRIAL_SIGNUP`, `ENTERPRISE_INBOUND`, `REFERRAL_INBOUND`, `INTERESTED_REPLY_UNACTIONED`

Dry-run behavior: skip scan, use existing `.tmp/raw_signals.json`.

### Step 2 — Scan Instantly unibox
**Tool:** `tools/scan_instantly.py`
**Output:** `.tmp/raw_signals.json` (appended)

Fetches unread replies from Instantly unibox. Normalizes schema to match Gmail signal format. Appends to `.tmp/raw_signals.json`. Skips gracefully if `INSTANTLY_API_KEY` is not set.

Dry-run behavior: skip entirely.

### Step 3 — Enrich leads
**Tool:** `tools/enrich_lead.py`
**Input:** `.tmp/raw_signals.json`
**Output:** `.tmp/enriched_signals.json`

Keyword-based enrichment — no API calls. Infers:
- `specialty_profile`: from keywords in subject + body + sender name
- `geography`: from email domain + keywords (AU / UK / US)
- `compliance`: from `config/config.json` compliance_map
- `ehr_likely`: from `config/config.json` ehr_map (geo + specialty)
- `top_objection`: specialty-mapped objection
- `first_name`: extracted from sender_name

Match order for specialty: enterprise_health_system > practice_manager > family_medicine_gp > mental_health > medical_specialist > nurse_np > allied_health > dentist > veterinarian > unknown

### Step 4 — Score urgency
**Tool:** `tools/score_urgency.py`
**Input:** `.tmp/enriched_signals.json`
**Output:** `.tmp/scored_signals.json`

Calculates:
- `elapsed_minutes`: time since `received_at` to now UTC
- `sla_minutes`: from `config/config.json` based on signal_type
- `minutes_remaining`: sla_minutes - elapsed_minutes
- `is_crack`: elapsed_minutes > sla_minutes
- `crack_type`: DEMO_REQUEST_COLD / ENTERPRISE_DROPPED / REFERRAL_DROPPED / INTERESTED_NO_DRAFT
- `crack_severity`: LOW (0–30min over) / MEDIUM (30–120min over) / HIGH (120min+)
- `priority_rank`: 1–5 (see priority table below)

Priority ranking:
| Rank | Condition |
|------|-----------|
| 1 | DEMO_REQUEST or ENTERPRISE_INBOUND, not crack |
| 2 | REFERRAL_INBOUND or INTERESTED_REPLY_UNACTIONED, not crack |
| 3 | Crack, LOW severity |
| 4 | Crack, MEDIUM severity |
| 5 | Crack, HIGH severity |

### Step 5 — Draft responses
**Tool:** `tools/draft_response.py`
**Input:** `.tmp/scored_signals.json`
**Output:** `.tmp/response_drafts.json`

Generates one draft per signal_id. Checks for existing draft first — never regenerates. Uses Claude Haiku if `ANTHROPIC_API_KEY` is set; falls back to template drafts if not. Loads `references/brand-context.md` and `references/voice-guide.md` in every Claude prompt.

Template structure (non-enterprise):
```
Hi {firstName},

{specialty_context_line}

Here's a link to book a time: {CALENDAR_LINK}

15 minutes is enough to see the full workflow.

The [Company] Team
```

Enterprise template uses compliance context line instead of specialty context line.

### Step 6 — Build queue
**Tool:** `tools/build_queue.py`
**Input:** `.tmp/scored_signals.json` + `.tmp/response_drafts.json`
**Output:** `outputs/triage_queue.json`

Sorts signals by priority_rank (1 = highest priority). Within hot signals (rank 1–2), sorts by minutes_remaining ascending (least time left = most urgent). Within cracks (rank 3–5), sorts by overdue_minutes descending (most overdue first).

Updates `.tmp/processed_signal_ids.json` with all processed signal IDs.

### Step 7 — Notify Slack
**Tool:** `tools/notify_slack.py`
**Input:** `outputs/triage_queue.json`

Posts one Slack message per hot signal or crack to `#speed-to-lead`. If `SLACK_BOT_TOKEN` is not set, prints the same content to terminal. The pipeline never fails because of missing Slack credentials.

Format for hot signals: signal type, sender name, body snippet, SLA countdown, EHR, compliance, objection, draft status.
Format for cracks: crack type, severity, sender, overdue time, action instruction.

## Edge Cases

**No new signals:** Print "All clear — no new signals in the last 48h." to Slack (or terminal). Still completes all 7 steps.

**Gmail auth expired:** Steps 1–2 fail. Pipeline continues from step 3 using existing `.tmp/raw_signals.json`. Log warning. Prompt user to re-run `python3 tools/setup_gmail.py`.

**Anthropic API unavailable:** Step 5 falls back to templates silently. Log which signals got template vs. AI drafts.

**Dedup:** `processed_signal_ids.json` prevents re-processing the same signal across pipeline runs. Updated at end of step 6 (not step 1) to ensure a signal is only marked processed after the full pipeline succeeds.

**Timezone note:** All `received_at` values are UTC. `score_urgency.py` uses `datetime.now(timezone.utc)` for elapsed time calculation. Do not mix tz-naive and tz-aware datetimes.
