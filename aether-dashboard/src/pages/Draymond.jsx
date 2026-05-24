import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Radio, Shield, Cpu, Activity, Zap, CheckCircle, AlertCircle, Loader2, Search, ArrowRight } from 'lucide-react';
import { systemsRegistry, systemsHealth, dashboardFeed } from '../api';

export default function Draymond() {
  const [agents, setAgents] = useState([]);
  const [health, setHealth] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [initLoading, setInitLoading] = useState(null);
  const [initResult, setInitResult] = useState({});

  const refresh = async () => {
    try {
      const [r, h, fd] = await Promise.all([systemsRegistry(), systemsHealth(), dashboardFeed()]);
      if (!r._error) setAgents(r.agents);
      if (!h._error) setHealth(h);
      if (!fd._error) setEvents(fd.events || []);
    } finally {
      setLoading(false);
    }
  };

  const handleInitializeSession = async (agentId) => {
    setInitLoading(agentId);
    try {
      const res = await fetch(`http://localhost:8000/task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: `Initialize session for agent: ${agentId}` })
      });
      const data = await res.json();
      setInitResult(prev => ({ ...prev, [agentId]: data }));
      await refresh();
    } catch (err) {
      setInitResult(prev => ({ ...prev, [agentId]: { error: err.message } }));
    } finally {
      setInitLoading(null);
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 'var(--gap-lg)', height: 'calc(100vh - 180px)' }}>
      
      {/* ─── Flagship Registry ────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-lg)' }}>
        <div className="glass panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <Shield size={14} color="var(--primary)" />
            <span className="panel__title">Flagship Agentic Registry</span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', opacity: 0.5 }}>STRATEGIC_ASSETS_LIVE</span>
          </div>
          
          <div className="panel__body" style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {agents.map(agent => (
              <div key={agent.id} className="glass" style={{ padding: '1.2rem', position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: 0, right: 0, width: 40, height: 40, background: agent.status === 'online' ? 'rgba(0,255,159,0.05)' : 'rgba(255,255,255,0.02)', borderRadius: '0 0 0 20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {agent.status === 'online' ? <Zap size={14} color="var(--accent)" /> : <Activity size={14} color="var(--text-muted)" />}
                </div>
                
                <div className="mono" style={{ fontSize: '0.6rem', color: 'var(--primary)', textTransform: 'uppercase', marginBottom: 8 }}>{agent.sector}</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 900, marginBottom: 4 }}>{agent.name}</div>
                <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>{agent.role}</div>
                
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: '1rem' }}>
                  {agent.capabilities.map(cap => (
                    <span key={cap} className="mono" style={{ fontSize: '0.55rem', padding: '0.2rem 0.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: 4, color: 'var(--text-muted)' }}>{cap}</span>
                  ))}
                </div>
                
                <p style={{ fontSize: '0.75rem', color: 'var(--text)', opacity: 0.8, lineHeight: 1.5 }}>{agent.description}</p>
                
                <button 
                  className="glass" 
                  onClick={() => handleInitializeSession(agent.id)}
                  disabled={initLoading === agent.id}
                  style={{ marginTop: '1.5rem', width: '100%', padding: '0.6rem', border: '1px solid rgba(255,255,255,0.05)', background: 'none', color: 'var(--text)', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
                >
                  {initLoading === agent.id ? <Loader2 size={12} className="spin" /> : <>INITIALIZE SESSION <ArrowRight size={12} /></>}
                </button>
                {initResult[agent.id] && (
                  <div className="mono" style={{ marginTop: 8, fontSize: '0.55rem', color: initResult[agent.id].error ? 'var(--secondary)' : 'var(--accent)', wordBreak: 'break-all' }}>
                    {initResult[agent.id].status || initResult[agent.id].error || 'OK'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* System Performance (Harness Integration) */}
        <div className="glass panel" style={{ height: 200 }}>
          <div className="panel__header">
            <Activity size={14} color="var(--accent)" />
            <span className="panel__title">Draymond Performance Harness</span>
          </div>
          <div className="panel__body" style={{ padding: '1rem', display: 'flex', gap: '2rem' }}>
             <div style={{ flex: 1 }}>
                <div className="label">System Health Score</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: 'var(--accent)' }}>{health?.benchmarks?.health_score || 0}<span style={{ fontSize: '1rem', opacity: 0.5 }}>/100</span></div>
                <div className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>LAST BENCHMARK: {health?.benchmarks?.report_generated ? new Date(health.benchmarks.report_generated).toLocaleTimeString() : 'NEVER'}</div>
             </div>
             <div style={{ flex: 2, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="glass" style={{ padding: '0.8rem' }}>
                   <div className="label" style={{ fontSize: '0.55rem' }}>CPU Utilization</div>
                   <div className="mono" style={{ fontSize: '1rem', fontWeight: 700 }}>{health?.benchmarks?.performance?.cpu_percent || 0}%</div>
                </div>
                <div className="glass" style={{ padding: '0.8rem' }}>
                   <div className="label" style={{ fontSize: '0.55rem' }}>Memory Pressure</div>
                   <div className="mono" style={{ fontSize: '1rem', fontWeight: 700 }}>{health?.benchmarks?.performance?.memory_percent || 0}%</div>
                </div>
                <div className="glass" style={{ padding: '0.8rem' }}>
                   <div className="label" style={{ fontSize: '0.55rem' }}>KAIROS Idle Triggers</div>
                   <div className="mono" style={{ fontSize: '1rem', fontWeight: 700 }}>{health?.benchmarks?.kairos?.idle_triggers || 0}</div>
                </div>
                <div className="glass" style={{ padding: '0.8rem' }}>
                   <div className="label" style={{ fontSize: '0.55rem' }}>Autonomous Corrections</div>
                   <div className="mono" style={{ fontSize: '1rem', fontWeight: 700 }}>{health?.benchmarks?.autodream?.corrections_found || 0}</div>
                </div>
             </div>
          </div>
        </div>
      </div>

      {/* ─── Machine Speed Bus ────────────────────────── */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <Activity size={14} color="var(--primary)" />
          <span className="panel__title">Machine-Speed Event Bus</span>
          <div className="status-dot status-dot--online" style={{ marginLeft: 'auto' }} />
        </div>
        <div className="panel__content mono" style={{ flex: 1, overflowY: 'auto', padding: '1rem', fontSize: '0.65rem' }}>
          {events.length === 0 && <div style={{ opacity: 0.3, textAlign: 'center', padding: '2rem' }}>WAITING FOR MACHINE ACTIVITY...</div>}
          {events.map((ev, i) => (
            <div key={i} style={{ marginBottom: 12, paddingLeft: 12, borderLeft: '1px solid var(--surface-border)', position: 'relative' }}>
              <div style={{ position: 'absolute', left: -4, top: 4, width: 8, height: 8, borderRadius: '50%', background: ev.type === 'error' ? 'var(--secondary)' : 'var(--primary)', boxShadow: `0 0 10px ${ev.type === 'error' ? 'var(--secondary)' : 'var(--primary)'}` }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.5, marginBottom: 2 }}>
                <span>{ev.type?.toUpperCase()}</span>
                <span>{new Date(ev.ts * 1000).toLocaleTimeString()}</span>
              </div>
              <div style={{ color: ev.type === 'error' ? 'var(--secondary)' : 'var(--text)', wordBreak: 'break-all' }}>
                {JSON.stringify(ev.data)}
              </div>
            </div>
          )).reverse()}
        </div>

        {/* External Health */}
        <div style={{ padding: '1rem', borderTop: '1px solid var(--surface-border)', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>SUPERALGOS NODES</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div className={`status-dot status-dot--${health?.superalgos?.status === 'online' ? 'online' : 'offline'}`} />
              <span className="mono" style={{ fontSize: '0.6rem' }}>{health?.superalgos?.active_bots || 0} ACTIVE</span>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>CONTENT PIPELINE</span>
            <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--accent)' }}>READY</span>
          </div>
        </div>
      </div>

    </div>
  );
}
