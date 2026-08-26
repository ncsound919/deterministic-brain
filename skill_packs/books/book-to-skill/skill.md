---
skill: book-to-skill
version: 1.0
backend: local
backend_skill_id: ""
description: Convert books and documents into structured agent skills — frameworks, principles, techniques, anti-patterns — via Draymond's book-to-skill converter.
inputs:
  source: string
  skill_name: string
  book_type: string
tools: [bookbridge_search, bookbridge_cite, extract]
audit: []
monte_carlo: false
---
## Step 1
Validate the source path (PDF/EPUB/DOCX/MD/TXT/RTF/MOBI). Ground with BookBridge passages first.

## Step 2
Run Draymond's converter: `python agents/skills/book-to-skill/scripts/extract.py <source> <slug> --mode text`.

## Step 3
Generate SKILL.md + chapters/ + glossary + patterns + cheatsheet following the book-to-skill workflow.

## Step 4
Run `validate_skill.py` and fix any failures before registering.

## Step 5
Register the generated skill in Draymond's registry + entity registry so agents can load it.
