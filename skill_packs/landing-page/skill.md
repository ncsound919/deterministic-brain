---
skill: landing-page
version: 1.0
description: Generate a complete landing page HTML with CSS. No LLM needed.
inputs:
  raw: string
  title: string
  subtitle: string
  theme: string
tools:
  - file_write
audit:
  - file_exists
---
# Landing Page Generator

## Step 1
Render template `landing.html.j2` with context
Write result to `builds/{{ session_id }}/index.html`

## Step 2
Render template `style.css.j2` with context
Write result to `builds/{{ session_id }}/style.css`
