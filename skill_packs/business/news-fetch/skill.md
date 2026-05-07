---
skill: news-fetch
version: 1.0
backend: local
backend_skill_id: ""
description: Fetch headlines from RSS sources — tech, crypto, sports, finance, AI
inputs:
  categories: string
tools: [fetch_news]
audit: []
monte_carlo: false
---
## Step 1
Call `fetch_news` tool. Returns headlines grouped by category with keywords.

## Step 2
Extract top stories, rank by keyword relevance to the brain's current context.

## Step 3
Emit `news_pulse` event on bus for AutoDream to process.
