import React, { useState, useEffect, useCallback } from 'react';
import { Cpu, Brain, Activity, Terminal, GitBranch, Layers, Shield, Database, Check, X, RefreshCw, Loader2, Zap, Radio, Eye, EyeOff, Clock } from 'lucide-react';
import { engineState, engineResults } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

const LANES = [
  { id: 'coding', label: 'Coding', desc: 'Code gen, refactor, implement', examples: ['code', 'function', 'class', 'implement', 'refactor', 'write', 'build'] },
  { id: 'business_logic', label: 'Business Logic', desc: 'Policy, rules, compliance', examples: ['policy', 'rule', 'approval', 'compliance', 'budget', 'business', 'logic'] },
  { id: 'agent_brain', label: 'Agent Brain', desc: 'Browser, automation, click', examples: ['agent', 'browser', 'click', 'navigate', 'autonom'] },
  { id: 'tool_calling', label: 'Tool Calling', desc: 'APIs, tools, execution', examples: ['tool', 'call', 'invoke', 'api', 'validate', 'execute'] },
  { id: 'cross_domain', label: 'Cross Domain', desc: 'Everything else', examples: ['default fallback route'] },
];

const TASK_PATTERNS = [
  { pattern: 'create-react-component', routes: ['create-react-component', 'react-component'] },
  { pattern: 'scaffold-rest-api', routes: ['scaffold-rest-api', 'api-scaffold'] },
  { pattern: 'add-auth', routes: ['add-auth'] },
  { pattern: 'generate-dockerfile', routes: ['generate-dockerfile'] },
  { pattern: 'audit-repo', routes: ['audit-repo'] },
  { pattern: 'live-docs-to-skill', routes: ['live-docs-to-skill'] },
  { pattern: 'landing-page', routes: ['landing-page'] },
  { pattern: 'css-layout', routes: ['css-layout'] },
];

export default function BrainOps() {
  const [state, setState] = useState(null);
  const [results, setResults] = useState([]);
  const [pageState, updatePageState] = usePageState('brain-ops', {
    activeLane: null,
    showInternals: false,
    testQuery: '',
    routingResult: null,
  });
  const [loading, setLoading] = useState(false);
  const [soulData, setSoulData] = useState(null);

  const refresh = useCallback(async () => {
    const [s, r, soul] = await Promise.all([
      engineState(),
      engineResults(),
      fetch('http://localhost:8000/soul').then(r => r.json()).catch(() => null),
    ]);
    if (!s._error) setState(s);
    if (!r._error) setResults(r.results || []);
    if (soul && !soul._error) setSoulData(soul);
  }, []);

  useAutoRefresh(refresh, 5000, true);

  const testRoute = async () => {
    if (!pageState.testQuery.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/reason', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: pageState.testQuery }),
      });
      const data = await res.json();
      updatePageState({ routingResult: data });
    } catch (e) {
      updatePageState({ routingResult: { error: e.message } });
    }
    setLoading(false);
  };

  const eng = state?.engine || {};
  const comps = state?.components || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

      {/* Top Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr', gap: 'var(--gap-md)' }}>
        <MetricCard label="Lanes Active" value={LANES.length} icon={Layers} color="var(--primary)" />
        <MetricCard label="Task Patterns" value={TASK_PATTERNS.length} icon={GitBranch} color="var(--accent)" />
        <MetricCard label="Confidence Gate" value={`${((eng.confidence_threshold || 0.85) * 100).toFixed(0)}%`} icon={Shield} color="var(--warning)" />
        <MetricCard label="Sessions" value={results.length} icon={Terminal} color="var(--secondary)" />
        <MetricCard label="Components" value={comps.length} icon={Cpu} color="#A78BFA" />
      </div>

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--gap-md)' }}>

        {/* Left Column: Lane Router + Task Parser */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

          {/* Lane Router Visualization */}
          <div className="glass panel">
            <div className="panel__header">
              <Brain size={14} color="var(--primary)" />
              <span className="panel__title">MoE Lane Router</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>DETERMINISTIC REGEX</span>
            </div>
            <div className="panel__body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {LANES.map(lane => (
                  <div
                    key={lane.id}
                    onClick={() => updatePageState({ activeLane: pageState.activeLane === lane.id ? null : lane.id })}
                    className="glass"
                    style={{
                      padding: '1rem',
                      cursor: 'pointer',
                      borderLeft: pageState.activeLane === lane.id ? '3px solid var(--primary)' : '3px solid transparent',
                      background: pageState.activeLane === lane.id ? 'rgba(0,184,255,0.05)' : 'transparent',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 24, height: 24, borderRadius: 6, background: 'rgba(0,184,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {lane.id === 'coding' && <Terminal size={14} color="var(--primary)" />}
                        {lane.id === 'business_logic' && <Shield size={14} color="var(--warning)" />}
                        {lane.id === 'agent_brain' && <Radio size={14} color="var(--accent)" />}
                        {lane.id === 'tool_calling' && <Zap size={14} color="#FF00D4" />}
                        {lane.id === 'cross_domain' && <Brain size={14} color="var(--text-muted)" />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 800, fontSize: '0.85rem' }}>{lane.label}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{lane.desc}</div>
                      </div>
                      <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{lane.id}</div>
                    </div>
                    {pageState.activeLane === lane.id && (
                      <div style={{ marginTop: 12, padding: '0.8rem', background: 'rgba(0,0,0,0.2)', borderRadius: 8 }}>
                        <div className="label" style={{ fontSize: '0.55rem', marginBottom: 6 }}>TRIGGER KEYWORDS</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {lane.examples.map(kw => (
                            <span key={kw} className="mono" style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: 4, fontSize: '0.6rem' }}>{kw}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Task Parser Patterns */}
          <div className="glass panel">
            <div className="panel__header">
              <GitBranch size={14} color="var(--accent)" />
              <span className="panel__title">Task Parser Registry</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>{TASK_PATTERNS.length} PATTERNS</span>
            </div>
            <div className="panel__body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {TASK_PATTERNS.map((tp, i) => (
                  <div key={i} className="glass" style={{ padding: '0.8rem' }}>
                    <div style={{ fontWeight: 800, fontSize: '0.75rem', marginBottom: 4 }}>{tp.pattern}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                      {tp.routes.map(r => (
                        <span key={r} className="mono" style={{ fontSize: '0.55rem', color: 'var(--primary)', background: 'rgba(0,184,255,0.1)', padding: '1px 6px', borderRadius: 3 }}>{r}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* Right Column: Route Tester + Memory */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

          {/* Interactive Route Tester */}
          <div className="glass panel" style={{ background: 'linear-gradient(135deg, rgba(0,184,255,0.05), rgba(0,255,159,0.05))' }}>
            <div className="panel__header">
              <Activity size={14} color="var(--accent)" />
              <span className="panel__title">Route Tester</span>
            </div>
            <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <div className="label" style={{ marginBottom: 6 }}>Test Query</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={pageState.testQuery}
                    onChange={e => updatePageState({ testQuery: e.target.value })}
                    onKeyDown={e => e.key === 'Enter' && testRoute()}
                    placeholder="e.g. build a react component with auth"
                    style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.7rem', color: 'var(--text)', fontSize: '0.8rem' }}
                  />
                  <button
                    onClick={testRoute}
                    disabled={loading || !pageState.testQuery.trim()}
                    style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.7rem 1.2rem', color: '#fff', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    {loading ? <Loader2 size={14} className="spin" /> : <Zap size={14} />} ROUTE
                  </button>
                </div>
              </div>

              {pageState.routingResult && !pageState.routingResult.error && (
                <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span className="label" style={{ fontSize: '0.55rem' }}>ROUTING DECISION</span>
                    <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--accent)' }}>
                      CONFIDENCE: {(pageState.routingResult.decision?.confidence * 100 || 0).toFixed(0)}%
                    </span>
                  </div>
                  <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--primary)' }}>
                    {pageState.routingResult.decision?.chosen_skill || 'N/A'}
                  </div>
                  <div style={{ marginTop: 8, fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                    Task: {pageState.routingResult.task?.task || 'N/A'}
                  </div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                    <span className="mono" style={{ fontSize: '0.55rem', color: pageState.routingResult.decision?.audit_ok ? 'var(--accent)' : 'var(--secondary)' }}>
                      AUDIT: {pageState.routingResult.decision?.audit_ok ? 'PASS' : 'FAIL'}
                    </span>
                  </div>
                </div>
              )}

              {pageState.routingResult?.error && (
                <div style={{ padding: '1rem', background: 'rgba(255,107,107,0.05)', borderRadius: 8, color: 'var(--secondary)', fontSize: '0.75rem' }}>
                  Error: {pageState.routingResult.error}
                </div>
              )}
            </div>
          </div>

          {/* Session Memory */}
          <div className="glass panel">
            <div className="panel__header">
              <Database size={14} color="var(--primary)" />
              <span className="panel__title">Session Memory</span>
              <button onClick={() => updatePageState({ showInternals: !pageState.showInternals })} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                {pageState.showInternals ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <div className="panel__body">
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                Recent sessions: {results.length}
              </div>
              {pageState.showInternals && (
                <div className="mono" style={{ fontSize: '0.6rem', background: 'rgba(0,0,0,0.3)', padding: '0.8rem', borderRadius: 8, maxHeight: 250, overflowY: 'auto' }}>
                  {results.length > 0 ? (
                    results.slice(0, 5).map((r, i) => (
                      <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <span style={{ color: 'var(--accent)' }}>{r.result?.skill_executed || r.result?.status || 'ok'}</span>
                        {' '}
                        <span style={{ color: 'var(--text-muted)' }}>{JSON.stringify(r.result?.message || '').slice(0, 80)}</span>
                      </div>
                    ))
                  ) : (
                    <div style={{ opacity: 0.5 }}>No session history yet. Run a query to see results.</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Soul Identity Summary */}
          <div className="glass panel">
            <div className="panel__header">
              <Radio size={14} color="#FFD700" />
              <span className="panel__title">Soul Identity</span>
            </div>
            <div className="panel__body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="label" style={{ fontSize: '0.6rem' }}>Name</span>
                  <span className="mono" style={{ fontSize: '0.7rem' }}>{soulData?.identity?.name || '---'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="label" style={{ fontSize: '0.6rem' }}>Role</span>
                  <span className="mono" style={{ fontSize: '0.7rem' }}>{soulData?.identity?.role || '---'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="label" style={{ fontSize: '0.6rem' }}>Mission</span>
                  <span className="mono" style={{ fontSize: '0.55rem', maxWidth: 150, textAlign: 'right', wordBreak: 'break-word' }}>{soulData?.agenda?.mission?.slice(0, 80) || '---'}</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
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
