---
skill: book-synthesis-personal
version: 1.0
backend: local
backend_skill_id: ""
description: Transform a nonfiction book into a deeply personalized synthesis — every idea translated into the reader's domain, problems, and cognitive style. Produces PDF + markdown.
inputs:
  book: string
  reader_profile: string
tools: [bookbridge_search, bookbridge_retrieve, bookbridge_cite]
audit: []
monte_carlo: false
---
## Step 1
Load the reader profile if present; otherwise ask the 12-13 onboarding questions once.

## Step 2
Ground the book with BookBridge (search + retrieve) and collect cited passages.

## Step 3
Translate every idea into the reader's domain — not a summary but an applied synthesis.

## Step 4
Produce the markdown synthesis and the visual PDF using the synthesis-template and visual-principles references.

## Step 5
Attach citations for every book-sourced claim.
