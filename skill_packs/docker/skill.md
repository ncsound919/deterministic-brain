---
skill: generate-dockerfile
version: 1.0
backend: local
backend_skill_id: ""
description: Generate a Dockerfile for a service
inputs:
  service: string
tools: [file_write]
audit: []
monte_carlo: false
---
## Step 1
Generate Dockerfile for service `{{service}}`.

## Step 2
Write Dockerfile to `output/docker/{{service}}/Dockerfile`