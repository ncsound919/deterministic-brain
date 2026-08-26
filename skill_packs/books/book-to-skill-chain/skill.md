---
skill: book-to-skill-chain
version: 1.0
backend: local
backend_skill_id: ""
description: Orchestrator for the full book pipeline — ground with BookBridge, synthesize, convert to a skill, register for agents. Single book or whole library mode.
inputs:
  source: string
  skill_name: string
  mode: string
  topic: string
tools: [bookbridge_search, bookbridge_reading_plan, bookbridge_cite, book_to_skill, registry]
audit: []
monte_carlo: false
---
## Step 1
Ground with BookBridge (Stage 1): health check, reading plan, search passages, citations.

## Step 2
Synthesize the author's frameworks into a brief (Stage 2).

## Step 3
Convert with the book-to-skill converter (Stage 3): run extract.py, validate_skill.py.

## Step 4
Register the generated skill in Draymond's registry + entity registry (Stage 4).

## Step 5
Library mode: iterate every indexed book, write a manifest, surface the next reading plan.
