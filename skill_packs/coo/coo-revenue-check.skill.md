---
skill_id: coo-revenue-check
name: COO Stripe Revenue Check
version: 1.0
description: >
  Checks Stripe for payment failures, cancellations, and MRR changes across revenue-generating products.
tools:
  - stripe_client
  - github_queue
inputs:
  action: str
  products: List[str]
---

# COO Stripe Revenue Check

## Purpose
Monitor revenue-generating products for payment issues and subscription changes.

## Steps

1. **Fetch Stripe events** for the last 4 hours
2. **For each product** in the revenue list:
   - Check for failed payments → Yellow zone issue
   - Check for cancellations → Yellow zone issue
   - Calculate MRR change → Log to economic vector
3. **Open GitHub Issues** for any payment failures or cancellations
4. **Update economic vectors** in the portfolio state

## Output
```json
{
  "products_checked": 2,
  "payment_failures": 3,
  "cancellations": 1,
  "mrr_change": -49.00,
  "issues_opened": 4,
  "timestamp": "2026-05-20T09:00:00Z"
}
```
