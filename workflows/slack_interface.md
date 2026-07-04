# Workflow: Slack Interface

## Objective
Surface hot signal alerts and crack warnings to the SDR in real time, and answer SDR questions about leads via 1v1 DM.

## Two Modes

### Mode 1 — Automated Alerts (notify_slack.py)
Triggered at the end of every pipeline run. Posts to `#speed-to-lead`.

### Mode 2 — 1v1 Chat (slack_bot.py)
Long-lived Socket Mode process. SDR DMs the bot. Responds using Claude Haiku + current context files.

---

## Setup (One-Time)

**Tool:** `tools/setup_slack.py`

1. Create a Slack App at api.slack.com/apps
2. Enable Socket Mode → generate App-Level Token (scope: `connections:write`)
3. Add Bot Token Scopes: `chat:write`, `channels:read`, `im:write`, `im:history`
4. Enable Event Subscriptions (Socket Mode): subscribe to `message.im`
5. Install to workspace → copy Bot User OAuth Token
6. Invite bot to `#speed-to-lead` and `#sdr-assistant`
7. Add tokens to `.env`:
   - `SLACK_BOT_TOKEN=xoxb-...`
   - `SLACK_APP_TOKEN=xapp-...`
   - `SLACK_ALERT_CHANNEL_ID=C...`
8. Run `python3 tools/setup_slack.py` to verify connection

---

## Automated Alert Format

**Hot signal:**
```
🔴 HOT SIGNAL — ACT NOW
━━━━━━━━━━━━━━━━━━━━━━
{SIGNAL_TYPE}
{Sender Name} · {Specialty} · {Geography}
"{body_snippet}"

⏱ {N} min before SLA breach
🏥 EHR: {ehr_likely}
⚖️ Compliance: {compliance}
💬 Top objection: {top_objection}

Draft ready — ask me: "show draft for {first_name}"
━━━━━━━━━━━━━━━━━━━━━━
```

**Crack alert:**
```
⚠️ CRACK DETECTED — OVERDUE
━━━━━━━━━━━━━━━━━━━━━━
{CRACK_TYPE} [{SEVERITY} — {N}h overdue]
{Sender Name} · {Specialty} · {Geography}
{original body snippet}

Draft generated. Review and send immediately.
Ask me: "show draft for {first_name}"
━━━━━━━━━━━━━━━━━━━━━━
```

**No signals:**
```
✓ Pipeline ran — no new signals in the last 48h. All clear.
```

---

## 1v1 Bot Queries

The SDR can DM the bot in natural language. Claude interprets intent and responds from current context files.

| SDR asks | Bot returns |
|----------|-------------|
| "who's calling at 2pm?" | Pre-call briefing for next scheduled demo |
| "what do I need to know about Dr. Patel?" | Full lead context card |
| "show draft for James Park" | Email draft from response_drafts.json |
| "any hot leads right now?" | Current queue from triage_queue.json |
| "what's the top objection for mental health leads?" | Objection + pre-empt from enrichment logic |
| "how should I open the call with an NHS trust?" | Suggested talking points + compliance framing |
| "who replied interested today?" | INTERESTED signals from last 24h |
| "what's our SLA status?" | Summary of all signals with time remaining |

**Response format (all bot responses):**
1. Direct answer — 1–3 lines
2. Context card if relevant (specialty, EHR, compliance, objection)
3. Suggested action

**Run the bot:** `python3 tools/slack_bot.py` (separate process, always-on)

---

## Pre-Call Briefings

When a lead's status is `demo_scheduled` and `demo_scheduled_at` is set in `.tmp/lead_context.json`, fire a briefing 15 minutes before.

**Trigger check:** Run at start of every pipeline run, or as a lightweight cron.
**Dedup:** Set `briefing_sent: true` on the lead record after posting.

**Briefing format:**
```
📋 PRE-CALL BRIEFING — in 15 minutes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{Name} · {Specialty}
{Company} · {Location}

SIGNAL THAT STARTED THIS:
{signal_type} — "{subject}"
Received: {elapsed} ago · Responded in: {response_time}

WHAT TO KNOW:
• Specialty: {specialty_profile}
• EHR: {ehr_likely}
• Compliance: {compliance}
• Practice context: {from body snippet}

TOP OBJECTION TO EXPECT:
"{top_objection}"
→ Lead with: {specialty context line}

DRAFT EMAIL SENT: ✓ / ✗
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Fallback Behavior

If `SLACK_BOT_TOKEN` is not set:
- `notify_slack.py` prints alerts to terminal in the same format
- Pipeline completes normally — no failure
- `slack_bot.py` exits with a clear message: "SLACK_BOT_TOKEN not set — Slack bot unavailable"
