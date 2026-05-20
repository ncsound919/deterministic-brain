---
skill_id: coo-health-check
name: COO Portfolio Health Check
version: 1.0
description: >
  Checks all portfolio products for build failures, exceptions, and security alerts.
  Classifies events using the Traffic Light system and opens GitHub Issues for Yellow/Red events.
tools:
  - github_client
  - event_bus
  - classifier
inputs:
  products: List[str]
  action: str
---

# COO Portfolio Health Check

## Purpose
Run a health check across all portfolio products. Ingest events, classify them, and dispatch to the appropriate zone.

## Steps

1. **Load portfolio state** from `coo/orchestrator.py`
2. **For each product**, simulate event ingestion:
   - Check GitHub for recent failures
   - Check Sentry for exceptions
   - Check Stripe for payment issues
3. **Classify each event** using `coo/classifier.py`
4. **Dispatch**:
   - Green: auto-execute (log only)
   - Yellow: open GitHub Issue
   - Red: escalate immediately
5. **Report** summary of actions taken

## Output
```json
{
  "products_checked": 5,
  "events_processed": 12,
  "green_auto_executed": 3,
  "yellow_issues_opened": 7,
  "red_escalated": 2,
  "timestamp": "2026-05-20T05:00:00Z"
}
```
