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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

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
      try {
        const data = await hermesChat(input.trim());
        if (data._error) {
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
