import React, { useState, useEffect } from 'react';
import { Globe, Play, Square, RefreshCw, Loader2, Terminal, MousePointer, Monitor, Camera, FileText, Link, Radio } from 'lucide-react';
import { taskDispatch } from '../api';

export default function BrowserAutomation() {
  const [url, setUrl] = useState('https://example.com');
  const [command, setCommand] = useState('');
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [logs, setLogs] = useState([]);
  const [running, setRunning] = useState(false);
  const [screenshots, setScreenshots] = useState([]);
  const [browsedUrl, setBrowsedUrl] = useState('about:blank');

  const addLog = (msg, status = 'info') => {
    setLogs(prev => [{ ts: new Date().toLocaleTimeString(), msg, status }, ...prev.slice(0, 99)]);
  };

  const navigateUrl = async () => {
    if (!url.trim()) return;
    setRunning(true);
    addLog(`Navigating to ${url}...`, 'running');
    try {
      const data = await taskDispatch(`browser navigate to ${url}`);
      setBrowsedUrl(url);
      addLog(`Navigation result: ${JSON.stringify(data).slice(0, 200)}`, data.status === 'ok' ? 'success' : 'failed');
    } catch (e) { addLog(`Navigation failed: ${e.message}`, 'failed'); }
    setRunning(false);
  };

  const sendCommand = async (cmdOverride) => {
    const cmd = cmdOverride || command;
    if (!cmd.trim()) return;
    setRunning(true);
    addLog(`Sending: ${cmd}`, 'running');
    try {
      const data = await taskDispatch(`browser ${cmd}`);
      addLog(`Command result: ${JSON.stringify(data).slice(0, 200)}`, data.status === 'ok' ? 'success' : 'failed');
    } catch (e) { addLog(`Command failed: ${e.message}`, 'failed'); }
    setRunning(false);
    setCommand('');
  };

  const takeScreenshot = async () => {
    setRunning(true);
    addLog('Taking screenshot...', 'running');
    try {
      const data = await taskDispatch('browser take screenshot of current page');
      addLog(`Screenshot: ${JSON.stringify(data).slice(0, 200)}`, data.status === 'ok' ? 'success' : 'failed');
    } catch (e) { addLog(`Screenshot failed: ${e.message}`, 'failed'); }
    setRunning(false);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>

        {/* URL Bar */}
        <div className="glass panel">
          <div className="panel__header">
            <Globe size={14} color="var(--primary)" />
            <span className="panel__title">Browser Automation</span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--accent)' }}>PLAYWRIGHT ENGINE</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={url}
                onChange={e => setUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && navigateUrl()}
                placeholder="https://..."
                style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
              />
              <button onClick={navigateUrl} disabled={running || !url.trim()}
                style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.8rem 1.5rem', color: '#fff', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                {running ? <Loader2 size={14} className="spin" /> : <Play size={14} />} GO
              </button>
            </div>

            {/* Command Input */}
            <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
              <input
                value={command}
                onChange={e => setCommand(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendCommand()}
                placeholder="e.g. click the login button, fill the search form, extract all prices..."
                style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
              />
              <button onClick={sendCommand} disabled={running || !command.trim()}
                style={{ background: 'rgba(0,184,255,0.1)', border: '1px solid var(--primary)', borderRadius: 8, padding: '0.8rem 1.2rem', color: 'var(--primary)', fontWeight: 800, cursor: 'pointer' }}>
                SEND
              </button>
              <button onClick={takeScreenshot} disabled={running}
                style={{ background: 'rgba(0,255,159,0.1)', border: '1px solid var(--accent)', borderRadius: 8, padding: '0.8rem 1rem', color: 'var(--accent)', cursor: 'pointer' }}>
                <Camera size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Quick Commands */}
        <div className="glass panel">
          <div className="panel__header">
            <MousePointer size={14} color="var(--accent)" />
            <span className="panel__title">Quick Actions</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {[
                { cmd: 'click the first link on the page', icon: MousePointer, color: 'var(--primary)' },
                { cmd: 'extract all text from the page', icon: FileText, color: 'var(--accent)' },
                { cmd: 'find and click the login button', icon: Play, color: 'var(--warning)' },
                { cmd: 'fill the search form with "test"', icon: Terminal, color: '#FF00D4' },
                { cmd: 'scroll down 500 pixels', icon: Monitor, color: '#A78BFA' },
                { cmd: 'get all links on the page', icon: Link, color: '#FFD700' },
              ].map((action, i) => (
                <button key={i} onClick={() => { setCommand(action.cmd); sendCommand(action.cmd); }}
                  disabled={running}
                  style={{
                    padding: '0.8rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--surface-border)',
                    borderRadius: 8, color: 'var(--text)', cursor: 'pointer', display: 'flex', flexDirection: 'column',
                    alignItems: 'center', gap: 6, fontSize: '0.6rem', textAlign: 'center',
                  }}>
                  <action.icon size={18} color={action.color} />
                  {action.cmd.slice(0, 40)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Page Preview */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <Monitor size={14} color="var(--primary)" />
            <span className="panel__title">Current Page</span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>{url}</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
            <iframe
              src={browsedUrl}
              title="Browser Preview"
              style={{ width: '100%', height: '100%', minHeight: 300, border: 'none', borderRadius: 8, background: '#111' }}
            />
          </div>
        </div>

      </div>

      {/* Sidebar: Logs */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <Terminal size={14} color="var(--accent)" />
          <span className="panel__title">Browser Log</span>
        </div>
        <div className="panel__body mono" style={{ flex: 1, overflowY: 'auto', fontSize: '0.6rem' }}>
          {logs.map((entry, i) => (
            <div key={i} style={{ padding: '0.4rem', borderBottom: '1px solid var(--surface-border)' }}>
              <span style={{ color: 'var(--text-muted)' }}>[{entry.ts}]</span>{' '}
              <span style={{ color: entry.status === 'success' ? 'var(--accent)' : entry.status === 'failed' ? 'var(--secondary)' : entry.status === 'running' ? 'var(--primary)' : 'var(--text-muted)' }}>
                {entry.status === 'success' ? 'OK' : entry.status === 'failed' ? 'ERR' : entry.status === 'running' ? '>>>' : '--'}
              </span>{' '}
              {entry.msg}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
