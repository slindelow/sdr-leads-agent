# Speed-to-Lead Agent — [Company]

A real-time SDR intelligence system for healthcare SaaS inbound leads. Scans Gmail and Instantly for hot signals, enriches with clinical specialty context, scores urgency against SLA targets, drafts specialty-aware responses, and surfaces everything to the SDR in Slack — within 5 minutes of the signal arriving.

---

## Why This Exists

Average B2B SaaS response time: 42–47 hours. Responding within 5 minutes vs. 30 minutes is a 21x improvement in qualification rate (MIT/InsideSales). Healthcare buyers are specialty-specific, EHR-locked, and compliance-conscious — generic outreach fails. This agent handles the preparation so the SDR can respond immediately with the right context.

---

## Architecture

Built on the WAT framework: **Workflows** define the SOPs, the **Agent** (Claude) orchestrates, **Tools** execute deterministically.

```
Step 1  scan_inbox.py            →  Gmail inbound signals (last 48h)
Step 2  scan_instantly.py        →  Instantly unibox replies (appended)
Step 3  enrich_lead.py           →  Specialty · geography · EHR · compliance · objection
Step 4  score_urgency.py         →  SLA countdown · crack detection · priority rank
Step 5  draft_response.py        →  Specialty-aware email drafts (Claude Haiku or template)
Step 6  build_queue.py           →  Prioritized queue → outputs/triage_queue.json
Step 7  notify_slack.py          →  Hot signal alerts to #speed-to-lead (terminal fallback)
Step 8  briefing.py              →  Pre-call briefing 15 min before scheduled demos
```

All intermediate data flows through `.tmp/*.json`. Every step is independently re-runnable.

---

## Setup

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the 4 core values (see steps 3–5 below). `ANTHROPIC_API_KEY` and `SLACK_WEBHOOK_URL` are optional — the pipeline runs without them and falls back to templates / terminal output.

### 3. Gmail — App Password (2 minutes)

No Google Cloud project required. Uses your regular Gmail/Google Workspace account.

1. Enable 2-factor auth on your Google account (if not already on)
2. Go to **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
3. Generate a password → name it "Speed-to-Lead"
4. Copy the 16-character password into `.env`:

```
GMAIL_EMAIL=you@yourcompany.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

> If you don't see the App Passwords page, your Google Workspace admin may need to enable it. IMAP must also be enabled in Gmail settings: Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP.

### 4. Slack — Incoming Webhook (3 minutes)

1. Go to **[api.slack.com/apps](https://api.slack.com/apps)** → Create New App → From scratch
2. Name it "Speed-to-Lead" → pick your workspace
3. In the left sidebar: **Incoming Webhooks** → toggle **On**
4. Click **Add New Webhook to Workspace** → pick `#speed-to-lead` → Allow
5. Copy the webhook URL into `.env`:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
```

### 5. Anthropic API key (1 minute)

Go to **[console.anthropic.com](https://console.anthropic.com)** → API Keys → Create Key → paste into `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 6. Verify setup

```bash
python3 tools/check_setup.py
```

Prints ✓ or ✗ for each connection with specific fix instructions if anything fails.

### 7. Run

```bash
# Generate sample leads and test the full pipeline (no credentials needed)
python3 tools/generate_sample_data.py
python3 tools/run_pipeline.py --dry-run

# Go live against your inbox
python3 tools/run_pipeline.py
```

### 8. Automate (optional)

To run every 15 minutes during business hours, add to your crontab (`crontab -e`):

```
*/15 9-18 * * 1-5 cd /path/to/speed-to-lead && python3 tools/run_pipeline.py >> logs/pipeline.log 2>&1
```

---

## Usage

### Run the pipeline

```bash
# Full run (requires Gmail OAuth + .env configured)
python3 tools/run_pipeline.py

# Dry run — skip Gmail + Slack, use existing .tmp/raw_signals.json
python3 tools/run_pipeline.py --dry-run
```

### Start the Slack bot (Phase 4)

```bash
# Run as a separate always-on process
python3 tools/slack_bot.py
```

The SDR can then DM the bot directly in Slack:
- `"what do I need to know about Dr. Patel?"`
- `"show draft for James Park"`
- `"any hot leads right now?"`
- `"what's our SLA status?"`

---

## Signal Types and SLA Targets

| Signal | Triggers | SLA |
|--------|----------|-----|
| `DEMO_REQUEST` | "demo", "walkthrough", "schedule", "see it in action" | 30 min |
| `INBOUND_TRIAL_SIGNUP` | "welcome to [company]", "trial", "sign up confirmed" | 30 min |
| `ENTERPRISE_INBOUND` | Hospital/NHS domain; "enterprise", "procurement", "CMO" | 30 min |
| `REFERRAL_INBOUND` | "referred by", "colleague recommended" | 45 min |
| `INTERESTED_REPLY_UNACTIONED` | Instantly unibox reply or Gmail reply to outbound thread | 60 min |

Signals past their SLA become **cracks** — ranked by severity (LOW / MEDIUM / HIGH) and surfaced with a pre-generated draft for immediate action.

---

## Enrichment

No third-party enrichment APIs. All context is inferred from signal keywords:

- **Specialty** — 9 profiles: GP, mental health, medical specialist, enterprise health system, practice manager, nurse/NP, allied health, dentist, vet
- **Geography** — AU / UK / US (from email domain + keywords)
- **EHR** — mapped from specialty + geography (e.g., AU GP → Best Practice or Medical Director)
- **Compliance** — AU: Privacy Act 1988 + My Health Record Act · UK: NHS IG Toolkit + UK GDPR · US: HIPAA + BAA required
- **Top objection** — one pre-mapped objection per specialty for pre-call prep

---

## Draft Generation

`draft_response.py` checks for `ANTHROPIC_API_KEY`:

- **With API key** — calls Claude Haiku (`claude-haiku-4-5-20251001`) with full brand + voice context loaded from `references/brand-context.md` and `references/voice-guide.md`
- **Without API key** — uses specialty-mapped templates (functional for Phase 1)

Drafts are saved to `.tmp/response_drafts.json` keyed by `signal_id`. Already-drafted signals are never regenerated.

---

## Slack Alerts

When `SLACK_BOT_TOKEN` is set, alerts post to `#speed-to-lead` automatically after each pipeline run. Without it, the same content prints to terminal — the pipeline never fails because of missing Slack credentials.

**Hot signal format:**
```
🔴 HOT SIGNAL — ACT NOW
━━━━━━━━━━━━━━━━━━━━━━
DEMO_REQUEST
Dr. Anika Patel · Medical Specialist · AU
"Could we schedule a walkthrough for our team of 6 cardiologists?"

⏱ 12 min before SLA breach
🏥 EHR: Genie Solutions
⚖️  Compliance: Privacy Act 1988, My Health Record Act
💬 Top objection: Does it match my specialty's note format?

Draft ready — ask: "show draft for Anika"
━━━━━━━━━━━━━━━━━━━━━━
```

---

## File Structure

```
speed-to-lead/
├── CLAUDE.md                    ← Agent instructions (WAT framework)
├── README.md                    ← This file
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   └── [company].json               ← SLA rules, compliance map, EHR map, ICP
│
├── references/
│   ├── [company]-brand.md           ← Brand identity (loaded at runtime)
│   └── [company]-voice.md           ← Voice, DOs/DON'Ts, product terminology
│
├── workflows/
│   ├── inbound_triage.md        ← Core pipeline SOP
│   └── slack_interface.md       ← Slack alerts + bot SOP
│
├── tools/
│   ├── setup_gmail.py           ← One-time Gmail OAuth setup
│   ├── setup_slack.py           ← One-time Slack verification
│   ├── scan_inbox.py            ← Gmail inbound signals
│   ├── scan_instantly.py        ← Instantly unibox replies
│   ├── enrich_lead.py           ← Keyword enrichment
│   ├── score_urgency.py         ← SLA + crack detection
│   ├── draft_response.py        ← Email draft generation
│   ├── build_queue.py           ← Priority queue assembly
│   ├── notify_slack.py          ← Slack alerts
│   ├── slack_bot.py             ← 1v1 Slack chat (Socket Mode)
│   ├── briefing.py              ← Pre-call briefings (15 min before demos)
│   ├── generate_sample_data.py  ← Realistic sample leads for demo/dry-run
│   └── run_pipeline.py          ← Pipeline orchestrator
│
├── .tmp/                        ← Intermediate JSON (gitignored, regenerated each run)
└── outputs/
    └── triage_queue.json        ← Final prioritized queue
```

**[Company]-specific files:** `config/config.json` and `references/[company]-*.md`. Swap those to deploy for a different health tech client.

---

## Pre-Call Briefings

When a demo is booked, set `demo_scheduled_at` on the lead in `.tmp/lead_context.json` (populated automatically after each pipeline run):

```json
{
  "sample_001": {
    "demo_scheduled_at": "2026-04-08T14:30:00Z",
    "briefing_sent": false,
    ...
  }
}
```

`briefing.py` fires automatically as step 8 of the pipeline. It posts a Slack briefing card 15–30 minutes before the call and marks `briefing_sent: true` to prevent duplicates.

```bash
python3 tools/briefing.py --list    # see all scheduled demos
python3 tools/briefing.py           # fire any briefings due now
```
