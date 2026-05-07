---
skill: deploy-web
version: 1.0
backend: local
backend_skill_id: ""
description: Deploy built artifacts to Cloudflare Pages / Workers
inputs:
  project: string
  branch: string
  zone: string
  domain: string
tools: [cloudflare_deploy, cloudflare_purge]
audit: []
monte_carlo: false
---
## Step 1 — Validate build artifacts
Check that output directory contains index.html and static assets.

## Step 2 — Deploy to Cloudflare
Call `cloudflare_deploy` for project with branch.
Returns deployment URL and status.

## Step 3 — Purge cache (optional)
Call `cloudflare_purge` on zone to serve latest version.

## Step 4 — Update DNS (optional)
If domain provided, create/update CNAME record pointing to deployment.

Requires: CF_API_TOKEN + CF_ACCOUNT_ID env vars
