---
skill: webhook-notify
version: 1.0
backend: local
backend_skill_id: ""
description: Post skill execution results to Slack, Discord, or Teams webhooks
inputs:
  channel: string
  skill_name: string
  status: string
  details: string
tools: [slack_notify, discord_notify, notify_skill_result]
audit: []
monte_carlo: false
---
## Step 1 — Build notification message
Format: `*[{status}]* `{skill_name}` — {details}

## Step 2 — Dispatch to channel
- slack → POST to SLACK_WEBHOOK_URL
- discord → POST to DISCORD_WEBHOOK_URL
- teams → POST to TEAMS_WEBHOOK_URL
- all → broadcast to all configured channels

## Step 3 — Return dispatch results
```json
{"ok": true, "message": "...", "channels": ["slack", "discord"]}
```

## Env vars needed
SLACK_WEBHOOK_URL, DISCORD_WEBHOOK_URL, TEAMS_WEBHOOK_URL
