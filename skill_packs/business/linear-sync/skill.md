---
skill: linear-sync
version: 1.0
backend: local
backend_skill_id: ""
description: Sync Linear/Jira issues with brain skill execution status
inputs:
  action: string
  team_id: string
  title: string
  description: string
  priority: int
tools: [linear_list_issues, linear_create_issue, linear_search]
audit: []
monte_carlo: false
---
## Step 1 — Perform Linear/Jira action
- list_issues: view team's issues filtered by state
- create_issue: add new task (auto-triggered on skill failure)
- search: find issues matching keyword
- sync_status: update issue with skill execution result

## Step 2 — Return structured result

## Team workflow
When brain executes a skill:
- Success → post to Slack/Discord, update Linear issue if linked
- Failure → create Linear issue with trace + suggested fix
- Blocked → alert team via webhook + create high-priority issue

Requires: LINEAR_API_KEY or JIRA_API_TOKEN + JIRA_DOMAIN + JIRA_EMAIL
