---
skill: agent-orchestrate
version: 1.0
backend: local
backend_skill_id: ""
description: Orchestrate OpenClaw and Hermes agents with deterministic supervision
inputs:
  target_agent: string
  task: string
  inputs_json: string
  wait: bool
tools: [relay_forward, relay_broadcast]
audit: []
monte_carlo: false
---
## Step 1 — Resolve target agent
Map `target_agent` to a registered relay agent:
- "openclaw" → relay to registered OpenClaw instance
- "hermes" → relay to registered Hermes instance  
- "swarm" → broadcast to all registered agents
- "kairos" → trigger KAIROS daemon task

## Step 2 — Build task payload
Parse `inputs_json` into the relay body format:
```json
{
  "query": "{{task}}",
  "context": { ...inputs },
  "supervisor": "deterministic-brain",
  "trace_id": "{{session_id}}"
}
```

## Step 3 — Relay execution
Forward via `POST /relay` to target agent with 30s timeout.
Collect response with:
- status: success / failure / timeout
- output: agent's final output
- artifacts: any files produced
- trace: execution trace for audit

## Step 4 — Deterministic validation
Run the response through the brain's pre-audit:
- Check for injection patterns
- Validate output structure
- Score confidence

If audit fails, auto-retry with modified prompt.
Max 3 retries per task.

## Agent Registry (tools/relay.py)
OpenClaw agents: `http://localhost:8002`
Hermes agents: `http://localhost:8003`
Custom agents register via `POST /relay/register`
