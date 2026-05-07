---
skill: add-auth
version: 1.0
backend: local
backend_skill_id: ""
description: Add authentication middleware to a resource
inputs:
  resource: string
tools: [file_write]
audit: []
monte_carlo: false
---
## Step 1
Generate authentication middleware for resource `{{resource}}`.

## Step 2
Write auth file to `output/auth/{{resource}}_auth.py`