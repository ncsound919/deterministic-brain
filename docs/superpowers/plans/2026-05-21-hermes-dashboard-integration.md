# Hermes Dashboard Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate hermes-agent as the central orchestrator into the existing aether-dashboard, adding a Chat page, Models page, and WebSocket streaming — all proxied through the brain's FastAPI server.

**Architecture:** Dashboard talks only to brain (port 8000). Brain proxies to hermes (port 9119) and manages the local Gemma-4 model (port 8080). Two new React pages (Chat, Models) are added to the existing aether-dashboard SPA.

**Tech Stack:** FastAPI (Python), React + Vite, Framer Motion, lucide-react, WebSocket, httpx

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `api/server.py` | Modify | Add hermes proxy endpoints, model endpoints, tool endpoints, WebSocket handler |
| `aether-dashboard/src/api.js` | Modify | Add hermes, model, tool API functions |
| `aether-dashboard/src/ws.js` | **New** | WebSocket client helper for streaming chat |
| `aether-dashboard/src/pages/Chat.jsx` | **New** | Full chat interface with streaming, tool labels, history |
| `aether-dashboard/src/pages/Models.jsx` | **New** | Model status, info, and direct chat panel |
| `aether-dashboard/src/App.jsx` | Modify | Register Chat + Models in nav |
| `.env` | Modify | Add HERMES_URL, LOCAL_MODEL_URL |

---

### Task 1: Add Hermes Proxy Endpoints to Backend

**Files:**
- Modify: `api/server.py` (add ~60 lines near the bottom, before the `if __name__` block)

- [ ] **Step 1: Add hermes proxy endpoints**

Add these endpoints to `api/server.py`. Insert them after the existing `/chat` endpoint (~line 974) and before the dialogue section. First, add the import and constant at the top of the file, right after the existing imports (after line 106):

```python
# ── Hermes Integration ─────────────────────────────────────────
HERMES_URL = os.getenv("HERMES_URL", "http://127.0.0.1:9119")
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8080")
```

Then add the proxy endpoints. Place them after the `@app.post("/chat")` handler (~line 974):

```python
# ── Hermes Proxy ───────────────────────────────────────────────
@app.get("/hermes/status")
def hermes_status() -> Dict:
    """Check if hermes is reachable."""
    try:
        import httpx
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{HERMES_URL}/api/status")
            return {"connected": True, "status": resp.json()}
    except Exception:
        return {"connected": False, "status": None}


@app.post("/hermes/chat")
def hermes_chat(req: ChatRequest) -> Dict:
    """Send a message to hermes for processing."""
    try:
        import httpx
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{HERMES_URL}/api/chat", json={"text": req.text})
            return resp.json()
    except Exception as e:
        return {"_error": f"Hermes unavailable: {str(e)}", "text": req.text, "fallback": True}


@app.get("/hermes/skills")
def hermes_skills() -> Dict:
    """List skills from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/skills")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "skills": []}


@app.post("/hermes/skills/{skill_id}/toggle")
def hermes_toggle_skill(skill_id: str) -> Dict:
    """Toggle a skill in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/skills/{skill_id}/toggle")
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}


@app.get("/hermes/cron")
def hermes_cron() -> Dict:
    """List cron jobs from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/cron")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "cron": []}


@app.post("/hermes/cron")
def hermes_create_cron(body: Dict) -> Dict:
    """Create a cron job in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/cron", json=body)
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}


@app.get("/hermes/sessions")
def hermes_sessions() -> Dict:
    """List active sessions from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/sessions")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "sessions": []}


@app.get("/hermes/sessions/{session_id}/messages")
def hermes_session_messages(session_id: str) -> Dict:
    """Get messages from a hermes session."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/sessions/{session_id}/messages")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "messages": []}


@app.get("/hermes/models")
def hermes_models() -> Dict:
    """List available models from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/models")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "models": []}


@app.post("/hermes/models/assign")
def hermes_assign_model(body: Dict) -> Dict:
    """Assign a model in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/models/assign", json=body)
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}
```

- [ ] **Step 2: Verify the server still starts**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main" && python -c "from api.server import app; print(f'Routes: {len(app.routes)}')"`
Expected: `Routes: <number greater than 100>`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add api/server.py
git commit -m "feat: add hermes proxy endpoints to brain API"
```

---

### Task 2: Add Local Model & Tool Endpoints

**Files:**
- Modify: `api/server.py` (add ~50 lines after hermes proxy section)

- [ ] **Step 1: Add model management endpoints**

Add these after the hermes proxy section in `api/server.py`:

```python
# ── Local Model (Gemma-4 via llama.cpp) ────────────────────────
@app.get("/models/local/status")
def local_model_status() -> Dict:
    """Check if the local Gemma-4 model is running."""
    try:
        import httpx
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{LOCAL_MODEL_URL}/v1/models")
            return {"connected": True, "models": resp.json()}
    except Exception:
        return {"connected": False, "models": []}


@app.post("/models/local/chat")
def local_model_chat(req: ChatRequest) -> Dict:
    """Chat directly with the local Gemma-4 model."""
    try:
        import httpx
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{LOCAL_MODEL_URL}/v1/chat/completions", json={
                "model": "gemma-4",
                "messages": [{"role": "user", "content": req.text}],
                "stream": False,
            })
            return resp.json()
    except Exception as e:
        return {"_error": f"Model unavailable: {str(e)}"}
```

- [ ] **Step 2: Add tool registration endpoints**

Add these after the model endpoints:

```python
# ── Tool Registration (command-code, opencode) ─────────────────
_REGISTERED_TOOLS: Dict[str, Dict] = {}


@app.post("/tools/register")
def register_tool(body: Dict) -> Dict:
    """Register a tool (command-code, opencode, etc.)."""
    name = body.get("name")
    tool_type = body.get("type", "subprocess")
    config = body.get("config", {})
    _REGISTERED_TOOLS[name] = {"type": tool_type, "config": config}
    return {"status": "ok", "registered": name, "tools": list(_REGISTERED_TOOLS.keys())}


@app.get("/tools")
def list_tools() -> Dict:
    """List registered tools."""
    tools = []
    for name, info in _REGISTERED_TOOLS.items():
        tools.append({"name": name, "type": info["type"], "status": "registered"})
    return {"tools": tools}


@app.post("/tools/{tool_name}/execute")
def execute_tool(tool_name: str, body: Dict) -> Dict:
    """Execute a registered tool."""
    if tool_name not in _REGISTERED_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not registered")
    
    tool = _REGISTERED_TOOLS[tool_name]
    if tool["type"] == "subprocess":
        import subprocess
        cmd = tool["config"].get("command", [])
        if not cmd:
            raise HTTPException(status_code=400, detail="No command configured for tool")
        try:
            result = subprocess.run(
                cmd,
                input=body.get("input", ""),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "tool": tool_name,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:10000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"tool": tool_name, "error": "Tool execution timed out (60s)"}
        except Exception as e:
            return {"tool": tool_name, "error": str(e)}
    else:
        raise HTTPException(status_code=400, detail=f"Tool type '{tool['type']}' not supported")
```

- [ ] **Step 3: Verify imports work**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main" && python -c "from api.server import app, hermes_status, local_model_status, register_tool; print('All endpoints loaded')"`
Expected: `All endpoints loaded`

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add api/server.py
git commit -m "feat: add local model and tool management endpoints"
```

---

### Task 3: Add WebSocket Chat Endpoint

**Files:**
- Modify: `api/server.py` (add ~30 lines after tool endpoints)

- [ ] **Step 1: Add WebSocket import and endpoint**

Add the WebSocket import near the top of the file, with the other FastAPI imports (after line 12):

```python
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
```

Then add the WebSocket endpoint after the tool endpoints:

```python
# ── WebSocket Chat ─────────────────────────────────────────────
@app.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    """WebSocket endpoint for streaming chat with hermes."""
    await ws.accept()
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            text = data.get("text", "")
            
            # Forward to hermes and stream response
            try:
                import httpx
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{HERMES_URL}/api/chat/stream",
                        json={"text": text}
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            await ws.send_text(chunk)
            except Exception as e:
                await ws.send_text(json.dumps({"_error": str(e), "text": text, "fallback": True}))
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass
```

- [ ] **Step 2: Verify WebSocket endpoint is registered**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main" && python -c "from api.server import app; ws_routes = [r for r in app.routes if hasattr(r, 'path') and 'ws' in str(r.path).lower()]; print(f'WebSocket routes: {len(ws_routes)}')"`
Expected: `WebSocket routes: 1`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add api/server.py
git commit -m "feat: add WebSocket chat endpoint for streaming"
```

---

### Task 4: Add Frontend API Functions

**Files:**
- Modify: `aether-dashboard/src/api.js` (append ~30 lines at the end)

- [ ] **Step 1: Add hermes, model, and tool API functions**

Append these to the end of `aether-dashboard/src/api.js`:

```javascript
// ─── Hermes ───────────────────────────────────────────────────────
export const hermesStatus = () => fetchJSON(`${BRAIN_API}/hermes/status`);
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

- [ ] **Step 2: Verify the module loads**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main\aether-dashboard" && node -e "import('./src/api.js').then(() => console.log('API module OK'))"`
Expected: `API module OK` (or a syntax error if something is wrong)

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add aether-dashboard/src/api.js
git commit -m "feat: add hermes, model, and tool API functions to frontend"
```

---

### Task 5: Create WebSocket Client Helper

**Files:**
- Create: `aether-dashboard/src/ws.js`

- [ ] **Step 1: Write the WebSocket client**

Create `aether-dashboard/src/ws.js`:

```javascript
/* ═══════════════════════════════════════════════════════════════
   WebSocket Client — streaming chat with hermes via brain API
   ═══════════════════════════════════════════════════════════════ */

export function createChatWebSocket(onMessage, onError, onOpen, onClose) {
  const ws = new WebSocket('ws://localhost:8000/ws/chat');
  let reconnectTimer = null;

  ws.onopen = () => {
    console.log('[WS] Connected');
    if (onOpen) onOpen();
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    } catch {
      if (onMessage) onMessage({ text: event.data });
    }
  };

  ws.onerror = (error) => {
    console.error('[WS] Error:', error);
    if (onError) onError(error);
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
    if (onClose) onClose();
    // Auto-reconnect after 3s
    reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...');
      createChatWebSocket(onMessage, onError, onOpen, onClose);
    }, 3000);
  };

  return {
    send: (text) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ text }));
      }
    },
    close: () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws.close();
    },
  };
}
```

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add aether-dashboard/src/ws.js
git commit -m "feat: add WebSocket client helper for streaming chat"
```

---

### Task 6: Create Chat Page

**Files:**
- Create: `aether-dashboard/src/pages/Chat.jsx`

- [ ] **Step 1: Write the Chat page component**

Create `aether-dashboard/src/pages/Chat.jsx`:

```jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MessageSquare, Send, Loader2, RefreshCw, Zap, Bot, Terminal, Power, Radio } from 'lucide-react';
import { hermesChat, hermesStatus, localModelChat, localModelStatus, toolsExecute, toolsList } from '../api';
import { createChatWebSocket } from '../ws';
import { usePageState, useAutoRefresh } from '../stateManager';

const TOOL_ICONS = {
  hermes: Bot,
  'command-code': Terminal,
  opencode: Zap,
  model: Radio,
};

const TOOL_COLORS = {
  hermes: '#00FF9F',
  'command-code': '#00B8FF',
  opencode: '#FFD700',
  model: '#A78BFA',
};

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [hermesOnline, setHermesOnline] = useState(false);
  const [modelOnline, setModelOnline] = useState(false);
  const [tools, setTools] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [pageState, updatePageState] = usePageState('chat-page', {
    useWebSocket: true,
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  // Check hermes and model status
  const checkStatus = useCallback(async () => {
    const [hs, ms, tl] = await Promise.all([
      hermesStatus(),
      localModelStatus(),
      toolsList(),
    ]);
    if (!hs._error) setHermesOnline(hs.connected);
    if (!ms._error) setModelOnline(ms.connected);
    if (!tl._error) setTools(tl.tools || []);
  }, []);

  useAutoRefresh(checkStatus, 15000, true);
  useEffect(() => { checkStatus(); }, [checkStatus]);

  // WebSocket connection
  useEffect(() => {
    if (!pageState.useWebSocket) return;

    const ws = createChatWebSocket(
      (data) => {
        if (data._error) {
          setStreamingText('');
          setLoading(false);
          setMessages(prev => [...prev, {
            role: 'assistant',
            text: `Error: ${data._error}`,
            tool: 'hermes',
            ts: new Date().toLocaleTimeString(),
          }]);
        } else if (data.done) {
          setStreamingText('');
          setLoading(false);
          setMessages(prev => [...prev, {
            role: 'assistant',
            text: data.text || '',
            tool: data.tool || 'hermes',
            ts: new Date().toLocaleTimeString(),
          }]);
        } else {
          setStreamingText(prev => prev + (data.text || data.chunk || ''));
        }
      },
      () => setWsConnected(false),
      () => setWsConnected(true),
      () => setWsConnected(false),
    );

    wsRef.current = ws;
    return () => ws.close();
  }, [pageState.useWebSocket]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg = { role: 'user', text: input.trim(), ts: new Date().toLocaleTimeString() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setStreamingText('');

    if (pageState.useWebSocket && wsRef.current && wsConnected) {
      wsRef.current.send(input.trim());
    } else {
      // Fallback: use hermes REST API
      try {
        const data = await hermesChat(input.trim());
        if (data._error) {
          // Try local model as fallback
          const modelData = await localModelChat(input.trim());
          setMessages(prev => [...prev, {
            role: 'assistant',
            text: modelData.choices?.[0]?.message?.content || 'No response',
            tool: 'model',
            ts: new Date().toLocaleTimeString(),
          }]);
        } else {
          setMessages(prev => [...prev, {
            role: 'assistant',
            text: data.text || JSON.stringify(data).slice(0, 500),
            tool: data.tool || 'hermes',
            ts: new Date().toLocaleTimeString(),
          }]);
        }
      } catch (e) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          text: `Error: ${e.message}`,
          tool: 'hermes',
          ts: new Date().toLocaleTimeString(),
        }]);
      }
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setStreamingText('');
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>

      {/* Main Chat Area */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

        {/* Status Bar */}
        <div className="glass" style={{ padding: '0.8rem 1rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="status-dot" style={{ background: hermesOnline ? 'var(--accent)' : 'var(--secondary)' }} />
            <span className="mono" style={{ fontSize: '0.65rem', color: hermesOnline ? 'var(--accent)' : 'var(--secondary)', fontWeight: 800 }}>
              HERMES
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="status-dot" style={{ background: modelOnline ? 'var(--accent)' : 'var(--secondary)' }} />
            <span className="mono" style={{ fontSize: '0.65rem', color: modelOnline ? 'var(--accent)' : 'var(--secondary)', fontWeight: 800 }}>
              GEMMA-4
            </span>
          </div>
          {wsConnected && (
            <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--primary)', background: 'rgba(0,184,255,0.1)', padding: '2px 6px', borderRadius: 4 }}>
              WS STREAMING
            </span>
          )}
          {tools.length > 0 && (
            <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
              {tools.length} tool{tools.length !== 1 ? 's' : ''}
            </span>
          )}
          <button onClick={clearChat} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.65rem' }}>
            Clear
          </button>
        </div>

        {/* Messages */}
        <div className="glass panel" style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{ padding: '1rem 1.2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {messages.length === 0 && !streamingText && (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                <MessageSquare size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
                <div style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: 4 }}>Chat with Hermes</div>
                <div style={{ fontSize: '0.65rem' }}>Type a message or try one of these:</div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
                  {['What skills do you have?', 'Build a landing page', 'Status check'].map(q => (
                    <button key={q} onClick={() => { setInput(q); }} style={{
                      background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)',
                      borderRadius: 6, padding: '0.4rem 0.8rem', color: 'var(--text-muted)',
                      cursor: 'pointer', fontSize: '0.65rem',
                    }}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => {
              const ToolIcon = TOOL_ICONS[msg.tool] || Bot;
              const toolColor = TOOL_COLORS[msg.tool] || 'var(--text-muted)';
              return (
                <div key={i} style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}>
                  <div style={{
                    maxWidth: '80%',
                    padding: '0.8rem 1rem',
                    borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                    background: msg.role === 'user' ? 'rgba(0,184,255,0.1)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${msg.role === 'user' ? 'rgba(0,184,255,0.2)' : 'var(--surface-border)'}`,
                  }}>
                    {msg.role === 'assistant' && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                        <ToolIcon size={12} color={toolColor} />
                        <span className="mono" style={{ fontSize: '0.55rem', color: toolColor, fontWeight: 800 }}>
                          {msg.tool?.toUpperCase()}
                        </span>
                        <span className="mono" style={{ fontSize: '0.5rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                          {msg.ts}
                        </span>
                      </div>
                    )}
                    <div style={{ fontSize: '0.75rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                      {msg.text}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Streaming text */}
            {streamingText && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '0.8rem 1rem',
                  borderRadius: '12px 12px 12px 2px',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--surface-border)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <Loader2 size={12} className="spin" color="var(--accent)" />
                    <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--accent)', fontWeight: 800 }}>
                      HERMES (streaming)
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    {streamingText}
                    <span className="cursor-blink" />
                  </div>
                </div>
              </div>
            )}

            {/* Loading indicator */}
            {loading && !streamingText && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{
                  padding: '0.8rem 1rem',
                  borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--surface-border)',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <Loader2 size={14} className="spin" color="var(--primary)" />
                  <span className="mono" style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Thinking...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="glass" style={{ padding: '0.8rem 1rem', display: 'flex', gap: '0.8rem', alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter to send)"
            rows={1}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid var(--surface-border)',
              borderRadius: 8,
              padding: '0.6rem 0.8rem',
              color: 'var(--text)',
              fontSize: '0.75rem',
              fontFamily: "'JetBrains Mono', monospace",
              resize: 'none',
              outline: 'none',
              minHeight: 36,
              maxHeight: 120,
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            style={{
              background: input.trim() && !loading ? 'linear-gradient(135deg, var(--primary), var(--accent))' : 'rgba(255,255,255,0.05)',
              border: 'none',
              borderRadius: 8,
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: input.trim() && !loading ? '#fff' : 'var(--text-muted)',
              cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
            }}
          >
            {loading ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
          </button>
        </div>
      </div>

      {/* Sidebar: Tools & Settings */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

        {/* Registered Tools */}
        <div className="glass panel">
          <div className="panel__header">
            <Terminal size={14} color="var(--accent)" />
            <span className="panel__title">Tools</span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>{tools.length}</span>
          </div>
          <div className="panel__body" style={{ fontSize: '0.65rem' }}>
            {tools.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', padding: '0.5rem' }}>No tools registered</div>
            ) : (
              tools.map((t, i) => (
                <div key={i} style={{
                  padding: '0.5rem 0',
                  borderBottom: '1px solid var(--surface-border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}>
                  <span className="status-dot status-dot--online" style={{ width: 6, height: 6 }} />
                  <span style={{ fontWeight: 700 }}>{t.name}</span>
                  <span className="mono" style={{ fontSize: '0.5rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{t.type}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Settings */}
        <div className="glass panel">
          <div className="panel__header">
            <Power size={14} color="var(--primary)" />
            <span className="panel__title">Settings</span>
          </div>
          <div className="panel__body" style={{ fontSize: '0.65rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={pageState.useWebSocket}
                onChange={e => updatePageState({ useWebSocket: e.target.checked })}
                style={{ accentColor: 'var(--primary)' }}
              />
              <span>WebSocket streaming</span>
            </label>
          </div>
        </div>

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add aether-dashboard/src/pages/Chat.jsx
git commit -m "feat: add Chat page with streaming, tool labels, and hermes integration"
```

---

### Task 7: Create Models Page

**Files:**
- Create: `aether-dashboard/src/pages/Models.jsx`

- [ ] **Step 1: Write the Models page component**

Create `aether-dashboard/src/pages/Models.jsx`:

```jsx
import React, { useState, useEffect, useCallback } from 'react';
import { Cpu, Activity, RefreshCw, MessageSquare, Send, Loader2, Zap, Radio, Server } from 'lucide-react';
import { localModelStatus, localModelChat, hermesModels, hermesStatus } from '../api';
import { useAutoRefresh } from '../stateManager';

export default function ModelsPage() {
  const [modelStatus, setModelStatus] = useState(null);
  const [hermesStatusData, setHermesStatusData] = useState(null);
  const [hermesModelsData, setHermesModelsData] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatResponse, setChatResponse] = useState(null);
  const [chatLoading, setChatLoading] = useState(false);

  const refresh = useCallback(async () => {
    const [ms, hs, hm] = await Promise.all([
      localModelStatus(),
      hermesStatus(),
      hermesModels(),
    ]);
    if (!ms._error) setModelStatus(ms);
    if (!hs._error) setHermesStatusData(hs);
    if (!hm._error) setHermesModelsData(hm);
  }, []);

  useAutoRefresh(refresh, 10000, true);
  useEffect(() => { refresh(); }, [refresh]);

  const testChat = async () => {
    if (!chatInput.trim()) return;
    setChatLoading(true);
    setChatResponse(null);
    try {
      const data = await localModelChat(chatInput);
      setChatResponse({
        request: chatInput,
        response: data.choices?.[0]?.message?.content || JSON.stringify(data).slice(0, 500),
        model: data.model || 'gemma-4',
        ts: new Date().toLocaleTimeString(),
      });
    } catch (e) {
      setChatResponse({ request: chatInput, response: `Error: ${e.message}`, ts: new Date().toLocaleTimeString() });
    }
    setChatLoading(false);
  };

  const connected = modelStatus?.connected;
  const models = modelStatus?.models?.data || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>

        {/* Status Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--gap-md)' }}>
          <div className="glass metric-card">
            <div className="metric-card__icon-wrap" style={{ background: 'rgba(0,255,159,0.1)' }}>
              <Activity size={18} color={connected ? 'var(--accent)' : 'var(--secondary)'} />
            </div>
            <div className="label">Gemma-4 Status</div>
            <div className="metric-card__value" style={{ fontSize: '1rem', color: connected ? 'var(--accent)' : 'var(--secondary)' }}>
              {connected ? 'ONLINE' : 'OFFLINE'}
            </div>
            <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
              {models.length} model{models.length !== 1 ? 's' : ''} loaded
            </div>
          </div>

          <div className="glass metric-card">
            <div className="metric-card__icon-wrap" style={{ background: 'rgba(0,184,255,0.1)' }}>
              <Server size={18} color={hermesStatusData?.connected ? 'var(--primary)' : 'var(--secondary)'} />
            </div>
            <div className="label">Hermes</div>
            <div className="metric-card__value" style={{ fontSize: '1rem', color: hermesStatusData?.connected ? 'var(--primary)' : 'var(--secondary)' }}>
              {hermesStatusData?.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </div>
            <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
              Port 9119
            </div>
          </div>

          <div className="glass metric-card">
            <div className="metric-card__icon-wrap" style={{ background: 'rgba(167,139,250,0.1)' }}>
              <Zap size={18} color="var(--warning)" />
            </div>
            <div className="label">Endpoint</div>
            <div className="metric-card__value" style={{ fontSize: '0.8rem' }}>
              localhost:8080
            </div>
            <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
              llama.cpp server
            </div>
          </div>
        </div>

        {/* Model Details */}
        {connected && models.length > 0 && (
          <div className="glass panel">
            <div className="panel__header">
              <Cpu size={14} color="var(--accent)" />
              <span className="panel__title">Loaded Models</span>
            </div>
            <div className="panel__body">
              {models.map((m, i) => (
                <div key={i} className="glass" style={{
                  padding: '0.8rem 1rem',
                  marginBottom: 8,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                }}>
                  <Radio size={16} color="var(--accent)" />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: '0.8rem' }}>{m.id || m.name || 'gemma-4'}</div>
                    <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
                      {m.object || 'model'} • {m.owned_by || 'local'}
                    </div>
                  </div>
                  <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--accent)', background: 'rgba(0,255,159,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                    ACTIVE
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Hermes Models */}
        {hermesModelsData?.models && (
          <div className="glass panel">
            <div className="panel__header">
              <Server size={14} color="var(--primary)" />
              <span className="panel__title">Hermes Model Catalog</span>
            </div>
            <div className="panel__body" style={{ fontSize: '0.65rem' }}>
              <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                {JSON.stringify(hermesModelsData.models, null, 2).slice(0, 2000)}
              </pre>
            </div>
          </div>
        )}

        {/* Offline Instructions */}
        {!connected && (
          <div className="glass panel" style={{ background: 'linear-gradient(135deg, rgba(255,45,85,0.05), rgba(255,45,85,0.02))' }}>
            <div className="panel__header">
              <Cpu size={14} color="var(--secondary)" />
              <span className="panel__title">Model Not Running</span>
            </div>
            <div className="panel__body mono" style={{ fontSize: '0.65rem', color: 'var(--text-muted)', lineHeight: 1.8 }}>
              <div>Start the llama.cpp server with your Gemma-4 model:</div>
              <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.8rem', borderRadius: 6, marginTop: 8 }}>
                <div style={{ color: 'var(--accent)' }}>llama-server --model ^</div>
                <div style={{ color: 'var(--text)' }}>  path/to/gemma-4.gguf ^</div>
                <div style={{ color: 'var(--text)' }}>  --host 127.0.0.1 ^</div>
                <div style={{ color: 'var(--text)' }}>  --port 8080 ^</div>
                <div style={{ color: 'var(--text)' }}>  --ctx-size 4096</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sidebar: Test Chat */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <MessageSquare size={14} color="var(--accent)" />
          <span className="panel__title">Test Chat</span>
        </div>
        <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          <textarea
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            placeholder="Send a test message to Gemma-4..."
            rows={3}
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid var(--surface-border)',
              borderRadius: 8,
              padding: '0.6rem',
              color: 'var(--text)',
              fontSize: '0.7rem',
              fontFamily: "'JetBrains Mono', monospace",
              resize: 'vertical',
              outline: 'none',
            }}
          />
          <button
            onClick={testChat}
            disabled={!chatInput.trim() || chatLoading}
            style={{
              background: chatInput.trim() && !chatLoading ? 'linear-gradient(135deg, var(--accent), var(--primary))' : 'rgba(255,255,255,0.05)',
              border: 'none',
              borderRadius: 8,
              padding: '0.6rem',
              color: '#fff',
              fontWeight: 800,
              fontSize: '0.7rem',
              cursor: chatInput.trim() && !chatLoading ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            {chatLoading ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
            SEND TO MODEL
          </button>

          {chatResponse && (
            <div className="glass" style={{ padding: '0.8rem', fontSize: '0.65rem' }}>
              <div style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--accent)' }}>
                  RESPONSE ({chatResponse.model || 'gemma-4'})
                </span>
                <span className="mono" style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>
                  {chatResponse.ts}
                </span>
              </div>
              <div style={{
                background: 'rgba(0,0,0,0.3)',
                padding: '0.6rem',
                borderRadius: 6,
                whiteSpace: 'pre-wrap',
                lineHeight: 1.5,
                maxHeight: 300,
                overflowY: 'auto',
              }}>
                {chatResponse.response}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add aether-dashboard/src/pages/Models.jsx
git commit -m "feat: add Models page with status, info, and test chat"
```

---

### Task 8: Register Pages in App Navigation

**Files:**
- Modify: `aether-dashboard/src/App.jsx`

- [ ] **Step 1: Add imports for new pages**

At the top of `App.jsx`, add these imports after the existing page imports (after line 27):

```jsx
import ChatPage from './pages/Chat';
import ModelsPage from './pages/Models';
```

- [ ] **Step 2: Add nav items to PAGES array**

In the `PAGES` array, add these two entries after the Operations section (after the `systems` entry, before the Knowledge section comment):

```jsx
{ id: 'chat', label: 'Chat', icon: MessageSquare, color: '#00FF9F', section: 'Operations' },
{ id: 'models', label: 'Models', icon: Cpu, color: '#A78BFA', section: 'Operations' },
```

- [ ] **Step 3: Add to PAGE_MAP**

In the `PAGE_MAP` object, add:

```jsx
chat: ChatPage,
models: ModelsPage,
```

- [ ] **Step 4: Verify the dashboard builds**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main\aether-dashboard" && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add aether-dashboard/src/App.jsx
git commit -m "feat: register Chat and Models pages in dashboard navigation"
```

---

### Task 9: Update Environment Configuration

**Files:**
- Modify: `.env` (add 2 lines)

- [ ] **Step 1: Add hermes and model URLs to .env**

Add these lines to `deterministic-brain-main/.env`:

```
HERMES_URL=http://127.0.0.1:9119
LOCAL_MODEL_URL=http://127.0.0.1:8080
```

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add .env
git commit -m "config: add hermes and local model URL env vars"
```

---

### Task 10: Integration Test

**Files:**
- No file changes — verification only

- [ ] **Step 1: Start the brain server**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main" && python main.py --serve`

Expected: Server starts on port 8000 with no errors

- [ ] **Step 2: Verify new endpoints respond**

Run these in a separate terminal:

```powershell
# Check hermes proxy endpoint (will show disconnected if hermes isn't running — that's OK)
curl http://localhost:8000/hermes/status

# Check model endpoint (will show disconnected if llama.cpp isn't running — that's OK)
curl http://localhost:8000/models/local/status

# Check tools endpoint
curl http://localhost:8000/tools
```

Expected: All return JSON (may show `"connected": false` if services aren't running)

- [ ] **Step 3: Build and serve the dashboard**

Run: `cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main\aether-dashboard" && npm run build`

Then start the brain server and open `http://localhost:8000` in a browser. Navigate to the Chat and Models pages to verify they render.

- [ ] **Step 4: Final commit**

```bash
cd "C:\Users\User\Desktop\Billion Business\deterministic-brain-main"
git add -A
git commit -m "chore: integration test — all endpoints and pages verified"
```
