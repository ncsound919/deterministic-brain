# Features Directory

This directory contains specialized feature modules for the Deterministic Brain system.

## File Status Table

| File | Purpose | Status |
|------|---------|--------|
| `buddy.py` | Buddy component | Experimental |
| `chicago_mcp.py` | Chicago MCP integration | Experimental |
| `kairos.py` | Kairos time-tracking | Active |
| `kairos_channels.py` | Kairos channel management | Active |
| `kairos_github_webhooks.py` | GitHub webhook handler for Kairos | Active |
| `ultraplan.py` | Ultra-plan planning module | Experimental |
| `connector_text.py` | Text connector utilities | Active |
| `scheduler.py` | Task scheduling system | Active |
| `auto_dream.py` | Dream state automation | Active |
| `repoforge_client.py` | RepoForge API client | Active |
| `social_media_dashboard.py` | Social media output agent | Experimental |
| `browser_harness.py` | Web agent harness | Active |
| `tap919_middleman.py` | Middleware for agent handoffs | Active |

## Status Definitions

- **Active**: Integrated into main workflow, tested
- **Experimental**: Prototype, may be unstable
- **Deprecated**: No longer maintained

## Adding New Features

1. Add entry to table above with status
2. Include docstring with module purpose
3. Add tests in `tests/` directory
4. Update this README if behavior changes
