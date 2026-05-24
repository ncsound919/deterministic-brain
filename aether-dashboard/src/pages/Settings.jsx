import React, { useState, useEffect } from 'react';
import { soulGet, soulUpdate, integrationsStatus, settingsSaveKeys, llmStatus, autonomyStatus } from '../api';
import { Settings as SettingsIcon, Key, Shield, Save, Zap, Radio } from 'lucide-react';

export default function SettingsPage() {
  const [soul, setSoul] = useState(null);
  const [integrations, setIntegrations] = useState(null);
  const [llm, setLlm] = useState(null);
  const [autonomy, setAutonomy] = useState(null);
  const [keys, setKeys] = useState({ anthropic: '', openai: '', openrouter: '', deepseek: '', gemini: '' });
  const [saving, setSaving] = useState(false);
  const [editMission, setEditMission] = useState('');

  const refresh = async () => {
    const [s, i, l, a] = await Promise.all([soulGet(), integrationsStatus(), llmStatus(), autonomyStatus()]);
    if (!s._error) { setSoul(s); setEditMission(s.agenda?.mission || ''); }
    if (!i._error) setIntegrations(i);
    if (!l._error) setLlm(l);
    if (!a._error) setAutonomy(a);
  };
  useEffect(() => { refresh(); }, []);

  const handleSaveKeys = async () => {
    setSaving(true);
    const filtered = Object.fromEntries(Object.entries(keys).filter(([_, v]) => v.trim()));
    if (Object.keys(filtered).length) await settingsSaveKeys(filtered);
    setSaving(false);
    refresh();
  };

  const handleSaveMission = async () => {
    await soulUpdate({ agenda: { mission: editMission } });
    refresh();
  };

  const inputStyle = { background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.5rem 0.8rem', color: 'var(--text)', fontSize: '0.78rem', width: '100%' };
  const btnStyle = { background: 'linear-gradient(135deg, var(--primary), #0090CC)', border: 'none', borderRadius: 8, padding: '0.5rem 1.2rem', color: '#fff', fontWeight: 700, cursor: 'pointer' };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>
      {/* Soul Identity */}
      <div className="glass panel">
        <div className="panel__header"><Shield size={14} color="var(--accent)" /><span className="panel__title">Soul Identity</span></div>
        <div className="panel__body">
          {soul ? (
            <div style={{ fontSize: '0.78rem' }}>
              <div style={{ marginBottom: 12 }}><span className="label">Name</span><div style={{ fontWeight: 700, fontSize: '1rem' }}>{soul.identity?.name || '—'}</div></div>
              <div style={{ marginBottom: 12 }}><span className="label">Role</span><div>{soul.identity?.role || '—'}</div></div>
              <div style={{ marginBottom: 8 }}><span className="label">Mission</span></div>
              <textarea value={editMission} onChange={e => setEditMission(e.target.value)}
                style={{ ...inputStyle, minHeight: 80, resize: 'vertical', marginBottom: 8 }} />
              <button onClick={handleSaveMission} style={btnStyle}><Save size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />Save Mission</button>
              <div style={{ marginTop: 16 }}><span className="label">Goals</span>
                <ul style={{ paddingLeft: 16, color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                  {(soul.agenda?.goals || []).map((g, i) => <li key={i}>{g}</li>)}
                </ul>
              </div>
            </div>
          ) : <div className="label">Loading soul…</div>}
        </div>
      </div>

      {/* API Keys */}
      <div className="glass panel">
        <div className="panel__header"><Key size={14} color="var(--warning)" /><span className="panel__title">API Keys</span></div>
        <div className="panel__body">
          {['anthropic','openai','openrouter','deepseek','gemini'].map(k => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div className="label" style={{ marginBottom: 4 }}>{k.toUpperCase()}</div>
              <input type="password" value={keys[k]} onChange={e => setKeys(p => ({ ...p, [k]: e.target.value }))}
                placeholder={`Enter ${k} key…`} style={inputStyle} />
            </div>
          ))}
          <button onClick={handleSaveKeys} disabled={saving} style={{ ...btnStyle, marginTop: 8 }}>
            <Save size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />{saving ? 'Saving…' : 'Save Keys'}
          </button>
        </div>
      </div>

      {/* Integrations */}
      <div className="glass panel">
        <div className="panel__header"><Zap size={14} color="var(--primary)" /><span className="panel__title">Integrations Status</span></div>
        <div className="panel__body">
          {integrations?.apis ? Object.entries(integrations.apis).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>{v.label || k}</span>
              <span className={`status-pill ${v.configured ? 'status-pill--online' : 'status-pill--offline'}`} style={{ fontSize: '0.55rem' }}>
                <Radio size={8} />{v.configured ? 'READY' : 'MISSING'}
              </span>
            </div>
          )) : <div className="label">Loading integrations…</div>}
        </div>
      </div>

      {/* LLM + Autonomy */}
      <div className="glass panel">
        <div className="panel__header"><SettingsIcon size={14} color="var(--secondary)" /><span className="panel__title">LLM & Autonomy</span></div>
        <div className="panel__body" style={{ fontSize: '0.75rem' }}>
          <div className="label" style={{ marginBottom: 6 }}>LLM Status</div>
          {llm ? (
            <div style={{ marginBottom: 16 }}>
              <div>Provider: <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{llm.provider || 'none'}</span></div>
              <div>Available: {llm.available ? '✅' : '❌'}</div>
              <div>Keys: {Object.entries(llm.has_keys || {}).map(([k, v]) => <span key={k} style={{ marginRight: 8 }}>{k}: {v ? '✅' : '—'}</span>)}</div>
            </div>
          ) : <div>Loading…</div>}
          <div className="label" style={{ marginBottom: 6 }}>Autonomy</div>
          {autonomy ? <pre className="mono" style={{ fontSize: '0.65rem', whiteSpace: 'pre-wrap', color: 'var(--text-muted)' }}>{JSON.stringify(autonomy, null, 2).slice(0, 1000)}</pre> : <div>Loading…</div>}
        </div>
      </div>
    </div>
  );
}
