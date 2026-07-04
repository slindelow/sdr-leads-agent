# Speed-to-Lead — Quick Start

Every inbound lead gets context, a draft, and an SLA countdown before a human sees it. Setup takes under 20 minutes and requires no IT involvement.

---

## Prerequisites

- Python 3.9+ (`python3 --version`)
- A Gmail account that receives [Company] inbound leads
- An Anthropic API key → [console.anthropic.com](https://console.anthropic.com)
- A Slack workspace with a `#speed-to-lead` channel

---

## Step 1 — Install dependencies

```bash
cd "SDR leads agent"
pip install anthropic python-dotenv slack-bolt
```

---

## Step 2 — Configure credentials

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` in any text editor. Fill in the three required fields:

```
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   ← see note below
ANTHROPIC_API_KEY=sk-ant-...
```

**Getting your Gmail App Password** (2 minutes):
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in → Select app: "Mail" → Select device: "Other" → name it "[Company] SDR Agent"
3. Copy the 16-character password → paste into `.env`

> Note: This is not your Gmail login password. It's a separate app-specific credential.
> If you don't see App Passwords, you need to enable 2-Step Verification first.

---

## Step 3 — Run the demo (no live inbox needed)

Generate 5 realistic sample leads and run the full pipeline against them:

```bash
python3 tools/generate_sample_data.py
python3 tools/run_pipeline.py --dry-run
```

You should see the pipeline run all 7 steps and display a formatted queue like this:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOT SIGNALS — ACT NOW
━━━━━━━━━━━━━━━━━━━━━━━

  [1]  DEMO_REQUEST
       Dr. Rachel Kim · Family Medicine Gp · AU
       "I'm a GP in a 3-doctor practice in Brisbane and we're drowning in notes"
       SLA: 20 min remaining
       EHR: Best Practice or Medical Director · Compliance: Privacy Act 1988, ...
       Top objection: Does it work in a 10-min consult?
       Draft ready → .tmp/response_drafts.json
```

Email drafts are in `.tmp/response_drafts.json`. Each lead has a personalized draft.

---

## Step 4 — Connect to live Gmail

Once the dry run looks good, run live:

```bash
python3 tools/run_pipeline.py
```

The pipeline scans your Gmail inbox for the last 48 hours, finds any emails that mention [Company], classifies them, enriches with healthcare context, drafts responses, and outputs a prioritized queue.

> First run may show no signals if there are no qualifying emails in the last 48h. That's expected.
> To test, send yourself an email with subject "Demo request – [Company]" and body mentioning [Company].

---

## Step 5 — Connect Slack alerts (optional but recommended)

Slack alerts fire to `#speed-to-lead` after every pipeline run — formatted lead cards with SLA countdown, EHR, compliance, and a ready-to-send draft.

**2-minute setup:**
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
2. Incoming Webhooks → toggle On → Add New Webhook to Workspace → pick `#speed-to-lead`
3. Copy the webhook URL → paste into `.env` as `SLACK_WEBHOOK_URL`

Run the pipeline again — alerts will now post to Slack automatically.

---

## Slack Bot (optional — 1v1 queries)

The Slack bot lets your SDR DM questions in natural language:

> "Show me Rachel's draft"
> "Who's overdue right now?"
> "What do I need to know about the NHS Trust lead?"

**Setup:**
1. At [api.slack.com/apps](https://api.slack.com/apps), open your app → Socket Mode → Enable → generate App-Level Token (scope: `connections:write`) → add to `.env` as `SLACK_APP_TOKEN`
2. Bot Token Scopes: add `chat:write`, `im:write`, `im:history`
3. Event Subscriptions → subscribe to `message.im`
4. Install to workspace → copy Bot Token → add to `.env` as `SLACK_BOT_TOKEN`
5. In Slack: open the bot's App Home → Messages tab → enable "Allow users to send messages"

Run the bot (keep it running in a separate terminal):

```bash
python3 tools/slack_bot.py
```

Full setup walkthrough: [`workflows/slack_interface.md`](workflows/slack_interface.md)

---

## Automate (run every 15 minutes)

Add a cron entry so the pipeline runs automatically:

```bash
crontab -e
```

Add this line (update the path to match your install location):

```
*/15 * * * * cd /path/to/SDR-leads-agent && python3 tools/run_pipeline.py >> /tmp/sdr_pipeline.log 2>&1
```

---

## Level 2: Richer enrichment (optional)

The pipeline enriches leads from email signals alone — specialty, geography, EHR, compliance, and likely objections are all inferred from keywords. This works well for demo purposes and low-volume use.

For real company names, verified job titles, headcount, and LinkedIn data, you can optionally connect Apollo.io:

1. Sign up at [apollo.io](https://www.apollo.io) → Settings → Integrations → API → Create Key
2. Add `APOLLO_API_KEY=your_key` to `.env`
3. Done — enrichment improves automatically on the next run

> Apollo free tier: 50 enrichments/month. Upgrade if volume exceeds that.
> The pipeline runs identically without an Apollo key.

---

## File structure

```
tools/          Python scripts (one job each)
workflows/      Markdown SOPs — read these to understand each pipeline step
config/         [company].json — SLA rules, compliance map, EHR map (swap to redeploy)
references/     [company]-brand.md + [company]-voice.md — loaded into every draft
outputs/        triage_queue.json — the prioritized queue your SDR acts on
.tmp/           Intermediate files (regenerated each run, gitignored)
.env            API keys — never commit this file
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Gmail login failed | Check GMAIL_APP_PASSWORD in .env — must be an App Password, not your login password |
| No signals found | The inbox scan looks for emails mentioning "[company]" in the last 48h. Send a test email. |
| Slack alerts not posting | Check SLACK_WEBHOOK_URL in .env — should start with `https://hooks.slack.com/services/` |
| Draft uses template instead of Claude | Check ANTHROPIC_API_KEY is set in .env |
| Slack bot not responding | Make sure Messages Tab is enabled in your Slack App settings |
