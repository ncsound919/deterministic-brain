---
skill: react-component
version: 1.0
description: Generate a React TypeScript component. No LLM needed.
inputs:
  raw: string
  component_name: string
tools:
  - file_write
audit:
  - file_exists
---
# React Component Generator

## Step 1
Render template `Component.tsx.j2` with context
Write result to `builds/{{ session_id }}/{{ component_name or "Component" }}.tsx`
