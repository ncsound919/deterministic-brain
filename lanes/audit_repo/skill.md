---
skill: audit-repo
version: 1.0
backend: local
backend_skill_id: ""
description: Audit a repository for code quality and security
inputs:
  repo_path: string
tools: [file_read]
audit: []
monte_carlo: false
---
## Step 1
Analyze repository at `{{repo_path}}` for code quality and security issues.

## Step 2
Generate audit report in `output/audit/{{repo_path}}_report.md`