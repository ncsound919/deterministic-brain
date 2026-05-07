---
skill: openclaw-data
version: 1.0
backend: openclaw
backend_skill_id: data-processor-v1
description: Use OpenClaw to process and transform data files
inputs:
  file_path: string
  operation: string
tools: [file_read, file_write]
audit: []
monte_carlo: false
---
## Step 1
Delegate data processing to OpenClaw skill.

## Step 2
Return processed result.