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
