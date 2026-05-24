import React, { useState, useEffect, useCallback } from 'react';
import { plannerTasks, plannerAdd, plannerRunDue, saasProjects, saasCreate, chainsList, chainsRun } from '../api';
import { Briefcase, Plus, Play, Rocket, GitBranch, Server, Activity, CheckCircle, Clock, Zap, Globe, Search, Loader2 } from 'lucide-react';
import { usePageState, useAutoRefresh } from '../stateManager';

export default function BusinessDev() {
  const [tasks, setTasks] = useState([]);
  const [chains, setChains] = useState([]);
  const [projects, setProjects] = useState([]);
  const [pageState, updatePageState] = usePageState('business-dev', {
    newTitle: '',
    newQuery: '',
    newProjName: '',
    newProjIdea: '',
  });
  const [running, setRunning] = useState(false);
  const [advancing, setAdvancing] = useState(null);

  const refresh = useCallback(async () => {
    const [t, p, c] = await Promise.all([plannerTasks(), saasProjects(), chainsList()]);
    if (!t._error) setTasks(t.tasks || []);
    if (!p._error) setProjects(p.projects || []);
    if (!c._error) setChains(Object.entries(c.chains || c).filter(([k]) => k !== '_error'));
  }, []);

  useAutoRefresh(refresh, 30000, true);

  const handleAddTask = async () => {
    if (!pageState.newTitle || !pageState.newQuery) return;
    await plannerAdd(pageState.newTitle, pageState.newQuery);
    updatePageState({ newTitle: '', newQuery: '' });
    refresh();
  };

  const handleRunDue = async () => { setRunning(true); await plannerRunDue(); await refresh(); setRunning(false); };

  const handleCreateProject = async () => {
    if (!pageState.newProjName || !pageState.newProjIdea) return;
    await saasCreate(pageState.newProjName, pageState.newProjIdea);
    updatePageState({ newProjName: '', newProjIdea: '' });
    refresh();
  };

  const handleAdvanceProject = async (projectId) => {
    setAdvancing(projectId);
    try {
      const res = await fetch(`http://localhost:8000/saas/advance?project_id=${encodeURIComponent(projectId)}`, { method: 'POST' });
      if (res.ok) await refresh();
    } catch (e) { console.error(e); }
    setAdvancing(null);
  };

  const handleRunChain = async (name) => { setRunning(true); await chainsRun(name); await refresh(); setRunning(false); };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>
        {/* Active Projects Portfolio */}
        <div className="glass panel">
          <div className="panel__header">
            <Rocket size={14} color="var(--primary)" />
            <span className="panel__title">Project Portfolio & Deployment Pipeline</span>
            <button onClick={handleRunDue} disabled={running} style={{ marginLeft: 'auto', background: 'rgba(0,184,255,0.1)', border: '1px solid var(--primary)', borderRadius: 6, padding: '0.3rem 0.8rem', color: 'var(--primary)', fontSize: '0.65rem', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Play size={12} /> RUN ALL PENDING OPS
            </button>
          </div>
          <div className="panel__body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
              {projects.map((p, i) => (
                <div key={i} className="glass" style={{ padding: '1rem', borderLeft: `3px solid ${p.stage === 'production' ? 'var(--accent)' : 'var(--warning)'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ fontWeight: 800, fontSize: '0.9rem' }}>{p.name}</div>
                    <div className={`status-pill status-pill--${p.stage === 'production' ? 'online' : 'offline'}`} style={{ fontSize: '0.5rem' }}>{p.stage?.toUpperCase() || 'DEVELOPMENT'}</div>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4, height: 32, overflow: 'hidden' }}>{p.idea}</div>
                  
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--surface-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <Activity size={12} color="var(--primary)" />
                      <span className="mono" style={{ fontSize: '0.6rem' }}>88% HEALTH</span>
                    </div>
                    <button onClick={() => handleAdvanceProject(p.id)} disabled={advancing === p.id}
                      style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {advancing === p.id ? <Loader2 size={12} className="spin" /> : 'CONSOLE'}
                    </button>
                  </div>
                </div>
              ))}
              {projects.length === 0 && <div className="label" style={{ gridColumn: '1/-1', textAlign: 'center', padding: '2rem' }}>No projects initialized. Use the factory on the right.</div>}
            </div>
          </div>
        </div>

        {/* Task Planner & Backlog */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <Briefcase size={14} color="var(--accent)" />
            <span className="panel__title">Operational Backlog</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', gap: 8, marginBottom: '1.5rem' }}>
              <input value={pageState.newTitle} onChange={e => updatePageState({ newTitle: e.target.value })} placeholder="Operation ID (e.g. Q3 Audit)" style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.6rem 1rem', color: 'var(--text)', fontSize: '0.8rem' }} />
              <input value={pageState.newQuery} onChange={e => updatePageState({ newQuery: e.target.value })} placeholder="Action parameters..." style={{ flex: 2, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.6rem 1rem', color: 'var(--text)', fontSize: '0.8rem' }} />
              <button onClick={handleAddTask} style={{ background: 'var(--primary)', border: 'none', borderRadius: 8, padding: '0.6rem 1.2rem', color: '#fff', fontWeight: 800, cursor: 'pointer' }}><Plus size={16} /></button>
            </div>
            {tasks.slice(0, 15).map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0.7rem', borderBottom: '1px solid var(--surface-border)' }}>
                {t.status === 'completed' ? <CheckCircle size={14} color="var(--accent)" /> : <Clock size={14} color="var(--text-muted)" />}
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '0.75rem' }}>{t.title}</div>
                  <div className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>SCHEDULE: {t.schedule}</div>
                </div>
                <div className="mono" style={{ fontSize: '0.6rem', padding: '0.2rem 0.5rem', borderRadius: 4, background: 'rgba(255,255,255,0.05)' }}>{t.status.toUpperCase()}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
        {/* Startup Factory */}
        <div className="glass panel">
          <div className="panel__header">
            <Zap size={14} color="#A78BFA" />
            <span className="panel__title">Startup Factory</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div className="label" style={{ marginBottom: 4 }}>Project Name</div>
              <input value={pageState.newProjName} onChange={e => updatePageState({ newProjName: e.target.value })} placeholder="e.g. VibeServe Pro" style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.7rem', color: 'var(--text)', fontSize: '0.8rem' }} />
            </div>
            <div>
              <div className="label" style={{ marginBottom: 4 }}>Concept / Tech Stack</div>
              <textarea value={pageState.newProjIdea} onChange={e => updatePageState({ newProjIdea: e.target.value })} placeholder="Brief description..." style={{ width: '100%', height: 100, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.7rem', color: 'var(--text)', fontSize: '0.8rem', resize: 'none' }} />
            </div>
            <button onClick={handleCreateProject} style={{ background: 'linear-gradient(135deg, #A78BFA, #8B5CF6)', border: 'none', borderRadius: 8, padding: '0.8rem', color: '#fff', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <Rocket size={16} /> INITIALIZE SAAS
            </button>
          </div>
        </div>

        {/* Global Business Chains */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <GitBranch size={14} color="var(--warning)" />
            <span className="panel__title">Global Ops Chains</span>
          </div>
          <div className="panel__body">
            {chains.map(([name, data], i) => (
              <div key={i} className="glass" style={{ padding: '0.8rem', marginBottom: '0.6rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.75rem' }}>{name.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Multi-step Agent Chain</div>
                </div>
                <button onClick={() => handleRunChain(name)} disabled={running} style={{ background: 'rgba(255,184,0,0.1)', border: '1px solid var(--warning)', borderRadius: 4, padding: '0.3rem 0.6rem', color: 'var(--warning)', fontSize: '0.6rem', fontWeight: 800, cursor: 'pointer' }}>
                  RUN
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Market Research Feed */}
        <div className="glass panel">
          <div className="panel__header">
            <Globe size={14} color="var(--primary)" />
            <span className="panel__title">Market Intel Snippets</span>
          </div>
          <div className="panel__body">
             <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ fontSize: '0.7rem', padding: '0.5rem', background: 'rgba(0,184,255,0.05)', borderRadius: 6, borderLeft: '3px solid var(--primary)' }}>
                  <strong>COMPETITOR ALERT:</strong> New AI agent platform launched by Meta.
                </div>
                <div style={{ fontSize: '0.7rem', padding: '0.5rem', background: 'rgba(255,107,107,0.05)', borderRadius: 6, borderLeft: '3px solid var(--secondary)' }}>
                  <strong>OPPORTUNITY:</strong> High demand for sovereign LLM nodes in EU.
                </div>
             </div>
          </div>
        </div>
      </div>

    </div>
  );
}
