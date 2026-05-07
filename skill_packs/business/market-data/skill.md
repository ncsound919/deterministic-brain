---
skill: market-data
version: 1.0
backend: local
backend_skill_id: ""
description: Fetch crypto prices (Coinbase) and stock data (Yahoo Finance)
inputs:
  symbols: string
  currency: string
tools: [market_summary, crypto_prices, stock_prices]
audit: []
monte_carlo: false
---
## Step 1 — Fetch crypto prices
Call `crypto_prices` — returns BTC-USD, ETH-USD, SOL-USD, DOGE-USD spot prices.

## Step 2 — Fetch stock prices (optional)
Call `stock_prices` with requested symbols. Requires yfinance package.

## Step 3 — Assemble market summary
Combine crypto + stock data into a single structured report.
Emit `market_update` event on bus.
