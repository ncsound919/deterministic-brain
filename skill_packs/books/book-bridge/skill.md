---
skill: book-bridge
version: 1.0
backend: local
backend_skill_id: ""
description: Bridge to the BookBridge book library (:8777) — grounded search, reading plans, retrieval, citations, summaries, and library distillation.
inputs:
  query: string
  topic: string
  book_id: string
tools: [bookbridge_search, bookbridge_reading_plan, bookbridge_retrieve, bookbridge_cite, bookbridge_summarize, bookbridge_books, bookbridge_scan]
audit: []
monte_carlo: false
---
## Step 1
Health check BookBridge via `bookbridge_status`. If offline, report it — never fabricate passages.

## Step 2
Orient with `bookbridge_reading_plan` for the topic, then `bookbridge_search` for targeted passages.

## Step 3
Retrieve full context with `bookbridge_retrieve` when a snippet is too short.

## Step 4
Always attach `bookbridge_cite` output to every book-sourced claim. Log provenance.

## Step 5
If the goal is to distill the book into a skill, call the `book-to-skill-chain` skill (Stage 1 grounding).
