# Expansion Plan: Integrating Each Capability

## 1. MCP Integration
**Goal**: Connect to external MCP servers for more tools

### Architecture
```
deterministic-brain
    │
    ├─► tools/mcp_client.py    (new - MCP protocol client)
    │      │
    │      ├─ discover_servers()    - Auto-detect running MCP servers
    │      ├─ connect(server_url)   - Connect to MCP server
    │      ├─ call(tool_name, args) - Call tool via MCP
    │      └─ list_tools()          - Get available tools from server
    │
    ├─► config/mcp_servers.yaml   (new - MCP server configs)
    │      Example:
    │        servers:
    │          filesystem:
    │            command: npx
    │            args: ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    │          slack:
    │            url: "http://localhost:3000"
```

### Implementation Steps

| Step | File | Task |
|------|------|------|
| 1.1 | `tools/mcp_client.py` | Create MCP client class with stdio and HTTP transport |
| 1.2 | `tools/mcp_client.py` | Implement `discover()` to find running servers |
| 1.3 | `tools/mcp_client.py` | Implement `call_tool()` for remote execution |
| 1.4 | `tools/registry.py` | Auto-register MCP tools in ToolRegistry |
| 1.5 | `config/mcp_servers.yaml` | Add example MCP server configs |
| 1.6 | `tools/mcp_client.py` | Add server health checks and reconnection |

### Files to Create/Modify
- **Create**: `tools/mcp_client.py`, `config/mcp_servers.yaml`
- **Modify**: `tools/registry.py`

### Success Criteria
- [ ] Can connect to at least one MCP server (filesystem or slack)
- [ ] Tools from MCP server appear in `tr.list_tools()`
- [ ] MCP tool calls return valid results
- [ ] Graceful fallback when MCP server unavailable

---

## 2. Database Tools
**Goal**: Add SQL query, migration, and schema tools

### Architecture
```
deterministic-brain
    │
    ├─► tools/db_client.py      (new - DB abstraction layer)
    │      │
    │      ├─ connect(connection_string)
    │      ├─ execute(query) → results
    │      ├─ schema() → table info
    │      ├─ migrations list/apply/rollback
    │
    ├─► lanes/db_operations/lane.py  (new - DB lane)
    │      │
    │      ├─ query(sql) → results
    │      ├─ migrate(up/down)
    │      ├─ backup()
    │      └─ restore()
```

### Implementation Steps

| Step | File | Task |
|------|------|------|
| 2.1 | `tools/db_client.py` | Create DBClient with SQLite, PostgreSQL, MySQL support |
| 2.2 | `tools/db_client.py` | Implement `execute()`, `query()`, `schema()` |
| 2.3 | `tools/db_client.py` | Add migration runner (up/down files) |
| 2.4 | `lanes/db_operations/lane.py` | Create DB operations lane |
| 2.5 | `tools/registry.py` | Register db tools: `db_query`, `db_execute`, `db_migrate` |
| 2.6 | `tools/db_client.py` | Add connection pooling and error handling |

### Files to Create/Modify
- **Create**: `tools/db_client.py`, `lanes/db_operations/lane.py`
- **Modify**: `tools/registry.py`

### Success Criteria
- [ ] Can connect to SQLite and at least one remote DB
- [ ] Execute SELECT queries and return results
- [ ] Run migrations from files
- [ ] Schema introspection works

---

## 3. Notification System
**Goal**: Integrate with Slack, Discord, email notifications

### Architecture
```
deterministic-brain
    │
    ├─► features/notifications.py  (new - notification manager)
    │      │
    │      ├─ send_slack(channel, message)
    │      ├─ send_discord(webhook, message)
    │      ├─ send_email(to, subject, body)
    │      └─ notify(platform, config, message)
    │
    ├─► features/alert_rules.py    (new - alert automation)
    │      │
    │      ├─ Rule(condition, action)
    │      ├─ evaluate(event) → trigger?
    │      └─ actions: slack, email, webhook
```

### Implementation Steps

| Step | File | Task |
|------|------|------|
| 3.1 | `features/notifications.py` | Create NotificationManager class |
| 3.2 | `features/notifications.py` | Implement Slack webhook sender |
| 3.3 | `features/notifications.py` | Implement Discord webhook sender |
| 3.4 | `features/notifications.py` | Implement email (SMTP) sender |
| 3.5 | `features/alert_rules.py` | Create AlertRule with condition/action |
| 3.6 | `features/notifications.py` | Wire to scheduler for periodic alerts |
| 3.7 | `tools/registry.py` | Register: `notify_slack`, `notify_discord`, `notify_email` |

### Files to Create/Modify
- **Create**: `features/notifications.py`, `features/alert_rules.py`
- **Modify**: `tools/registry.py`

### Success Criteria
- [ ] Can send Slack message to configured channel
- [ ] Can send Discord message via webhook
- [ ] Can send email via SMTP
- [ ] Alert rules can trigger notifications

---

## 4. State Persistence
**Goal**: Save/restore system state for restart and recovery

### Architecture
```
deterministic-brain
    │
    ├─► brain/state_manager.py   (new - state persistence)
    │      │
    │      ├─ save(state, snapshot_name)
    │      ├─ load(snapshot_name) → state
    │      ├─ list_snapshots()
    │      ├─ auto_snapshot(interval)
    │      └─ restore_latest()
    │
    ├─► .state/snapshots/       (new - state storage)
    │      ├─ 2026-05-07_10-30-00.json
    │      ├─ 2026-05-07_11-00-00.json
    │      └─ metadata.yaml
```

### Implementation Steps

| Step | File | Task |
|------|------|------|
| 4.1 | `brain/state_manager.py` | Create StateManager with save/load |
| 4.2 | `brain/state_manager.py` | Implement JSON serialization for state |
| 4.3 | `brain/state_manager.py` | Add snapshot metadata (timestamp, query count, etc.) |
| 4.4 | `brain/state_manager.py` | Add incremental snapshots (diff) |
| 4.5 | `brain/state_manager.py` | Wire to scheduler for auto-snapshots |
| 4.6 | `brain/memory.py` | Integrate state loading on init |
| 4.7 | `main.py` | Add `--restore` CLI option |

### Files to Create/Modify
- **Create**: `brain/state_manager.py`, `.state/` directory structure
- **Modify**: `brain/memory.py`, `main.py`

### Success Criteria
- [ ] Can save current state to named snapshot
- [ ] Can load and restore from snapshot
- [ ] Auto-snapshot runs on schedule
- [ ] State survives process restart

---

## 5. Multi-Agent Coordination
**Goal**: Orchestrate multiple agents for complex workflows

### Architecture
```
deterministic-brain
    │
    ├─ orchestration/multi_agent.py  (new - agent coordinator)
    │      │
    │      ├─ spawn(agent_type, config) → agent_id
    │      ├─ delegate(task, agent_ids) → results
    │      ├─ gather(parallel_tasks) → all_results
    │      ├─ sequence(task_chain) → chain_results
    │      └─ monitor(agent_id) → status
    │
    ├─ lanes/multi_agent/lane.py    (new - multi-agent lane)
    │      │
    │      ├─ run_parallel(skills)
    │      ├─ run_sequence(skills)
    │      └─ run_delegate(task, agents)
```

### Implementation Steps

| Step | File | Task |
|------|------|------|
| 5.1 | `orchestration/multi_agent.py` | Create AgentPool for spawning multiple agents |
| 5.2 | `orchestration/multi_agent.py` | Implement `delegate()` with task distribution |
| 5.3 | `orchestration/multi_agent.py` | Implement `gather()` for parallel execution |
| 5.4 | `orchestration/multi_agent.py` | Add agent health monitoring |
| 5.5 | `lanes/multi_agent/lane.py` | Create lane for multi-agent workflows |
| 5.6 | `orchestration/multi_agent.py` | Add result aggregation and merging |
| 5.7 | `orchestration/multi_agent.py` | Add timeout and failure handling |

### Files to Create/Modify
- **Create**: `orchestration/multi_agent.py`, `lanes/multi_agent/lane.py`
- **Modify**: `orchestration/router.py` (if needed)

### Success Criteria
- [ ] Can spawn multiple agent instances
- [ ] Can delegate task to specific agents
- [ ] Can run skills in parallel across agents
- [ ] Results aggregated from all agents

---

## Implementation Priority

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 1 | State Persistence | Medium | High - enables reliability |
| 2 | Database Tools | Medium | Medium - expands capabilities |
| 3 | MCP Integration | High | High - massive tool expansion |
| 4 | Notifications | Low | Medium - usability |
| 5 | Multi-Agent | High | High - complex workflows |

---

## Quick Start - Choose One to Implement First

### Option A: State Persistence (Recommended First)
```python
from brain.state_manager import get_state_manager

sm = get_state_manager()
sm.save_snapshot("pre-feature-work")
# ... do work ...
sm.restore_snapshot("pre-feature-work")
```

### Option B: Database Tools
```python
from tools.db_client import DBClient

db = DBClient("postgresql://user:pass@localhost/mydb")
results = db.query("SELECT * FROM users LIMIT 10")
```

### Option C: MCP Integration
```python
from tools.mcp_client import MCPClient

mcp = MCPClient()
mcp.discover()  # Find running servers
tools = mcp.list_tools()  # Get tools from server
result = mcp.call_tool("filesystem_read", {"path": "/tmp/test.txt"})
```

**Which feature would you like to implement first?**