# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This architecture separates concerns so that probabilistic AI handles reasoning while deterministic code handles execution. That separation is what makes this system reliable.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use, expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself
- Example: If the pipeline detects a DEMO_REQUEST, don't draft a response directly. Read `workflows/inbound_triage.md`, confirm enrichment ran, then call `tools/draft_response.py`

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work
- API calls, data transformations, file operations
- All credentials and API keys live in `.env` — never baked into scripts
- These scripts are consistent, testable, and fast

**Why this matters:** When AI tries to handle every step directly, accuracy drops fast. If each step is 90% accurate, you're down to 59% success after just five steps. By offloading execution to deterministic scripts, you stay focused on orchestration and decision-making where you excel.

## How to Operate

**1. Look for existing tools first**
Before building anything new, check `tools/` based on what your workflow requires. Only create new scripts when nothing exists for that task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace
- Fix the script and retest (if it uses paid API calls or credits, check with me before running again)
- Document what you learned in the workflow (rate limits, timing quirks, unexpected behavior)

**3. Keep workflows current**
Workflows should evolve as you learn. When you find better methods, discover constraints, or encounter recurring issues, update the workflow. Don't create or overwrite workflows without asking unless explicitly told to.

## The Self-Improvement Loop

Every failure is a chance to make the system stronger:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with the new approach
5. Move on with a more robust system

## File Structure

```
.tmp/               # Intermediate JSON (regenerated each run, gitignored)
  raw_signals.json          ← Gmail + Instantly inbound signals
  enriched_signals.json     ← + specialty, geo, EHR, compliance, objection
  scored_signals.json       ← + SLA timing, crack detection, priority rank
  response_drafts.json      ← Draft emails keyed by signal_id
  processed_signal_ids.json ← Dedup registry
  lead_context.json         ← Enriched lead records for Slack bot
  execution_log.json        ← Pipeline run log

tools/              # Python scripts (one job each)
workflows/          # Markdown SOPs
config/             # Company-specific config (swap to redeploy for another client)
  [company].json                ← SLA rules, ICP, compliance map, EHR map
references/         # Brand files (loaded at runtime, never summarized inline)
  [company]-brand.md
  [company]-voice.md
outputs/            # Final deliverables
  triage_queue.json         ← Prioritized queue for the SDR
.credentials/       # OAuth tokens (gitignored)
.env                # API keys (NEVER store secrets anywhere else)
```

**Core principle:** `.tmp/` is disposable. `outputs/` is what the SDR acts on. Everything else is infrastructure.

## Pipeline Steps

The full pipeline runs as:
```
Step 1: scan_inbox.py        → .tmp/raw_signals.json (Gmail)
Step 2: scan_instantly.py    → .tmp/raw_signals.json (Instantly, appended)
Step 3: enrich_lead.py       → .tmp/enriched_signals.json
Step 4: score_urgency.py     → .tmp/scored_signals.json
Step 5: draft_response.py    → .tmp/response_drafts.json
Step 6: build_queue.py       → outputs/triage_queue.json
Step 7: notify_slack.py      → Slack alerts (or terminal fallback)
```

Run the full pipeline: `python3 tools/run_pipeline.py`
Dry run (skip Gmail + Slack): `python3 tools/run_pipeline.py --dry-run`

## Slack Interface

The SDR's primary interface is Slack, not the terminal. Two modes:

**Automated alerts** (`notify_slack.py`): Posts hot signal alerts and crack warnings to `#speed-to-lead` after each pipeline run. Falls back to terminal output if `SLACK_BOT_TOKEN` is not set — the pipeline never fails because of missing Slack credentials.

**1v1 chat** (`slack_bot.py`): Long-lived Socket Mode process. SDR DMs the bot with questions about leads, drafts, or SLA status. Uses Claude Haiku + current context files to respond in <3 seconds. Run separately: `python3 tools/slack_bot.py`.

## Content Generation for [Company]

Any tool that generates [Company]-facing content (email drafts, Slack messages, in-app copy) must load both brand files before generating:

- **`references/brand-context.md`**: Brand identity, tone of voice, ICP, competitive positioning, compliance context
- **`references/voice-guide.md`**: Observed production emails, messaging DOs/DON'Ts, exact product terminology

The existing generation tools (`draft_response.py`, `notify_slack.py`) load these files automatically at runtime. Inline summaries in scripts are not substitutes for the full files.

**Hard rules for all [Company] content:**
- No emoji, no urgency language, no superlatives
- Sign-off: "The [Company] Team" exactly
- Max 5 sentences in body
- Lead with clinical outcome, not product feature
- Greeting: "Hi {firstName}," — never "Dear Dr."

## Bottom Line

You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go.

Stay pragmatic. Stay reliable. Keep learning.
