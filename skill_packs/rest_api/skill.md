---
skill: scaffold-rest-api
version: 1.0
backend: local
backend_skill_id: ""
description: Scaffold a REST API for a resource
inputs:
  resource: string
tools: [file_write]
audit: []
monte_carlo: false
---
## Step 1
Create basic REST API structure for resource `{{resource}}`.

## Step 2
Write API file to `output/api/{{resource}}_api.py`