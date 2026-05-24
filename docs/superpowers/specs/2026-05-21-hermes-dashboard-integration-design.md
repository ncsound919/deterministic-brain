# Hermes Dashboard Integration Design

**Date:** 2026-05-21
**Project:** deterministic-brain-main / aether-dashboard
**Status:** Draft — awaiting review

## 1. Objective

Integrate hermes-agent as the central orchestrator into the existing aether-dashboard. Add a Chat page and Models page. Wire up command-code, opencode, and the local Gemma-4 model as tool sources. All communication proxies through the brain's FastAPI server (port 8000).

## 2. Architecture

```
Browser (aether-dashboard) ──fetch/WebSocket──► Brain API (port 8000)
                                                    │
                                        ┌───────────┼───────────┐
                                        ▼           ▼           ▼
                                   Hermes API   command-code  opencode
                                   (port 9119)  (subprocess) (subprocess)
                                        │
                                        ▼
                                   Gemma-4 (localhost:8080)
```

- **Dashboard** talks only to port 8000 (brain server)
- **Brain server** proxies to hermes (port 9119) and manages subprocesses
- **Hermes** orchestrates between command-code, opencode, and the local model
- **Local model** runs via llama.cpp server at localhost:8080

## 3. Backend Changes (api/server.py)

### 3.1 Hermes Proxy Endpoints

New endpoints that forward requests to hermes's web API (port 9119):

```python
# Hermes proxy — all calls go through brain, not direct to hermes
HERMES_URL = os.getenv("HERMES_URL", "http://127.0.0.1:9119")

@app.post("/hermes/chat")
async def hermes_chat(req: ChatRequest):
    """Send a message to hermes for processing."""
    # Forward to hermes's chat/session endpoint
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{HERMES_URL}/api/chat", json={"text": req.text})
        return resp.json()

@app.get("/hermes/skills")
async def hermes_skills():
    """List skills from hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HERMES_URL}/api/skills")
        return resp.json()

@app.post("/hermes/skills/{skill_id}/toggle")
async def hermes_toggle_skill(skill_id: str):
    """Toggle a skill in hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{HERMES_URL}/api/skills/{skill_id}/toggle")
        return resp.json()

@app.get("/hermes/cron")
async def hermes_cron():
    """List cron jobs from hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HERMES_URL}/api/cron")
        return resp.json()

@app.post("/hermes/cron")
async def hermes_create_cron(body: Dict):
    """Create a cron job in hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{HERMES_URL}/api/cron", json=body)
        return resp.json()

@app.get("/hermes/sessions")
async def hermes_sessions():
    """List active sessions from hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HERMES_URL}/api/sessions")
        return resp.json()

@app.get("/hermes/sessions/{session_id}/messages")
async def hermes_session_messages(session_id: str):
    """Get messages from a hermes session."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HERMES_URL}/api/sessions/{session_id}/messages")
        return resp.json()

@app.get("/hermes/models")
async def hermes_models():
    """List available models from hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HERMES_URL}/api/models")
        return resp.json()

@app.post("/hermes/models/assign")
async def hermes_assign_model(body: Dict):
    """Assign a model in hermes."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{HERMES_URL}/api/models/assign", json=body)
        return resp.json()

@app.get("/hermes/status")
async def hermes_status():
    """Check if hermes is running."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HERMES_URL}/api/status", timeout=3)
            return {"connected": True, "status": resp.json()}
    except Exception:
        return {"connected": False, "status": None}
```

### 3.2 WebSocket Chat Endpoint

For streaming chat responses:

```python
from fastapi import WebSocket

@app.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    """WebSocket endpoint for streaming chat with hermes."""
    await ws.accept()
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            
            # Forward to hermes via WebSocket or SSE
            # Stream response chunks back to client
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{HERMES_URL}/api/chat/stream", 
                                         json={"text": data.get("text", "")}) as resp:
                    async for chunk in resp.aiter_text():
                        await ws.send_text(chunk)
    except WebSocketDisconnect:
        pass
```

### 3.3 Model Management Endpoints

```python
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8080")

@app.get("/models/local/status")
async def local_model_status():
    """Check if the local Gemma-4 model is running."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LOCAL_MODEL_URL}/v1/models", timeout=3)
            return {"connected": True, "models": resp.json()}
    except Exception:
        return {"connected": False, "models": []}

@app.post("/models/local/chat")
async def local_model_chat(req: ChatRequest):
    """Chat directly with the local Gemma-4 model."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{LOCAL_MODEL_URL}/v1/chat/completions", json={
            "model": "gemma-4",
            "messages": [{"role": "user", "content": req.text}],
            "stream": False,
        })
        return resp.json()

@app.post("/models/local/chat/stream")
async def local_model_chat_stream(req: ChatRequest):
    """Streaming chat with the local model (SSE)."""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{LOCAL_MODEL_URL}/v1/chat/completions", json={
                "model": "gemma-4",
                "messages": [{"role": "user", "content": req.text}],
                "stream": True,
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 3.4 Tool Registration Endpoints

```python
# Registered external tools
_REGISTERED_TOOLS = {}

@app.post("/tools/register")
async def register_tool(body: Dict):
    """Register a tool (command-code, opencode, etc.)."""
    name = body.get("name")
    tool_type = body.get("type")  # "subprocess" or "api"
    config = body.get("config", {})
    _REGISTERED_TOOLS[name] = {"type": tool_type, "config": config}
    return {"status": "ok", "registered": name, "tools": list(_REGISTERED_TOOLS.keys())}

@app.get("/tools")
async def list_tools():
    """List registered tools."""
    tools = []
    for name, info in _REGISTERED_TOOLS.items():
        tools.append({"name": name, "type": info["type"], "status": "registered"})
    return {"tools": tools}

@app.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, body: Dict):
    """Execute a registered tool."""
    if tool_name not in _REGISTERED_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not registered")
    
    tool = _REGISTERED_TOOLS[tool_name]
    if tool["type"] == "subprocess":
        import asyncio
        cmd = tool["config"].get("command", [])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=body.get("input", "").encode())
        return {
            "tool": tool_name,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": proc.returncode,
        }
    else:
        raise HTTPException(status_code=400, detail=f"Tool type '{tool['type']}' not supported")
```

### 3.5 Dependencies

Add `httpx` to requirements (already installed based on earlier check).

## 4. Frontend Changes

### 4.1 New Pages

#### Chat.jsx — Full Chat Interface
- ChatGPT-style message bubbles
- Real-time streaming via WebSocket (`/ws/chat`)
- Tool labels on responses (which tool handled it)
- Conversation history sidebar
- Quick actions (Build, Question, Status, Help)
- Uses `/hermes/chat` for non-streaming, `/ws/chat` for streaming

#### Models.jsx — Model Management
- Local Gemma-4 status card (connected/disconnected)
- Model info display (name, context size, parameters)
- Direct chat with local model (test panel)
- Model switching (if multiple models configured)
- Uses `/models/local/status`, `/models/local/chat`

### 4.2 App.jsx Changes

Add two new nav items:

```javascript
// In PAGES array:
{ id: 'chat', label: 'Chat', icon: MessageSquare, color: '#00FF9F', section: 'Operations' },
{ id: 'models', label: 'Models', icon: Cpu, color: '#A78BFA', section: 'Operations' },

// In PAGE_MAP:
chat: ChatPage,
models: ModelsPage,
```

### 4.3 api.js Additions

```javascript
// ─── Hermes ───────────────────────────────────────────────────────
export const hermesChat = (text) =>
  fetchJSON(`${BRAIN_API}/hermes/chat`, { method: 'POST', body: JSON.stringify({ text }) });
export const hermesSkills = () => fetchJSON(`${BRAIN_API}/hermes/skills`);
export const hermesToggleSkill = (id) =>
  fetchJSON(`${BRAIN_API}/hermes/skills/${id}/toggle`, { method: 'POST' });
export const hermesCron = () => fetchJSON(`${BRAIN_API}/hermes/cron`);
export const hermesCreateCron = (data) =>
  fetchJSON(`${BRAIN_API}/hermes/cron`, { method: 'POST', body: JSON.stringify(data) });
export const hermesSessions = () => fetchJSON(`${BRAIN_API}/hermes/sessions`);
export const hermesSessionMessages = (id) =>
  fetchJSON(`${BRAIN_API}/hermes/sessions/${id}/messages`);
export const hermesModels = () => fetchJSON(`${BRAIN_API}/hermes/models`);
export const hermesAssignModel = (data) =>
  fetchJSON(`${BRAIN_API}/hermes/models/assign`, { method: 'POST', body: JSON.stringify(data) });
export const hermesStatus = () => fetchJSON(`${BRAIN_API}/hermes/status`);

// ─── Local Model ──────────────────────────────────────────────────
export const localModelStatus = () => fetchJSON(`${BRAIN_API}/models/local/status`);
export const localModelChat = (text) =>
  fetchJSON(`${BRAIN_API}/models/local/chat`, { method: 'POST', body: JSON.stringify({ text }) });

// ─── Tools ────────────────────────────────────────────────────────
export const toolsRegister = (name, type, config) =>
  fetchJSON(`${BRAIN_API}/tools/register`, { method: 'POST', body: JSON.stringify({ name, type, config }) });
export const toolsList = () => fetchJSON(`${BRAIN_API}/tools`);
export const toolsExecute = (name, input) =>
  fetchJSON(`${BRAIN_API}/tools/${name}/execute`, { method: 'POST', body: JSON.stringify({ input }) });
```

### 4.4 WebSocket Client (new file: src/ws.js)

```javascript
export function createChatWebSocket(onMessage, onError) {
  const ws = new WebSocket('ws://localhost:8000/ws/chat');
  
  ws.onopen = () => console.log('[WS] Connected');
  ws.onmessage = (event) => onMessage(event.data);
  ws.onerror = (error) => onError(error);
  ws.onclose = () => console.log('[WS] Disconnected');
  
  return {
    send: (text) => ws.send(JSON.stringify({ text })),
    close: () => ws.close(),
  };
}
```

## 5. Configuration

### 5.1 Environment Variables (.env additions)

```
HERMES_URL=http://127.0.0.1:9119
LOCAL_MODEL_URL=http://127.0.0.1:8080
```

### 5.2 Startup Order

1. Start llama.cpp server: `llama-server --model <gemma-4.gguf> --host 127.0.0.1 --port 8080`
2. Start hermes: `hermes web --host 127.0.0.1 --port 9119`
3. Start brain: `python main.py --serve` (port 8000)
4. Open dashboard: `http://localhost:8000` → navigate to Chat page

### 5.3 Tool Registration (run once)

```bash
# Register command-code
curl -X POST http://localhost:8000/tools/register \
  -H "Content-Type: application/json" \
  -d '{"name":"command-code","type":"subprocess","config":{"command":["command-code","run"]}}'

# Register opencode
curl -X POST http://localhost:8000/tools/register \
  -H "Content-Type: application/json" \
  -d '{"name":"opencode","type":"subprocess","config":{"command":["opencode","run"]}}'
```

## 6. File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `api/server.py` | Modify | Add ~80 lines: hermes proxy, model, tool endpoints, WebSocket |
| `aether-dashboard/src/App.jsx` | Modify | Add Chat + Models to nav (4 lines) |
| `aether-dashboard/src/api.js` | Modify | Add ~25 lines: hermes, model, tool API functions |
| `aether-dashboard/src/pages/Chat.jsx` | **New** | Full chat interface (~200 lines) |
| `aether-dashboard/src/pages/Models.jsx` | **New** | Model management page (~150 lines) |
| `aether-dashboard/src/ws.js` | **New** | WebSocket client helper (~20 lines) |
| `.env` | Modify | Add HERMES_URL, LOCAL_MODEL_URL |

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| hermes not running | Dashboard shows "Hermes disconnected" banner, falls back to brain's existing chat |
| Local model not running | Models page shows status, offers "Start Model" button with instructions |
| WebSocket disconnects | Auto-reconnect with exponential backoff, fallback to polling |
| Subprocess hangs | Timeout of 60s on tool execution, kill on timeout |
| Port conflicts | Configurable via env vars, default to 8000/9119/8080 |

## 8. Future Enhancements (out of scope for this phase)

- Real-time event streaming from hermes to dashboard sidebar
- Tool output visualization (code blocks, file previews, terminal output)
- Multi-session management with tabbed conversations
- Voice input/output integration
- Mobile-responsive layout
