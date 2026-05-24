import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Shield, Zap, Brain, Cpu, TrendingUp, TrendingDown, RefreshCw, CheckCircle, XCircle, Loader2, Radio, Clock, Database, Heart, AlertTriangle, Terminal } from 'lucide-react';
import { healthCheck, llmStatus, autonomyStatus, integrationsStatus } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

export default function SystemsHealth() {
  const [health, setHealth] = useState(null);
  const [autonomy, setAutonomy] = useState(null);
  const [llm, setLlm] = useState(null);
  const [integrations, setIntegrations] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pageState, updatePageState] = usePageState('systems-health', {
    logs: [],
    activeTab: 'overview',
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [h, a, l, i] = await Promise.all([
        healthCheck(),
        autonomyStatus(),
        llmStatus(),
        integrationsStatus(),
      ]);
      if (!h._error) setHealth(h);
      if (!a._error) setAutonomy(a);
      if (!l._error) setLlm(l);
      if (!i._error) setIntegrations(i);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useAutoRefresh(refresh, 10000, true);

  const addLog = (msg, status = 'info') => {
    const entry = { ts: new Date().toLocaleTimeString(), msg, status };
    updatePageState({ logs: [entry, ...pageState.logs.slice(0, 49)] });
  };

  const handleAction = async (endpoint, label) => {
    addLog(`Triggering ${label}...`, 'running');
    try {
      const res = await fetch(`http://localhost:8000${endpoint}`, { method: 'POST' });
      const data = await res.json();
      addLog(`${label}: ${JSON.stringify(data).slice(0, 200)}`, data.status === 'ok' ? 'success' : 'failed');
    } catch (e) {
      addLog(`${label} failed: ${e.message}`, 'failed');
    }
  };

  const configuredApis = integrations?.apis ? Object.values(integrations.apis).filter(a => a.configured).length : 0;
  const totalApis = integrations?.apis ? Object.values(integrations.apis).length : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

      {/* Top Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr', gap: 'var(--gap-md)' }}>
        <MetricCard label="API Status" value={`${configuredApis}/${totalApis}`} icon={Zap} color="var(--primary)" />
        <MetricCard label="LLM Provider" value={llm?.provider || 'NONE'} icon={Cpu} color="var(--accent)" />
        <MetricCard label="Autonomy" value={autonomy?.status || 'CHECKING'} icon={Radio} color="var(--warning)" />
        <MetricCard label="Cache Size" value={health?.cache_size || 0} icon={Database} color="#A78BFA" />
        <MetricCard label="Version" value="v2.5.0" icon={Activity} color="var(--secondary)" />
      </div>

      {/* Overview Grid */}
      {pageState.activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--gap-md)' }}>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

            {/* Components Status */}
            <div className="glass panel">
              <div className="panel__header"><Activity size={14} color="var(--primary)" /><span className="panel__title">System Components</span></div>
              <div className="panel__body">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {(() => {
                    const kairosOk = autonomy?.kairos || false;
                    const apiCount = integrations?.apis ? Object.values(integrations.apis).filter(a => a.configured).length : 0;
                    const apiTotal = integrations?.apis ? Object.values(integrations.apis).length : 0;
                    return [
                      { name: 'Soul Identity', status: 'online', desc: '.soul.yaml loaded' },
                      { name: 'Learning Loop', status: 'online', desc: 'Bandit + Tracker + Evolver' },
                      { name: 'KAIROS Daemon', status: kairosOk ? 'online' : 'offline', desc: kairosOk ? 'Idle-time maintenance' : 'Daemon not running' },
                      { name: 'Swarm Worker', status: 'online', desc: 'Background task processing' },
                      { name: 'Scheduler', status: 'online', desc: 'Cron + interval tasks' },
                      { name: 'Knowledge Bank', status: health?.qdrant_ok ? 'online' : 'offline', desc: health?.qdrant_ok ? 'Qdrant + Neo4j + SQLite' : 'Vector store unavailable' },
                      { name: 'AutoDream', status: 'online', desc: 'Memory consolidation' },
                      { name: 'Policy Engine', status: 'online', desc: 'Guardrails active' },
                      { name: 'Content Engine', status: 'online', desc: 'Social + blog + media' },
                      { name: 'Browser Automation', status: 'online', desc: 'Playwright controller' },
                      { name: 'API Gateways', status: apiCount > 0 ? 'online' : 'offline', desc: apiTotal > 0 ? `${apiCount}/${apiTotal} configured` : 'No APIs configured' },
                      { name: 'LLM Provider', status: llm?.available ? 'online' : 'offline', desc: llm?.provider || 'None configured' },
                    ].map((comp, i) => (
                    <div key={i} className="glass" style={{ padding: '0.6rem', display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className={`status-dot ${comp.status === 'online' ? 'status-dot--online' : 'status-dot--offline'}`} style={{ width: 8, height: 8 }} />
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '0.7rem' }}>{comp.name}</div>
                        <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>{comp.desc}</div>
                      </div>
                    </div>
                    )); })()}
                </div>
              </div>
            </div>

            {/* Evolution Stats */}
            <div className="glass panel">
              <div className="panel__header"><Brain size={14} color="var(--accent)" /><span className="panel__title">Evolution & Learning</span></div>
              <div className="panel__body">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                  <div className="glass" style={{ padding: '1rem', textAlign: 'center' }}>
                    <div className="label" style={{ fontSize: '0.55rem' }}>DREAM CYCLES</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--primary)' }}>{autonomy?.dream_stats?.cycles || 0}</div>
                  </div>
                  <div className="glass" style={{ padding: '1rem', textAlign: 'center' }}>
                    <div className="label" style={{ fontSize: '0.55rem' }}>SKILLS EXPANDED</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--accent)' }}>{autonomy?.dream_stats?.total_skills_expanded || 0}</div>
                  </div>
                  <div className="glass" style={{ padding: '1rem', textAlign: 'center' }}>
                    <div className="label" style={{ fontSize: '0.55rem' }}>TASKS COMPLETED</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--warning)' }}>{autonomy?.dream_stats?.total_tasks_completed || 0}</div>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Right Side: Actions + Integrations */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
            
            {/* Quick Actions */}
            <div className="glass panel">
              <div className="panel__header"><Zap size={14} color="var(--accent)" /><span className="panel__title">Quick Actions</span></div>
              <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'Force Dream', endpoint: '/autonomy/dream', color: 'var(--primary)' },
                  { label: 'Run AutoDream', endpoint: '/autodream/run', color: 'var(--accent)' },
                  { label: 'Consolidate Knowledge', endpoint: '/knowledge/consolidate', color: 'var(--warning)' },
                  { label: 'Expand Skills', endpoint: '/skills/expand', color: '#FF00D4' },
                  { label: 'Generate Refs', endpoint: '/knowledge/generate-refs', color: '#A78BFA' },
                ].map((action, i) => (
                  <button key={i} onClick={() => handleAction(action.endpoint, action.label)}
                    style={{
                      width: '100%', padding: '0.7rem', background: `${action.color}10`, border: `1px solid ${action.color}`,
                      borderRadius: 8, color: '#fff', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    }}>
                    <Zap size={14} color={action.color} /> {action.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Integration Status */}
            <div className="glass panel" style={{ flex: 1 }}>
              <div className="panel__header"><Database size={14} color="var(--primary)" /><span className="panel__title">API Integrations</span></div>
              <div className="panel__body">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {integrations?.apis && Object.entries(integrations.apis).map(([key, val]) => (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.3rem 0', borderBottom: '1px solid var(--surface-border)' }}>
                      <span style={{ color: val.configured ? 'var(--accent)' : 'var(--text-muted)' }}>
                        {val.configured ? <CheckCircle size={12} /> : <XCircle size={12} />}
                      </span>
                      <span style={{ fontSize: '0.65rem', flex: 1 }}>{val.label}</span>
                      <span className="mono" style={{ fontSize: '0.55rem', color: val.configured ? 'var(--accent)' : 'var(--text-muted)' }}>
                        {val.configured ? 'CONNECTED' : 'NOT SET'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              </div>
            </div>

            {/* Action Log */}
            <div className="glass panel" style={{ flex: 1 }}>
              <div className="panel__header"><Terminal size={14} color="var(--text-muted)" /><span className="panel__title">Action Log</span></div>
              <div className="panel__body mono" style={{ flex: 1, overflowY: 'auto', fontSize: '0.55rem', maxHeight: 200 }}>
                {pageState.logs.length === 0 && <div style={{ opacity: 0.3, padding: '1rem', textAlign: 'center' }}>No actions yet</div>}
                {pageState.logs.map((entry, i) => (
                  <div key={i} style={{ padding: '0.3rem', borderBottom: '1px solid var(--surface-border)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>[{entry.ts}]</span>{' '}
                    <span style={{ color: entry.status === 'success' ? 'var(--accent)' : entry.status === 'failed' ? 'var(--secondary)' : 'var(--primary)' }}>{entry.status}</span>{' '}
                    {entry.msg.slice(0, 100)}
                  </div>
                  ))}
                </div>
            </div>

          </div>
      )}

    </div>
  );
}

function MetricCard({ label, value, icon: Icon, color }) {
  return (
    <div className="glass metric-card">
      <div className="metric-card__icon-wrap" style={{ background: `${color}15` }}>
        <Icon size={18} color={color} />
      </div>
      <div className="label">{label}</div>
      <div className="metric-card__value">{value}</div>
    </div>
  );
}
