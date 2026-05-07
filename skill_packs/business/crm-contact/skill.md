---
skill: crm-contact
version: 1.0
backend: local
backend_skill_id: ""
description: Manage CRM contacts — create, update, search, tag
inputs:
  action: string
  name: string
  email: string
  company: string
  tags: string
tools: [file_read, file_write]
audit: []
monte_carlo: false
---
## Step 1 — Read CRM store
Load existing contacts from `crm/contacts.json`.

## Step 2 — Perform action
- create: add new contact with name, email, company, tags
- update: find by email and update fields
- search: filter by name, company, or tags
- list: return all contacts sorted by last_modified

## Step 3 — Write CRM store
Save updated contacts to `crm/contacts.json`.
