---
skill: github-manage
version: 1.0
backend: local
backend_skill_id: ""
description: GitHub operations — issues, PRs, CI status, code search
inputs:
  action: string
  owner: string
  repo: string
  title: string
  body: string
tools: [github_list_issues, github_create_issue, github_search_code]
audit: []
monte_carlo: false
---
## Step 1 — Perform GitHub action
- list_issues: list open issues for owner/repo
- create_issue: create issue with title and body
- search_code: search GitHub code with query
- list_prs: list pull requests
- ci_status: check CI status for a ref

## Step 2 — Return result
Structured response with issue URLs, PR numbers, or search results.

Requires: GITHUB_TOKEN env var (classic PAT with repo scope)
