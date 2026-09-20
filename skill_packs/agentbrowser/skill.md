---
skill: agentbrowser
version: 1.0.0
description: Browser automation via your logged-in Comet session — research, scraping, websearch, setup flows, authenticated actions. Uses the mirrored Comet profile so Supabase/Vercel/etc. sessions are already live.
inputs:
  task: string
  url: string
  selector: string
  text: string
  script: string
tools:
  - browser_launch
  - browser_navigate
  - browser_click
  - browser_fill
  - browser_screenshot
  - browser_get_content
  - browser_execute
audit:
  - browser_content_contains
---

# AgentBrowser — Ecosystem Browser Automation

Uses `AGENTBROWSER_URL` + `AGENTBROWSER_API_KEY` (Draymond env) → `http://localhost:3700/api/browser-control` with `X-Agent-Auth` (interpolated at call time so key rotation is safe). Comet engine with mirrored real profile (`AGENTBROWSER_COMET_REAL_PROFILE=1`) transports your logged-in sessions.

## Actions
- `browser_launch { engine: "comet", headless: true }` — attach to your Comet session
- `browser_navigate { url }` — open any URL as you
- `browser_click { selector|text }` / `browser_fill { selector, value }` — drive UI
- `browser_execute { script }` — run JS inside the authenticated page (use for Supabase SQL via `fetch('/dashboard/api/pg-meta/<ref>/query')`, Vercel invites, etc.)
- `browser_get_content` / `browser_screenshot` — read back state

## Execution
1. `POST $AGENTBROWSER_URL/api/browser-control` with `{ action: "launch", config: { engine: "comet" } }` and header `X-Agent-Auth: $AGENTBROWSER_API_KEY`.
2. Then `navigate` → `execute`/`click`/`fill` as needed. Sessions persist in `comet-profile` mirror.

## Ecosystem Wiring
- Draymond entity `agent-browser` (http_api `http://localhost:3700`, `X-Agent-Auth: ${AGENTBROWSER_API_KEY}`) — chains call it via `executeChain` on that entity.
- LLM fleet-client + deterministic brain MoE router surface this skill for any task tagged research/scraping/setup/websearch/login.
- Keywire/Axiom call the same HTTP endpoint directly (same env contract) or via the deterministic brain skill.
