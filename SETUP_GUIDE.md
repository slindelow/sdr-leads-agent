# Speed-to-Lead — Setup Guide

**What this does:** Monitors your sales inbox, reads every inbound lead, figures out what kind of clinician they are, writes a personalised draft reply, and posts an alert in Slack — all within about 5 minutes of the email arriving.

**How long setup takes:** Around 25 minutes  
**What you need to be comfortable with:** Copying and pasting commands into Terminal  
**What you'll need accounts for:** Gmail, Slack, and Anthropic (Claude)

---

## Before you start

You need Python installed on your computer. To check, open Terminal and type:

```
python3 --version
```

If you see a version number like `Python 3.11.2`, you're good. If you get an error, download Python from [python.org/downloads](https://www.python.org/downloads) and install it using the default settings.

---

## Step 1 — Get the files onto your computer

Download the project from GitHub and move into the folder:

```
git clone https://github.com/slindelow/sdr-leads-agent
cd sdr-leads-agent
```

> **If you're not sure how to use Terminal on a Mac:** Press Cmd + Space, type "Terminal", and hit Enter. That opens it. Then paste the two lines above one at a time and hit Enter after each.

---

## Step 2 — Install the required packages

This installs everything the tool depends on. You only need to do this once.

```
pip3 install -r requirements.txt
```

You'll see a bunch of text scroll by. That's normal. It takes about 30 seconds.

---

## Step 3 — Create your credentials file

The tool needs a few passwords and API keys to connect to Gmail, Slack, and Claude. These all live in a single file called `.env`.

Create it by running:

```
cp .env.example .env
```

Then open `.env` in any text editor — TextEdit on Mac, Notepad on Windows. It looks like this:

```
GMAIL_EMAIL=
GMAIL_APP_PASSWORD=
SLACK_WEBHOOK_URL=
ANTHROPIC_API_KEY=
COMPANY_CALENDAR_LINK=https://calendly.com/[company]/demo
```

You'll fill in each of these in the steps below. Keep this file private — don't share it or send it to anyone.

---

## Step 4 — Connect Gmail (about 5 minutes)

The tool reads your inbox using something called an "App Password." This is a separate password that only works for this tool — it doesn't give access to anything else in your Google account.

**First, make sure 2-Step Verification is turned on:**
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Find "2-Step Verification" and turn it on if it isn't already

**Then generate an App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Under "Select app", pick **Mail**
3. Under "Select device", pick **Other** and type `Speed-to-Lead`
4. Click **Generate**
5. You'll see a 16-character password — copy it (it looks like `kdei thkr ckvw dttx`)

> If you don't see the App Passwords page, your Google Workspace admin may need to enable it. Let them know you need to create an App Password for a third-party email reader.

**Then enable IMAP so the tool can read emails:**
1. Open Gmail and click the gear icon in the top right → **See all settings**
2. Click the **Forwarding and POP/IMAP** tab
3. Under "IMAP access", select **Enable IMAP**
4. Click **Save Changes**

**Add both to your `.env` file:**
```
GMAIL_EMAIL=your-inbox@gmail.com
GMAIL_APP_PASSWORD=kdei thkr ckvw dttx
```

---

## Step 5 — Get an Anthropic API key (about 2 minutes)

This is what powers the personalised draft emails. Without it the tool still works, but it uses basic pre-written templates instead of AI-generated drafts tailored to each lead.

1. Go to [console.anthropic.com](https://console.anthropic.com) and create a free account
2. Click **API Keys** in the left sidebar
3. Click **Create Key**, give it any name, and copy it

Add it to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

> **Cost:** The tool uses Claude Haiku, the most affordable version. At typical sales volumes, this costs less than $1 per month.

---

## Step 6 — Set up Slack alerts (about 5 minutes)

This makes the tool post automatically to a Slack channel every time a new lead comes in. You'll see a formatted card with the lead's context, how much time is left before the SLA window closes, and a prompt to pull up their draft.

**Create a Slack app:**
1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name it `Speed-to-Lead`, select your Slack workspace, and click **Create App**

**Set up the channel connection:**
1. In the left sidebar, click **Incoming Webhooks**
2. Toggle it **On**
3. Click **Add New Webhook to Workspace**
4. Select the `#speed-to-lead` channel and click **Allow**
5. Copy the URL it gives you — it starts with `https://hooks.slack.com/services/...`

Add it to `.env`:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

**What a Slack alert looks like:**
```
🔴 HOT SIGNAL — ACT NOW
━━━━━━━━━━━━━━━━━━━━━━
DEMO_REQUEST
Dr. Rachel Kim · Family Medicine GP · AU
"I'm a GP in a 3-doctor practice and we're drowning in notes..."

⏱ 19 min before SLA breach
🏥 EHR: Best Practice or Medical Director
⚖️ Compliance: Privacy Act 1988, My Health Record Act
💬 Top objection: Does it work in a 10-min consult?

Draft ready — ask: "show draft for Rachel"
━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 7 — Set up the Slack bot for lead questions (about 10 minutes, optional)

This is separate from the alerts. It lets your SDR send a direct message to the bot and ask questions like:

> "Show me Rachel's draft"  
> "Who's overdue right now?"  
> "What should I know about the NHS Trust lead?"

**Back in your Slack app settings** ([api.slack.com/apps](https://api.slack.com/apps) → Speed-to-Lead):

**Turn on Socket Mode:**
1. Click **Socket Mode** in the left sidebar and toggle it **On**
2. Click **Generate Token**, name it anything, check the `connections:write` box, and click **Generate**
3. Copy the token — it starts with `xapp-`

Add to `.env`:
```
SLACK_APP_TOKEN=xapp-1-...
```

**Give the bot permission to send and read messages:**
1. Click **OAuth & Permissions** in the sidebar
2. Under "Bot Token Scopes", add these three: `chat:write`, `im:write`, `im:history`

**Subscribe to direct messages:**
1. Click **Event Subscriptions** in the sidebar → toggle **On**
2. Under "Subscribe to bot events", click **Add Bot User Event** and add `message.im`

**Install the app to your workspace:**
1. Click **OAuth & Permissions** → **Install to Workspace** → **Allow**
2. Copy the Bot User OAuth Token — it starts with `xoxb-`

Add to `.env`:
```
SLACK_BOT_TOKEN=xoxb-...
```

**Allow DMs in Slack:**
1. Click **App Home** in the sidebar
2. Under "Show Tabs", turn on **Messages Tab**
3. Check the box that says "Allow users to send Slash commands and messages from the messages tab"

**Start the bot** (keep this running in a separate Terminal window):
```
python3 tools/slack_bot.py
```

You'll see the message `Slack bot started`. In Slack, find the bot under Apps and send it a message to test it.

---

## Step 8 — Try it out first (no inbox required)

Before pointing it at your real inbox, you can run a demo with 5 fake leads to see exactly what the output looks like. This doesn't need any of the credentials above.

```
python3 tools/generate_sample_data.py
python3 tools/run_pipeline.py --dry-run
```

This takes about 15–20 seconds and shows you the full pipeline in action — enriched leads, SLA countdowns, Slack alerts, and drafted emails. If Slack isn't set up yet, everything just prints in the terminal instead.

---

## Step 9 — Go live against your real inbox

Once everything looks right:

```
python3 tools/run_pipeline.py
```

The tool scans the last 48 hours of emails in your inbox, finds anything related to [Company], processes it, and fires alerts.

> If there are no results the first time, that's normal — it just means there are no qualifying emails in the last 48 hours. Send a test email to yourself mentioning "[Company]" and asking about a demo, then run it again to verify the full flow works.

---

## Step 10 — Make it run automatically every 15 minutes

Right now you have to run it manually. To make it run on its own, add it to your Mac's scheduler (called cron).

In Terminal, type:
```
crontab -e
```

This opens a text editor. Add this line at the bottom (replace the path with wherever you put the project folder):
```
*/15 * * * * cd /path/to/sdr-leads-agent && python3 tools/run_pipeline.py >> /tmp/sdr_pipeline.log 2>&1
```

Save and close the editor. To confirm it's running: `crontab -l`

To see what happened: `cat /tmp/sdr_pipeline.log`

---

## Optional: Richer lead data with Apollo

Out of the box, the tool figures out each lead's specialty, EHR, and location from keywords in their email. This works well for most leads.

If you want to also pull in real company names, job titles, headcount, and LinkedIn profiles, you can connect Apollo.io:

1. Create a free account at [apollo.io](https://www.apollo.io) (free tier covers 50 leads/month)
2. Go to Settings → Integrations → API → Create Key
3. Add it to `.env`:
```
APOLLO_API_KEY=your_key_here
```

The tool will use it automatically from the next run. If Apollo is unavailable, it falls back to keyword-based enrichment without any interruption.

---

## Updating the demo booking link

Every draft email includes a Calendly link. If that link ever changes, update this line in `.env`:

```
COMPANY_CALENDAR_LINK=https://calendly.com/[company]/demo
```

All future drafts will pick up the new link automatically.

---

## Adjusting SLA targets or compliance settings

Everything [Company]-specific is in `config/config.json` — response time targets per signal type, which compliance frameworks apply by region, and which EHR systems map to which specialties. If any of these need to change, that's the file to edit.

The brand voice and email tone guidelines live in `references/brand-context.md` and `references/voice-guide.md`. These get loaded into every Claude prompt. If messaging guidelines change, update those files and all future drafts reflect the update immediately.

---

## If something isn't working

| What you're seeing | What to try |
|--------------------|-------------|
| "Gmail login failed" | The App Password must be the 16-character one from Google, not your regular password |
| "IMAP error" | Go to Gmail → Settings → Forwarding and POP/IMAP → make sure IMAP is enabled |
| Pipeline runs but finds no signals | Send yourself a test email mentioning "[Company]" and re-run |
| Drafts look like templates, not personalised | Check that ANTHROPIC_API_KEY is in `.env` |
| Slack alerts not showing up | Check SLACK_WEBHOOK_URL in `.env` — it should start with `https://hooks.slack.com/services/` |
| Slack bot not responding | Make sure `python3 tools/slack_bot.py` is still running, and that the Messages Tab is enabled in your Slack app settings |

**To run a quick check on all your connections:**
```
python3 tools/check_setup.py
```

This tells you what's working and what isn't, with a specific fix suggestion for anything that fails.

---

*Questions? Reach out to the person who sent you this.*
