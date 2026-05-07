---
skill: claude-refactor
version: 1.0
backend: claude
backend_skill_id: claude-sonnet-4-20250514
description: Use Claude to refactor and improve existing code
inputs:
  code: string
  goal: string
tools: [llm]
audit: []
monte_carlo: false
---
## Step 1
Send code to Claude for refactoring analysis.

## Step 2
Return improved code.