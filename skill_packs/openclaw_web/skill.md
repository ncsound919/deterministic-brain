---
skill: openclaw-web
version: 1.0
backend: openclaw
backend_skill_id: web-scraper-v1
description: Use OpenClaw to scrape and extract data from web pages
inputs:
  url: string
  selector: string
tools: [web_fetch]
audit: []
monte_carlo: false
---
## Step 1
Delegate web scraping to OpenClaw skill.

## Step 2
Return extracted data.