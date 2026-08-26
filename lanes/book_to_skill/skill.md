---
skill: book-to-skill-lane
version: 1.0
backend: local
backend_skill_id: ""
description: Ground a book/topic via BookBridge and distill a reusable skill stub — the deterministic-brain half of the book-to-skill chain.
inputs:
  book_id: string
  topic: string
  source: string
tools: [bookbridge_status, bookbridge_search, bookbridge_books, bookbridge_scan, bookbridge_distill]
audit: []
monte_carlo: false
---
## Step 1
Health check BookBridge via bookbridge_status. If offline and no local source, fail with a start hint.

## Step 2
Trigger a best-effort scan so newly dropped books are ingested.

## Step 3
If only a topic was given, list candidate books from the library.

## Step 4
Distill the book/topic into a skill.md stub under skill_packs/books/ via bookbridge_distill.

## Step 5
Return the stub path and hint the caller to run Draymond's book-to-skill-chain Stage 3 for full conversion + registration.
