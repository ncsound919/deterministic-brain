---
skill: live-docs-to-skill
version: 1.0
backend: local
backend_skill_id: ""
description: Convert live documentation to a skill
inputs:
  url: string
tools: [web_fetch, file_write]
audit: []
monte_carlo: false
---
## Step 1
Fetch documentation from `{{url}}`.

## Step 2
Convert documentation to skill format and write to `output/skills/docs_skill.md`