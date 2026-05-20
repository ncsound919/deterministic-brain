---
skill_id: coo-issue-triage
name: COO GitHub Issue Triage
version: 1.0
description: >
  Triages open COO Brain GitHub Issues. Auto-closes resolved issues, escalates stale ones, and updates decision cards.
tools:
  - github_client
  - orchestrator
inputs:
  action: str
  labels: List[str]
---

# COO GitHub Issue Triage

## Purpose
Review all open COO Brain issues and take appropriate action based on their state.

## Steps

1. **Fetch open issues** with labels `coo-brain`, `yellow`, `red`
2. **For each issue**:
   - Check if the underlying problem is resolved (CI green, no new exceptions)
   - If resolved → close issue with "auto-resolved" comment
   - If stale (>7 days no activity) → escalate to Red zone
   - If active → leave open, update priority score
3. **Update decision cards** in the orchestrator
4. **Report** triage summary

## Output
```json
{
  "issues_reviewed": 15,
  "auto_closed": 4,
  "escalated": 2,
  "left_open": 9,
  "timestamp": "2026-05-20T05:30:00Z"
}
```
