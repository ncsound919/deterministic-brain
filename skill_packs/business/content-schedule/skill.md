---
skill: content-schedule
version: 1.0
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
