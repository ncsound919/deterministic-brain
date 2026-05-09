---
skill: css-layout
version: 1.0
description: Generate CSS grid/flex layout. No LLM needed.
inputs:
  raw: string
  layout_type: string
tools:
  - file_write
audit:
  - file_exists
---
# CSS Layout Generator

## Step 1
Render template `layout.html.j2` with context
Write result to `builds/{{ session_id }}/layout.html`
