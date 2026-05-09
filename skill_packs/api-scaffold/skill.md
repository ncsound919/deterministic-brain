---
skill: api-scaffold
version: 1.0
description: Generate a FastAPI API scaffold. No LLM needed.
inputs:
  raw: string
  resource: string
tools:
  - file_write
audit:
  - file_exists
---
# FastAPI Scaffold Generator

## Step 1
Render template `main.py.j2` with context
Write result to `builds/{{ session_id }}/main.py`

## Step 2
Render template `requirements.txt.j2` with context
Write result to `builds/{{ session_id }}/requirements.txt`
