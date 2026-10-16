---
skill: content-schedule
version: 1.1
backend: local
backend_skill_id: ""
description: Schedule and track content publishing — blog posts, social media, newsletters
inputs:
  action: string
  title: string
  content: string
  platform: string
  scheduled_date: string
  tags: string
tools: [file_read, file_write]
audit: []
monte_carlo: false
---
Engine: `tools/content_engine.py::ContentEngine`. `schedule_content(topic,
platforms, segment=...)` accepts a **CRM segment** — a tag or company in
`crm/contacts.json` — and stamps the draft with the audience it was aimed at
(`tools/crm.py::CRMStore.audience_segments`). With an empty CRM the draft
carries no `crm` block rather than a guessed one. The marketing engine
(`features/autonomous_ceo.py::sync_crm_marketing`) drives this end to end:
pipeline → segment → draft → CRM activity write-back.

## Step 1 — Read content calendar
Load from `content/calendar.json`.

## Step 2 — Perform action
- schedule: add to calendar with title, platform, scheduled_date
- list: show upcoming and past content
- publish: mark as published, log to content/activity.json
- cancel: remove from calendar

## Step 3 — Write calendar
Save updated calendar and activity log.

## Content Calendar JSON Schema
```json
{
  "entries": [{
    "id": "uuid",
    "title": "How to Use DevPets",
    "platform": "blog",
    "content": "...",
    "scheduled": "2026-05-10",
    "status": "scheduled|published|cancelled",
    "tags": ["brain", "devpet"],
    "metrics": {"views": 0, "shares": 0}
  }]
}
```
