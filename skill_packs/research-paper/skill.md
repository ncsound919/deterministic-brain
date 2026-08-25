---
skill: research-paper
version: 1.0
description: "Generate a structured research paper deterministically (no LLM) from sourced findings, and publish it to Overlay Global Lens. Uses Jinja2 templates for the paper skeleton and fills sections with the provided research context (arxiv/news/market data or inline findings)."
inputs:
  raw: string
  topic: string
  title: string
  abstract: string
  findings: list
  sources: list
  category: string
  pillar: string
  source_name: string
tools:
  - file_write
  - publish_global_lens
audit:
  - file_exists
---

# Deterministic Research Paper Generator

## Step 1
Render template `paper.md.j2` with context
Write result to `builds/{{ session_id }}/research_paper.md`

## Step 2
Run command `publish_global_lens` with `builds/{{ session_id }}/research_paper.md`
