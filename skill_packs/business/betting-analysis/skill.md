---
skill: betting-analysis
version: 1.0
backend: local
backend_skill_id: ""
description: Monte Carlo bet analysis — fetch odds, run simulations, return Kelly-optimal recommendation
inputs:
  sport: string
  bankroll: int
  simulations: int
tools: [fetch_odds, monte_carlo_bet]
audit: []
monte_carlo: true
---
## Step 1 — Fetch odds
Call `fetch_odds` for requested sport. Returns lines with American odds.

## Step 2 — Run Monte Carlo
Feed odds into `monte_carlo_bet` with:
  - bankroll = {{bankroll}}
  - simulations = {{simulations}} (default 5000)
  - seed = deterministic (based on timestamp)

## Step 3 — Kelly criterion
For each bet, compute:
  f* = (b·p - q) / b
  where b = decimal odds - 1, p = implied probability, q = 1-p

## Step 4 — Return recommendation
```json
{
  "recommendation": "bet" or "pass",
  "best_bet": "Lakers -5.5",
  "kelly_stake": "$23.50",
  "expected_value": "$1.87",
  "confidence": 0.72,
  "simulation_runs": 5000
}
```

⚠️ NEVER auto-execute financial actions. Human confirmation required.
