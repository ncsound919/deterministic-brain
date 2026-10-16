---
skill: crm-pipeline
version: 1.1
backend: local
backend_skill_id: ""
description: Manage CRM deal pipeline — stages, values, probabilities
inputs:
  action: string
  deal_name: string
  contact_email: string
  stage: string
  value: int
tools: [crm_pipeline]
audit: []
monte_carlo: false
---
Deterministic handler: `skills/crm_tools.py::handle_crm_pipeline` (registered on
the IntentRouter as `crm_pipeline`). It writes `crm/pipeline.json` through
`tools/crm.py`; the prose below is the specification it implements.

Grammar:

    create deal Acme pilot for dana@acme.test stage proposal value 12000
    move deal <deal_id> to closed
    forecast pipeline

Stages are `lead`, `qualified`, `proposal`, `closed`. Win probability is fixed
per stage in `tools/crm.py::STAGE_PROBABILITY`, so the weighted forecast is the
same number for every reader.

## Step 1 — Read pipeline store
Load existing deals from `crm/pipeline.json`.

## Step 2 — Perform action
- create: add new deal with contact, stage, value
- move: change deal stage (lead → qualified → proposal → closed)
- forecast: sum values by stage, compute weighted pipeline

## Step 3 — Write pipeline store
Save updated pipeline to `crm/pipeline.json`.
