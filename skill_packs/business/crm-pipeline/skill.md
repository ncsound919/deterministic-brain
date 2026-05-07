---
skill: crm-pipeline
version: 1.0
backend: local
backend_skill_id: ""
description: Manage CRM deal pipeline — stages, values, probabilities
inputs:
  action: string
  deal_name: string
  contact_email: string
  stage: string
  value: int
tools: [file_read, file_write]
audit: []
monte_carlo: false
---
## Step 1 — Read pipeline store
Load existing deals from `crm/pipeline.json`.

## Step 2 — Perform action
- create: add new deal with contact, stage, value
- move: change deal stage (lead → qualified → proposal → closed)
- forecast: sum values by stage, compute weighted pipeline

## Step 3 — Write pipeline store
Save updated pipeline to `crm/pipeline.json`.
