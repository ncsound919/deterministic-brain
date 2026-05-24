import React, { useState, useEffect } from 'react';
import { FolderGit2, Search, GitBranch, Download, RefreshCw, Loader2, ExternalLink, CheckCircle, XCircle, Star, GitFork, Terminal, FileCode, Database } from 'lucide-react';
import { githubSearchRaw, githubCloneRaw, githubExpandSkillsRaw, knowledgeStats } from '../api';

export default function GitHubManager() {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState([]);
  const [inventory, setInventory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [cloneUrl, setCloneUrl] = useState('');
  const [cloneOwner, setCloneOwner] = useState('');
  const [cloneRepo, setCloneRepo] = useState('');

  const addLog = (msg, status = 'info') => {
    setLogs(prev => [{ ts: new Date().toLocaleTimeString(), msg, status }, ...prev.slice(0, 99)]);
  };

  const searchRepos = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    addLog(`Searching: ${searchQuery}`, 'running');
    try {
      const data = await githubSearchRaw(searchQuery, 20);
      if (!data._error) {
        setResults(data.repos || []);
        addLog(`Found ${data.repos?.length || 0} repos`, 'success');
      } else {
        addLog(`Search failed: ${data._error}`, 'failed');
      }
    } catch (e) { addLog(`Search failed: ${e.message}`, 'failed'); }
    setLoading(false);
  };

  const cloneRepoAction = async (owner, repo) => {
    const o = owner || cloneOwner;
    const r = repo || cloneRepo;
    if (!o || !r) return;
    setLoading(true);
    addLog(`Cloning ${o}/${r}...`, 'running');
    try {
      const data = await githubCloneRaw(o, r);
      if (data.cloned) {
        addLog(`Cloned to ${data.path}`, 'success');
      } else {
        addLog('Clone failed or already exists', 'failed');
      }
    } catch (e) { addLog(`Clone failed: ${e.message}`, 'failed'); }
    setLoading(false);
  };

  const expandSkills = async () => {
    setLoading(true);
    addLog('Expanding skills from GitHub...', 'running');
    try {
      const data = await githubExpandSkillsRaw(5);
      addLog(`Skill expansion: ${JSON.stringify(data).slice(0, 200)}`, data.status === 'ok' ? 'success' : 'failed');
    } catch (e) { addLog(`Expand failed: ${e.message}`, 'failed'); }
    setLoading(false);
  };

  const refreshInventory = async () => {
    try {
      const data = await knowledgeStats();
      if (!data._error) setInventory(data);
    } catch (e) {}
  };

  useEffect(() => { refreshInventory(); }, []);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>

        {/* Search Bar */}
        <div className="glass panel">
          <div className="panel__header">
            <Search size={14} color="var(--primary)" />
            <span className="panel__title">GitHub Repository Manager</span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--accent)' }}>GITHUB API</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && searchRepos()}
                placeholder="Search repos (e.g. react components, python ml, rust cli tool...)"
                style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
              />
              <button onClick={searchRepos} disabled={loading || !searchQuery.trim()}
                style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.8rem 1.5rem', color: '#fff', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                {loading ? <Loader2 size={14} className="spin" /> : <Search size={14} />} SEARCH
              </button>
            </div>

            {/* Clone Input */}
            <div style={{ display: 'flex', gap: 8, marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--surface-border)' }}>
              <input value={cloneOwner} onChange={e => setCloneOwner(e.target.value)} placeholder="Owner" style={smallInputStyle} />
              <span style={{ alignSelf: 'center', color: 'var(--text-muted)' }}>/</span>
              <input value={cloneRepo} onChange={e => setCloneRepo(e.target.value)} placeholder="Repo name" style={smallInputStyle} />
              <button onClick={cloneRepoAction} disabled={loading || !cloneOwner || !cloneRepo}
                style={{ background: 'rgba(0,184,255,0.1)', border: '1px solid var(--primary)', borderRadius: 8, padding: '0.5rem 1rem', color: 'var(--primary)', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                <GitBranch size={14} /> CLONE
              </button>
              <button onClick={expandSkills} disabled={loading}
                style={{ background: 'rgba(0,255,159,0.1)', border: '1px solid var(--accent)', borderRadius: 8, padding: '0.5rem 1rem', color: 'var(--accent)', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                <Download size={14} /> EXPAND SKILLS
              </button>
            </div>
          </div>
        </div>

        {/* Search Results */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <FolderGit2 size={14} color="var(--warning)" />
            <span className="panel__title">Repositories ({results.length})</span>
            <button onClick={searchRepos} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {results.map((repo, i) => (
              <div key={i} className="glass" style={{ padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FolderGit2 size={14} color="var(--primary)" />
                  <span style={{ fontWeight: 800, fontSize: '0.85rem', color: 'var(--primary)' }}>{repo.full_name || repo.name}</span>
                  <a href={repo.html_url || repo.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)' }}><ExternalLink size={12} /></a>
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>{repo.description || 'No description'}</div>
                <div style={{ display: 'flex', gap: '1rem', marginTop: 8, alignItems: 'center' }}>
                  {repo.language && <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--accent)', background: 'rgba(0,255,159,0.1)', padding: '2px 6px', borderRadius: 4 }}>{repo.language}</span>}
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}><Star size={10} /> {repo.stargazers_count || repo.stars || 0}</span>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}><GitFork size={10} /> {repo.forks_count || repo.forks || 0}</span>
                  <button onClick={() => { const o = repo.owner?.login || repo.owner || ''; const r = repo.name || ''; setCloneOwner(o); setCloneRepo(r); cloneRepoAction(o, r); }}
                    style={{ marginLeft: 'auto', background: 'rgba(0,184,255,0.1)', border: '1px solid var(--primary)', borderRadius: 4, padding: '0.3rem 0.8rem', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.6rem', fontWeight: 700 }}>
                    <GitBranch size={10} style={{ marginRight: 4 }} /> CLONE
                  </button>
                </div>
              </div>
            ))}
            {results.length === 0 && (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                Search GitHub for repositories to clone and integrate.
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Sidebar: Logs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
        <div className="glass panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <Terminal size={14} color="var(--accent)" />
            <span className="panel__title">Operation Log</span>
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

        {/* Inventory Stats */}
        <div className="glass" style={{ padding: '1rem' }}>
          <div className="label">Knowledge Bank</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 900, color: 'var(--primary)', marginTop: 4 }}>
            {inventory?.total_fragments?.toLocaleString() || 0} <span style={{ fontSize: '0.65rem', fontWeight: 500 }}>Fragments</span>
          </div>
          <div className="mono" style={{ fontSize: '0.6rem', marginTop: 4, opacity: 0.6 }}>
            Tags: {inventory?.tags?.length || 0}
          </div>
        </div>
      </div>

    </div>
  );
}

const smallInputStyle = { flex: 1, minWidth: 80, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.5rem', color: 'var(--text)', fontSize: '0.75rem' };
