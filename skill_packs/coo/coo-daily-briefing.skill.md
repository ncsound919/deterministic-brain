---
skill_id: coo-daily-briefing
name: COO Daily Portfolio Briefing
version: 1.0
description: >
  Generates a daily briefing covering portfolio health, revenue, momentum, and pending decisions.
tools:
  - github_client
  - orchestrator
  - event_bus
inputs:
  action: str
  include: List[str]
---

# COO Daily Portfolio Briefing

## Purpose
Generate a comprehensive daily briefing for the portfolio principal.

## Sections

1. **Health Summary**: Build status, exception rates, uptime per product
2. **Revenue Summary**: MRR, churn, payment failures, cancellations
3. **Momentum Summary**: Open PRs, commits, deployments
4. **Pending Decisions**: Yellow/Red issues awaiting human approval
5. **Auto-Executed**: Green zone actions taken overnight
6. **Recommendations**: Top 3 actions for the day

## Output Format
```
## Daily Briefing — May 20, 2026

### Health
- Claw Protect: 99.8% uptime, 2 exceptions, 0 critical
- OpenHub: 100% uptime, 1 build failure (resolved)
- Uplift Lab: 99.5% uptime, 3 payment failures

### Revenue
- MRR: $1,247 (+$49 from new subscriptions)
- Churn: 2 customers (-$98)
- Net: +$1,149

### Pending Decisions (7)
- #142 [YELLOW] Build failure in claw-protect
- #145 [RED] Security alert in claw-protect
...

### Recommendations
1. Review security alert #145 — prompt injection detected
2. Approve PR #143 — dependency update for OpenHub
3. Contact 2 customers with expired payment methods
```
