---
skill: email-send
version: 1.0
backend: local
backend_skill_id: ""
description: Send transactional emails via SMTP — notifications, alerts, reports
inputs:
  to: string
  subject: string
  body: string
  cc: string
  bcc: string
tools: [send_email]
audit: []
monte_carlo: false
---
## Step 1
Call `send_email` tool with parameters:
  - to = {{to}}
  - subject = {{subject}}
  - body = {{body}}
  - cc = {{cc}}
  - bcc = {{bcc}}

## Step 2
Return the SMTP response status and message ID.
