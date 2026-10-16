---
skill: crm-contact
version: 1.1
backend: local
backend_skill_id: ""
description: Manage CRM contacts — create, update, search, tag
inputs:
  action: string
  name: string
  email: string
  company: string
  tags: string
tools: [crm_contact]
audit: []
monte_carlo: false
---
Deterministic handler: `skills/crm_tools.py::handle_crm_contact` (registered on
the IntentRouter as `crm_contact`). It writes `crm/contacts.json` through
`tools/crm.py`; the prose below is the specification it implements.

Grammar (anything it cannot parse is a structured failure, never a guess):

    create contact Dana Reed email dana@acme.test at Acme tag smb, outbound
    update contact dana@acme.test status customer
    search contacts tag smb
    list contacts

## Step 1 — Read CRM store
Load existing contacts from `crm/contacts.json`.

## Step 2 — Perform action
- create: add new contact with name, email, company, tags
- update: find by email and update fields
- search: filter by name, company, or tags
- list: return all contacts sorted by last_modified

## Step 3 — Write CRM store
Save updated contacts to `crm/contacts.json`.
