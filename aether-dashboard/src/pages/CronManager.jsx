import React, { useState, useEffect, useCallback } from 'react';
import { Clock, Calendar, Play, RefreshCw, Loader2, Zap, Radio, Terminal, Settings, Trash2, Power } from 'lucide-react';
import { kairosStatus, cronScheduleRaw, cronToggle, cronDelete, cronAdd, cronRunDue, chainsList, autodreamRun, autonomyTick } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

export default function CronManager() {
  const [schedulerState, setSchedulerState] = useState(null);
  const [kairosState, setKairosState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pageState, updatePageState] = usePageState('cron-manager', {
    actionLog: [],
    newCronName: '',
    newCronExpr: '',
    newCronSkill: '',
  });
  const [acting, setActing] = useState({});

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [ks, cr] = await Promise.all([kairosStatus(), cronScheduleRaw()]);
      if (!ks._error) setKairosState(ks);
      if (!cr._error) setSchedulerState(cr);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useAutoRefresh(refresh, 10000, true);

  const addLog = (msg, status = 'info') => {
    const entry = { ts: new Date().toLocaleTimeString(), msg, status };
    updatePageState({ actionLog: [entry, ...pageState.actionLog.slice(0, 49)] });
  };

  const handleAction = async (actionFn, label) => {
    setActing(prev => ({ ...prev, [label]: true }));
    addLog(`Triggering ${label}...`, 'running');
    try {
      const data = await actionFn();
      addLog(`${label}: ${JSON.stringify(data).slice(0, 200)}`, data?.status === 'ok' || !data?._error ? 'success' : 'failed');
    } catch (e) {
      addLog(`${label} failed: ${e.message}`, 'failed');
    }
    setActing(prev => ({ ...prev, [label]: false }));
    refresh();
  };

  const handleToggle = async (name) => {
    setActing(prev => ({ ...prev, [`toggle_${name}`]: true }));
    addLog(`Toggling ${name}...`, 'running');
    try {
      const data = await cronToggle(name);
      addLog(`Toggle ${name}: ${JSON.stringify(data).slice(0, 200)}`, !data?._error ? 'success' : 'failed');
    } catch (e) {
      addLog(`Toggle failed: ${e.message}`, 'failed');
    }
    setActing(prev => ({ ...prev, [`toggle_${name}`]: false }));
    refresh();
  };

  const handleDelete = async (name) => {
    setActing(prev => ({ ...prev, [`delete_${name}`]: true }));
    addLog(`Deleting ${name}...`, 'running');
    try {
      const data = await cronDelete(name);
      addLog(`Delete ${name}: ${JSON.stringify(data).slice(0, 200)}`, data?.status === 'ok' ? 'success' : 'failed');
    } catch (e) {
      addLog(`Delete failed: ${e.message}`, 'failed');
    }
    setActing(prev => ({ ...prev, [`delete_${name}`]: false }));
    refresh();
  };

  const addCustomCron = async () => {
    if (!pageState.newCronName || !pageState.newCronExpr || !pageState.newCronSkill) return;
    setActing(prev => ({ ...prev, addCron: true }));
    addLog(`Adding cron: ${pageState.newCronName} (${pageState.newCronExpr}) -> ${pageState.newCronSkill}`, 'running');
    try {
      const data = await cronAdd({ name: pageState.newCronName, skill: pageState.newCronSkill, trigger_type: 'cron', cron_expr: pageState.newCronExpr });
      addLog(`Cron task added: ${JSON.stringify(data).slice(0, 200)}`, data?.status === 'ok' ? 'success' : 'failed');
    } catch (e) {
      addLog(`Add cron failed: ${e.message}`, 'failed');
    }
    setActing(prev => ({ ...prev, addCron: false }));
    updatePageState({ newCronName: '', newCronExpr: '', newCronSkill: '' });
    refresh();
  };

  const tasks = schedulerState?.tasks || [];
  const cronTasks = tasks.filter(t => t.trigger === 'cron');
  const intervalTasks = tasks.filter(t => t.trigger === 'interval');

  const fmtNextRun = (nextRun) => {
    if (!nextRun) return '\u2014';
    try {
      return new Date(nextRun).toLocaleString();
    } catch {
      return nextRun;
    }
  };

  const kairosOk = kairosState?.status === 'idle' || kairosState?.status === 'running';
  const schedulerRunning = schedulerState?.running;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>

        {/* Status Controls */}
        <div className="glass" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="status-dot" style={{
              width: 10, height: 10, borderRadius: '50%', display: 'inline-block',
              background: kairosOk ? 'var(--accent)' : 'var(--secondary)',
            }} />
            <span className="mono" style={{ fontSize: '0.75rem', color: kairosOk ? 'var(--accent)' : 'var(--secondary)', fontWeight: 800 }}>
              KAIROS: {kairosState?.status?.toUpperCase() || 'CHECKING'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="status-dot" style={{
              width: 10, height: 10, borderRadius: '50%', display: 'inline-block',
              background: schedulerRunning ? 'var(--accent)' : 'var(--secondary)',
            }} />
            <span className="mono" style={{ fontSize: '0.75rem', color: schedulerRunning ? 'var(--accent)' : 'var(--secondary)', fontWeight: 800 }}>
              SCHEDULER: {schedulerRunning ? 'RUNNING' : 'STOPPED'}
            </span>
          </div>

          <button onClick={() => handleAction(autodreamRun, 'AutoDream Run')} style={actionBtn('var(--primary)')} disabled={acting['AutoDream Run']}>
            {acting['AutoDream Run'] ? <Loader2 size={12} className="spin" /> : <Zap size={12} />}
            DREAM NOW
          </button>
          <button onClick={() => handleAction(autonomyTick, 'Autonomy Tick')} style={actionBtn('var(--accent)')} disabled={acting['Autonomy Tick']}>
            {acting['Autonomy Tick'] ? <Loader2 size={12} className="spin" /> : <Radio size={12} />}
            TICK
          </button>
          <button onClick={() => handleAction(cronRunDue, 'Run Due Jobs')} style={actionBtn('var(--warning,#ffb800)')} disabled={acting['Run Due Jobs']}>
            {acting['Run Due Jobs'] ? <Loader2 size={12} className="spin" /> : <Play size={12} />}
            RUN DUE
          </button>

          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {tasks.length} task{tasks.length !== 1 ? 's' : ''}
          </span>

          <button onClick={refresh} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>

        {/* Cron Tasks */}
        <div className="glass panel">
          <div className="panel__header">
            <Calendar size={14} color="var(--primary)" />
            <span className="panel__title">Cron Schedule ({cronTasks.length} task{cronTasks.length !== 1 ? 's' : ''})</span>
          </div>
          <div className="panel__body">
            {cronTasks.length === 0 ? (
              <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>No cron tasks configured</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {cronTasks.map((task, i) => (
                  <div key={task.name || i} className="glass" style={{
                    padding: '0.8rem 1rem', display: 'flex', alignItems: 'center', gap: '1rem',
                    opacity: task.enabled ? 1 : 0.5,
                  }}>
                    <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--primary)', fontWeight: 800, minWidth: 90 }}>{task.cron_expr || '\u2014'}</span>
                    <span className="mono" style={{ fontSize: '0.55rem', color: task.enabled ? 'var(--accent)' : 'var(--secondary)', background: task.enabled ? 'rgba(0,255,159,0.1)' : 'rgba(255,80,80,0.1)', padding: '2px 6px', borderRadius: 4 }}>
                      {task.enabled ? 'CRON' : 'PAUSED'}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: '0.8rem' }}>{task.name}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{task.skill || ''}</div>
                    </div>
                    <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)', minWidth: 140 }}>{fmtNextRun(task.next_run)}</span>
                    <button onClick={() => handleToggle(task.name)}
                      style={{ background: 'none', border: 'none', color: task.enabled ? 'var(--accent)' : 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
                      disabled={acting[`toggle_${task.name}`]}
                      title={task.enabled ? 'Disable' : 'Enable'}>
                      {acting[`toggle_${task.name}`] ? <Loader2 size={14} className="spin" /> : <Power size={14} />}
                    </button>
                    <button onClick={() => handleDelete(task.name)}
                      style={{ background: 'none', border: 'none', color: 'var(--secondary)', cursor: 'pointer', padding: 4 }}
                      disabled={acting[`delete_${task.name}`]}
                      title="Delete">
                      {acting[`delete_${task.name}`] ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Interval Tasks */}
        {intervalTasks.length > 0 && (
          <div className="glass panel">
            <div className="panel__header">
              <Clock size={14} color="var(--accent)" />
              <span className="panel__title">Interval Health Checks ({intervalTasks.length})</span>
            </div>
            <div className="panel__body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {intervalTasks.map((task, i) => (
                  <div key={task.name || i} className="glass" style={{
                    padding: '0.8rem 1rem', display: 'flex', alignItems: 'center', gap: '1rem',
                    opacity: task.enabled ? 1 : 0.5,
                  }}>
                    <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--accent)', fontWeight: 800, minWidth: 120 }}>
                      {task.interval_seconds ? `${task.interval_seconds}s` : '\u2014'}
                    </span>
                    <span className="mono" style={{ fontSize: '0.55rem', color: task.enabled ? 'var(--primary)' : 'var(--secondary)', background: task.enabled ? 'rgba(0,184,255,0.1)' : 'rgba(255,80,80,0.1)', padding: '2px 6px', borderRadius: 4 }}>
                      {task.enabled ? 'INTERVAL' : 'PAUSED'}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: '0.8rem' }}>{task.name}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{task.skill || ''}</div>
                    </div>
                    <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--text-muted)', minWidth: 140 }}>{fmtNextRun(task.next_run)}</span>
                    <button onClick={() => handleToggle(task.name)}
                      style={{ background: 'none', border: 'none', color: task.enabled ? 'var(--accent)' : 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
                      disabled={acting[`toggle_${task.name}`]}
                      title={task.enabled ? 'Disable' : 'Enable'}>
                      {acting[`toggle_${task.name}`] ? <Loader2 size={14} className="spin" /> : <Power size={14} />}
                    </button>
                    <button onClick={() => handleDelete(task.name)}
                      style={{ background: 'none', border: 'none', color: 'var(--secondary)', cursor: 'pointer', padding: 4 }}
                      disabled={acting[`delete_${task.name}`]}
                      title="Delete">
                      {acting[`delete_${task.name}`] ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Add Custom Cron */}
        <div className="glass panel" style={{ background: 'linear-gradient(135deg, rgba(0,184,255,0.03), rgba(0,255,159,0.03))' }}>
          <div className="panel__header">
            <Settings size={14} color="var(--primary)" />
            <span className="panel__title">Add Cron Task</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap' }}>
              <input value={pageState.newCronName} onChange={e => updatePageState({ newCronName: e.target.value })} placeholder="Task name" style={inputStyle()} />
              <input value={pageState.newCronExpr} onChange={e => updatePageState({ newCronExpr: e.target.value })} placeholder="Cron (e.g. 0 9 * * *)" style={inputStyle()} />
              <input value={pageState.newCronSkill} onChange={e => updatePageState({ newCronSkill: e.target.value })} placeholder="Skill name" style={inputStyle()} />
              <button onClick={addCustomCron} disabled={!pageState.newCronName || !pageState.newCronExpr || !pageState.newCronSkill || acting.addCron}
                style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.6rem 1.2rem', color: '#fff', fontWeight: 800, cursor: 'pointer' }}>
                {acting.addCron ? <Loader2 size={14} className="spin" style={{ marginRight: 6 }} /> : null}
                ADD CRON
              </button>
            </div>
          </div>
        </div>

      </div>

      {/* Sidebar: Action Log */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <Terminal size={14} color="var(--accent)" />
          <span className="panel__title">Action Log</span>
        </div>
        <div className="panel__body mono" style={{ flex: 1, overflowY: 'auto', fontSize: '0.6rem' }}>
          {pageState.actionLog.length === 0 ? (
            <div style={{ padding: '0.5rem', color: 'var(--text-muted)' }}>No actions yet</div>
          ) : (
            pageState.actionLog.map((entry, i) => (
              <div key={i} style={{ padding: '0.5rem', borderBottom: '1px solid var(--surface-border)' }}>
                <span style={{ color: 'var(--text-muted)' }}>[{entry.ts}]</span>{' '}
                <span style={{ color: entry.status === 'success' ? 'var(--accent)' : entry.status === 'failed' ? 'var(--secondary)' : 'var(--text-muted)' }}>{entry.status === 'success' ? 'OK' : entry.status === 'failed' ? 'ERR' : '--'}</span>{' '}
                {entry.msg}
              </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
}

function actionBtn(color) {
  return {
    padding: '0.5rem 1rem', borderRadius: 8, background: `${color}15`, border: `1px solid ${color}`,
    color: '#fff', cursor: 'pointer', fontSize: '0.7rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6,
  };
}

function inputStyle() {
  return { flex: 1, minWidth: 150, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.6rem', color: 'var(--text)', fontSize: '0.75rem' };
}
