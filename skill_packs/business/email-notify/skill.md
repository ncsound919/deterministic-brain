---
skill: email-notify
version: 1.0
backend: local
backend_skill_id: ""
description: Send notification emails for skill execution results — success, failure, blocked
inputs:
  to: string
  skill_name: string
  status: string
  details: string
tools: [send_email]
audit: []
monte_carlo: false
---
## Step 1
Build notification message from status and details.
Format: "[Brain] {{skill_name}}: {{status}}"

## Step 2
Call `send_email` with formatted notification.
Include execution details in body.

```python
body = f"Skill: {skill_name}\nStatus: {status}\n\n{details}"
```
