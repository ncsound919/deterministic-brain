import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Cpu, Database, Shield, Layers, GitBranch, Clock, Check, Radio, Trash2 } from 'lucide-react';
import { engineState, engineProcess } from '../api';
import { MetricCard, ComponentCard, CronQueuePanel, ResultsBank, EventFeed, QueryInput } from '../components/AetherUI';
import { useAutoRefresh } from '../stateManager';

export default function CommandCenter() {
  const [state, setState] = useState(null);
  const [processing, setProcessing] = useState(false);

  const refresh = useCallback(async () => {
    const data = await engineState();
    if (!data._error) setState(data);
  }, []);

  useAutoRefresh(refresh, 4000, true);

  const handleSubmit = async (q) => {
    setProcessing(true);
    await engineProcess(q);
    await refresh();
    setProcessing(false);
  };

  const handleClearLog = async () => {
    try { await fetch('/dashboard/feed-clear', { method: 'POST' }); await refresh(); } catch {}
  };

  const eng = state?.engine || {};
  const comps = state?.components || [];
  const feedEvents = state?.events || [];
  const results = state?.results || [];
  const cronTasks = state?.cron_queue || [];
  const lastResult = results.length > 0 ? results[results.length - 1] : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>

      {/* Key Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--gap-md)' }}>
        <MetricCard label="Active Skills" value={eng.skill_count || 0} icon={Layers} color="var(--primary)" />
        <MetricCard label="Confidence Gate" value={`${((eng.confidence_threshold || 0.85) * 100).toFixed(0)}%`} icon={Shield} color="var(--accent)" />
        <MetricCard label="Cron Tasks" value={cronTasks.length} icon={Clock} color="var(--warning)" />
        <MetricCard label="Results Banked" value={results.length} icon={Database} color="var(--secondary)" />
      </div>

      {/* Three-panel layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>

        {/* Left: Active Components + Event Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
          <div className="glass panel">
            <div className="panel__header">
              <Cpu size={14} color="var(--primary)" />
              <span className="panel__title">Active Components</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>{comps.length} RUNNING</span>
            </div>
            <div className="panel__body">
              <div className="comp-grid">
                {comps.map((c, i) => {
                  const metaText = c.mode || c.type || c.threshold || c.routes || c.imported || c.schemas;
                  return <ComponentCard key={i} name={c.name} status={c.status} meta={metaText || (c.status === 'active' ? 'active' : 'waiting')} />;
                })}
              </div>
            </div>
          </div>

          <div className="glass panel" style={{ flex: 1 }}>
            <div className="panel__header">
              <Radio size={14} color="var(--accent)" />
              <span className="panel__title">Live Event Feed</span>
              <button onClick={handleClearLog} title="Clear event log"
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', opacity: 0.5 }}>
                <Trash2 size={12} />
              </button>
            </div>
            <EventFeed events={feedEvents} />
          </div>
        </div>

        {/* Right: Cron Schedule + Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
          <CronQueuePanel tasks={cronTasks} />
          <ResultsBank results={results} />
        </div>
      </div>

      {/* Latest Result Summary */}
      {lastResult && (
        <div className="glass" style={{ padding: '0.8rem 1.2rem', display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.75rem' }}>
          <Check size={14} color="var(--accent)" />
          <span className="mono" style={{ color: 'var(--accent)', fontWeight: 700 }}>LAST RUN:</span>
          <span style={{ color: 'var(--text-muted)' }}>
            {(lastResult.result?.intent || lastResult.result?.skill || 'task').toUpperCase()}
          </span>
          <span className="mono" style={{ color: 'var(--text-muted)', opacity: 0.5 }}>
            &mdash; {lastResult.query?.slice(0, 60) || ''}
          </span>
        </div>
      )}

      {/* Query Input */}
      <QueryInput onSubmit={handleSubmit} disabled={processing} placeholder="Ask the brain to do something..." />
    </div>
  );
}
