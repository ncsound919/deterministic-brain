---
skill: claude-code
version: 1.0
backend: claude
backend_skill_id: claude-sonnet-4-20250514
description: Use Claude to generate high-quality code with advanced reasoning
inputs:
  task: string
  constraints: string
tools: [llm]
audit: []
monte_carlo: false
---
## Step 1
Delegate code generation to Claude Sonnet 4 with task context.

## Step 2
Return generated code to caller.