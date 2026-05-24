import React, { useState, useEffect } from 'react';
import { Code, GitBranch, Zap, Search, Play, RefreshCw, Loader2, CheckCircle, XCircle, Clock, ExternalLink, Layers, BarChart3, Filter, Terminal, Info, Brain, Cpu, Globe, FileText, Bot, Settings, Shield, Image, Music, Briefcase, DollarSign, Plus } from 'lucide-react';
import { skillsList, chainsList, chainsRun, taskDispatch } from '../api';
import styles from './SkillMarketplace.module.css';
import { Skill, Chain, ExecutionLogEntry, CategoryMap } from './SkillMarketplace.types';
import { useNotifications } from '../stateManager';

const CATEGORY_MAP = {
  'ai-dev': { label: 'AI & LLM', icon: Bot, color: '#A78BFA', keywords: ['claude', 'openai', 'llm', 'vlm', 'asr', 'tts', 'speech', 'transcribe'] },
  'coding': { label: 'Coding & Dev', icon: Code, color: 'var(--primary)', keywords: ['react', 'api', 'docker', 'css', 'landing', 'auth', 'refactor', 'coding'] },
  'ops': { label: 'DevOps & Deploy', icon: Settings, color: '#FF8C00', keywords: ['deploy', 'cloudflare', 'netlify', 'vercel', 'render', 'k8s', 'ci'] },
  'docs-media': { label: 'Docs & Media', icon: FileText, color: '#FFD700', keywords: ['pdf', 'pptx', 'xlsx', 'docx', 'imagegen', 'canvas', 'video', 'podcast'] },
  'browser': { label: 'Browser & Scraping', icon: Globe, color: '#00FF9F', keywords: ['playwright', 'browser', 'web', 'screenshot', 'scrape', 'openclaw_web'] },
  'social': { label: 'Social & Content', icon: Image, color: '#FF69B4', keywords: ['social', 'content', 'wordpress', 'blog', 'seo', 'news'] },
  'business': { label: 'Business & CRM', icon: Briefcase, color: '#00B8FF', keywords: ['crm', 'email', 'betting', 'market', 'trading', 'saas'] },
  'security': { label: 'Security', icon: Shield, color: '#FF6B6B', keywords: ['security', 'audit', 'prompt-injection'] },
  'meta': { label: 'Meta & Workflow', icon: Brain, color: '#FF00D4', keywords: ['skill-creator', 'writing', 'plans', 'brainstorm', 'debug', 'tdd', 'review', 'git', 'session'] },
  'scientific': { label: 'Scientific', icon: BarChart3, color: '#7B68EE', keywords: ['bioinform', 'genom', 'scientific', 'research', 'lab'] },
};

const DEFAULT_CAT = 'all';

function categorizeSkill(skill: Skill): string {
  const text = [
    skill.skill_id || '',
    skill.skill_name || '',
    skill.description || '',
    skill.backend || ''
  ].join(' ').toLowerCase();

  for (const [key, cat] of Object.entries(CATEGORY_MAP)) {
    for (const kw of cat.keywords) {
      if (text.includes(kw)) return key;
    }
  }
  return 'other';
}

function isDestructiveSkill(skill: Skill): boolean {
  const destructiveKeywords = ['delete', 'remove', 'terminate', 'shutdown', 'wipe', 'clear', 'reset', 'purge', 'drop', 'uninstall'];
  const text = [
    skill.skill_id || '',
    skill.skill_name || '',
    skill.description || '',
    skill.backend || ''
  ].join(' ').toLowerCase();
  return destructiveKeywords.some(kw => text.includes(kw));
}

export default function SkillMarketplace(): JSX.Element {
  const { notify } = useNotifications();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [chains, setChains] = useState<Chain[]>([]);
  const [activeCat, setActiveCat] = useState<string>(DEFAULT_CAT);
  const [search, setSearch] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [running, setRunning] = useState<string | null>(null);
  const [resultLog, setResultLog] = useState<ExecutionLogEntry[]>([]);
  const [activeTab, setActiveTab] = useState<'skills' | 'chains'>('skills');
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [showCreate, setShowCreate] = useState<boolean>(false);
  const [newSkillName, setNewSkillName] = useState<string>('');
  const [newSkillDesc, setNewSkillDesc] = useState<string>('');
  const [newSkillCode, setNewSkillCode] = useState<string>('');
  const [showInputs, setShowInputs] = useState<boolean>(false);
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [selectedSkillForExecution, setSelectedSkillForExecution] = useState<Skill | null>(null);
  const [showConfirm, setShowConfirm] = useState<boolean>(false);
  const [skillToConfirm, setSkillToConfirm] = useState<Skill | null>(null);

  const createSkill = async (): Promise<void> => {
    if (!newSkillName || !newSkillCode) return;
    try {
      const res = await fetch('http://localhost:8000/upload/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newSkillName, content: newSkillCode, description: newSkillDesc }),
      });
      if (!res.ok) throw new Error('Upload failed');
      setNewSkillName(''); setNewSkillDesc(''); setNewSkillCode('');
      setShowCreate(false);
      refresh();
    } catch (e) { console.error(e); }
  };

  const refresh = async (): Promise<void> => {
    setLoading(true);
    try {
      const [sr, cr] = await Promise.all([
        skillsList(),
        chainsList(),
      ]);
      if (!sr._error) setSkills(sr.skills || []);
      if (!cr._error) setChains(cr.chains || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const runSkill = async (skillId: string, inputs: Record<string, string> = {}): Promise<void> => {
    setRunning(skillId);
    const ts = new Date().toLocaleTimeString();
    const skillName = skills.find(s => s.skill_id === skillId)?.skill_name || skillId;
    setResultLog(prev => [{ ts, skillId, status: 'running', msg: `Starting ${skillName}...` }, ...prev.slice(0, 49)]);
    
    // Show initial toast
    notify(`Starting ${skillName}...`, 'info', 3000);
    
    // Simulate progress updates for demo (in real app, use WebSocket or polling)
    const progressUpdates = [
      { delay: 500, msg: `Validating inputs for ${skillName}...` },
      { delay: 1000, msg: `Preparing execution environment...` },
      { delay: 1500, msg: `Executing ${skillName}...` },
    ];
    
    for (const update of progressUpdates) {
      await new Promise(resolve => setTimeout(resolve, update.delay));
      setResultLog(prev => [
        { ts: new Date().toLocaleTimeString(), skillId, status: 'running', msg: update.msg },
        ...prev.slice(0, 49),
      ]);
      notify(update.msg, 'info', 2000);
    }
    
    try {
      const inputStr = Object.keys(inputs).length > 0 ? ` with inputs ${JSON.stringify(inputs)}` : '';
      const data = await taskDispatch(`run skill ${skillId}${inputStr}`);
      const status = data.status === 'ok' ? 'success' : 'failed';
      const message = status === 'success' ? JSON.stringify(data.final_output || 'Done').slice(0, 200) : (data.detail || 'Failed').slice(0, 200);
      setResultLog(prev => [
        { ts: new Date().toLocaleTimeString(), skillId, status, msg: message },
        ...prev.slice(0, 49),
      ]);
      notify(`${skillName} completed ${status === 'success' ? 'successfully' : 'with errors'}`, status, 5000);
    } catch (e) {
      setResultLog(prev => [{ ts: new Date().toLocaleTimeString(), skillId, status: 'error', msg: e.message }, ...prev.slice(0, 49)]);
      notify(`Error executing ${skillName}: ${e.message}`, 'error', 5000);
    }
    setRunning(null);
  };

  const runChain = async (chainName: string): Promise<void> => {
    setRunning(chainName);
    const ts = new Date().toLocaleTimeString();
    setResultLog(prev => [{ ts, skillId: chainName, status: 'running', msg: `Starting chain ${chainName}...` }, ...prev.slice(0, 49)]);
    notify(`Starting chain ${chainName}...`, 'info', 3000);
    try {
      const data = await chainsRun(chainName, false);
      const status = data.status === 'ok' || data.status === 'completed' ? 'success' : 'failed';
      setResultLog(prev => [
        { ts: new Date().toLocaleTimeString(), skillId: chainName, status, msg: JSON.stringify(data).slice(0, 200) },
        ...prev.slice(0, 49),
      ]);
      notify(`Chain ${chainName} completed ${status === 'success' ? 'successfully' : 'with errors'}`, status, 5000);
    } catch (e) {
      setResultLog(prev => [{ ts: new Date().toLocaleTimeString(), skillId: chainName, status: 'error', msg: e.message }, ...prev.slice(0, 49)]);
      notify(`Error executing chain ${chainName}: ${e.message}`, 'error', 5000);
    }
    setRunning(null);
  };

  const categorizedSkills = {};
  let uncategorized = [];
  for (const skill of skills) {
    const cat = categorizeSkill(skill);
    if (cat === 'other') {
      uncategorized.push(skill);
    } else {
      if (!categorizedSkills[cat]) categorizedSkills[cat] = [];
      categorizedSkills[cat].push(skill);
    }
  }
  if (uncategorized.length > 0) categorizedSkills['other'] = uncategorized;

  const categoryCounts = {};
  Object.entries(CATEGORY_MAP).forEach(([k, v]) => {
    categoryCounts[k] = (categorizedSkills[k] || []).length;
  });
  categoryCounts['other'] = (categorizedSkills['other'] || []).length;
  categoryCounts['all'] = skills.length;

  let filteredSkills = skills;
  if (activeCat !== DEFAULT_CAT) {
    filteredSkills = categorizedSkills[activeCat] || [];
  }
  if (search.trim()) {
    const q = search.toLowerCase();
    filteredSkills = filteredSkills.filter(s =>
      (s.skill_id || '').toLowerCase().includes(q) ||
      (s.skill_name || '').toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q)
    );
  }

  const visibleCats = Object.entries(CATEGORY_MAP).filter(([k]) => (categorizedSkills[k] || []).length > 0);

  return (
    <div className={styles.container}>

      {/* Main Content */}
      <div className={styles.mainContent}>

        {/* Category Tabs */}
        <div className={`${styles.glass} ${styles.categoryTabs}`}>
          <Filter size={14} color="var(--primary)" style={{ marginRight: 4 }} />
          <button onClick={() => setActiveCat(DEFAULT_CAT)} className={activeCat === DEFAULT_CAT ? `${styles.categoryTab} ${styles.active}` : styles.categoryTab}>ALL ({skills.length})</button>
          {visibleCats.map(([catId, catMeta]) => (
            <button key={catId} onClick={() => setActiveCat(catId)} className={activeCat === catId ? `${styles.categoryTab} ${styles.active}` : styles.categoryTab}>
              {catMeta.label} ({categoryCounts[catId] || 0})
            </button>
          ))}
            <button onClick={() => setShowCreate(!showCreate)} style={{ background: 'rgba(0,255,159,0.1)', border: '1px solid var(--accent)', borderRadius: 8, padding: '0.4rem 0.8rem', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.65rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Plus size={12} /> NEW SKILL
            </button>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search {skills.length} skills..."
              className={styles.searchInput}
            />
            <button onClick={refresh} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <RefreshCw size={16} className={loading ? styles.spin : ''} />
            </button>
          </div>
        </div>

        {/* Tab Selector */}
        <div className={styles.tabSelector}>
          <button onClick={() => setActiveTab('skills')} className={tabStyle(activeTab === 'skills', true)}>
            <Code size={14} /> Skills ({skills.length})
          </button>
          <button onClick={() => setActiveTab('chains')} className={tabStyle(activeTab === 'chains', true)}>
            <GitBranch size={14} /> Skill Chains ({chains.length})
          </button>
        </div>

         {/* Confirmation Dialog Modal */}
        {showConfirm && skillToConfirm && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div className="glass panel" style={{ width: 450 }}>
              <div className="panel__header">
                <Zap size={14} color="var(--warning)" />
                <span className="panel__title">Confirm Execution</span>
                <button onClick={() => { setShowConfirm(false); setSkillToConfirm(null); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1rem' }}>×</button>
              </div>
              <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1.5rem', textAlign: 'center' }}>
                <div style={{ color: 'var(--text)', fontSize: '0.8rem', lineHeight: 1.6 }}>
                  <strong>{skillToConfirm.skill_name || skillToConfirm.skill_id}</strong> may perform destructive actions.
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                  Are you sure you want to execute this skill?
                </div>
                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                  <button
                    onClick={() => { setShowConfirm(false); runSkill(skillToConfirm.skill_id); }}
                    style={{ flex: 1, background: 'rgba(255,69,0,0.1)', border: '1px solid var(--secondary)', borderRadius: 6, padding: '0.6rem', color: 'var(--secondary)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                  >
                    CONFIRM & EXECUTE
                  </button>
                  <button
                    onClick={() => { setShowConfirm(false); setSkillToConfirm(null); }}
                    style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 6, padding: '0.6rem', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

         {/* Input Configuration Modal */}
        {showInputs && selectedSkillForExecution && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div className="glass panel" style={{ width: 500, maxHeight: '80vh', overflowY: 'auto' }}>
              <div className="panel__header">
                <Settings size={14} color="var(--primary)" />
                <span className="panel__title">Configure {selectedSkillForExecution.skill_name || selectedSkillForExecution.skill_id}</span>
                <button onClick={() => { setShowInputs(false); setSelectedSkillForExecution(null); setInputValues({}); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1rem' }}>×</button>
              </div>
              <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1rem' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', lineHeight: 1.5 }}>
                  {selectedSkillForExecution.description}
                </div>
                <form onSubmit={(e) => { e.preventDefault(); runSkill(selectedSkillForExecution.skill_id, inputValues); setShowInputs(false); }} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {selectedSkillForExecution.inputs && Object.keys(selectedSkillForExecution.inputs).length > 0 ? (
                    Object.entries(selectedSkillForExecution.inputs).map(([key, info]) => (
                      <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text)' }}>{key}</label>
                        <input
                          type="text"
                          value={inputValues[key] || ''}
                          onChange={(e) => setInputValues({ ...inputValues, [key]: e.target.value })}
                          placeholder={typeof info === 'string' ? info : JSON.stringify(info)}
                          style={{ ...createInputStyle, fontSize: '0.7rem' }}
                        />
                      </div>
                    )
                  ) : (
                    <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                      No input parameters required for this skill.
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '0.8rem', marginTop: '1rem' }}>
                    <button
                      type="submit"
                      disabled={running === selectedSkillForExecution.skill_id}
                      style={{ flex: 1, background: 'rgba(0,184,255,0.1)', border: '1px solid var(--primary)', borderRadius: 6, padding: '0.6rem', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                    >
                      {running === selectedSkillForExecution.skill_id ? <Loader2 size={12} className="spin" /> : <Play size={12} />}
                      RUN WITH INPUTS
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowInputs(false); setSelectedSkillForExecution(null); setInputValues({}); }}
                      style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 6, padding: '0.6rem', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                    >
                      CANCEL
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

         {/* Create New Skill Form */}
        {showCreate && (
          <div className={`${styles.glass} ${styles.panel} ${styles.createForm}`}>
            <div className={styles.panelHeader}>
              <Plus size={14} color="var(--primary)" />
              <span className={styles.panelTitle}>Create New Skill</span>
              <button onClick={() => setShowCreate(false)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1rem' }}>×</button>
            </div>
            <div className={styles.panelBody} style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <div style={{ display: 'flex', gap: '0.8rem' }}>
                <input value={newSkillName} onChange={e => setNewSkillName(e.target.value)} placeholder="Skill ID (kebab-case)" className={styles.createInput} />
                <input value={newSkillDesc} onChange={e => setNewSkillDesc(e.target.value)} placeholder="Short description" className={`${styles.createInput} ${styles.createInputLarge}`} />
              </div>
              <textarea value={newSkillCode} onChange={e => setNewSkillCode(e.target.value)} placeholder="Python implementation code..." className={`${styles.createInput} ${styles.createInputLarge}`} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem' }} />
              <button onClick={createSkill} disabled={!newSkillName || !newSkillCode}
                style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.6rem', color: '#fff', fontWeight: 800, cursor: 'pointer' }}>
                HOT-DEPLOY SKILL
              </button>
            </div>
          </div>
        )}

         {/* Skills Grid */}
        {activeTab === 'skills' && (
          <div className={styles.skillsGrid}>
            {filteredSkills.map((skill, i) => {
              const cat = categorizeSkill(skill);
              const catMeta = CATEGORY_MAP[cat] || {};
              const CatIcon = catMeta.icon || Zap;
              const desc = (skill.description || '').slice(0, 120);
              const hasInputs = skill.inputs && Object.keys(skill.inputs).length > 0;
              return (
                <div key={skill.skill_id || i} className={`${styles.glass} ${styles.panel} ${styles.skillCard}`}>
                  <div className={styles.skillHeader}>
                    <Zap size={12} color={catMeta.color || 'var(--accent)'} />
                    <span className={styles.skillTitle}>{skill.skill_name || skill.skill_id}</span>
                    <span className={`${styles.mono} ${styles.skillMeta}`}>{skill.backend}</span>
                  </div>
                  <div className={styles.skillBody}>
                    {desc && <div className={styles.skillDescription}>{desc}{desc.length >= 120 ? '...' : ''}</div>}
                    <div className={styles.skillStatus}>
                      <span className={`${styles.statusDot} ${styles.statusDotOnline}`} />
                      <span className={`${styles.mono} ${styles.skillStatusText}`}>AVAILABLE</span>
                      {hasInputs && <span className={styles.inputBadge}>{Object.keys(skill.inputs).length} INPUTS</span>}
                    </div>
                    <div className={styles.skillActions}>
                      <button
                        onClick={() => {
                          if (hasInputs) {
                            setSelectedSkillForExecution(skill);
                            setShowInputs(true);
                          } else if (isDestructiveSkill(skill)) {
                            setSkillToConfirm(skill);
                            setShowConfirm(true);
                          } else {
                            runSkill(skill.skill_id);
                          }
                        }}
                        disabled={running === skill.skill_id}
                        className={`${styles.executeButton} ${isDestructiveSkill(skill) ? styles.destructive : ''} ${running === skill.skill_id ? styles.running : ''}`}
                      >
                        {running === skill.skill_id ? <Loader2 size={12} className={styles.spin} /> : <Play size={12} />}
                        {hasInputs ? 'CONFIGURE & RUN' : isDestructiveSkill(skill) ? 'CONFIRM & RUN' : 'EXECUTE'}
                      </button>
                      <button
                        onClick={() => setSelectedSkill(selectedSkill?.skill_id === skill.skill_id ? null : skill)}
                        className={styles.infoButton}
                      >
                        <Info size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
            {filteredSkills.length === 0 && (
              <div className={styles.emptyState}>
                {loading ? 'Loading skills...' : skills.length === 0 ? 'No skills registered. Click refresh to discover.' : 'No skills match your filter.'}
              </div>
            )}
          </div>
        )}

        {/* Chains Grid */}
        {activeTab === 'chains' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--gap-md)' }}>
            {chains.map((chain, i) => (
              <div key={i} className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="panel__header">
                  <GitBranch size={12} color="var(--warning)" />
                  <span className="panel__title" style={{ fontSize: '0.7rem' }}>{chain.name || chain.id}</span>
                  <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.55rem', color: chain.cron ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {chain.cron ? `CRON: ${chain.cron}` : 'MANUAL'}
                  </span>
                </div>
                <div className="panel__body" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{chain.description || 'No description'}</div>
                  {chain.steps && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {chain.steps.map((step, j) => (
                        <div key={j} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 4, height: 4, borderRadius: '50%', background: step.status === 'ok' ? 'var(--accent)' : 'var(--text-muted)' }} />
                          <span className="mono" style={{ fontSize: '0.55rem' }}>{step.skill || step.name || step}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => runChain(chain.name || chain.id)}
                    disabled={running === (chain.name || chain.id)}
                    style={{
                      marginTop: 'auto', width: '100%', background: 'rgba(255,215,0,0.1)', border: '1px solid var(--warning)',
                      borderRadius: 6, padding: '0.5rem', color: 'var(--warning)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                      fontSize: '0.7rem', fontWeight: 700,
                    }}
                  >
                    {running === (chain.name || chain.id) ? <Loader2 size={12} className="spin" /> : <Play size={12} />}
                    RUN CHAIN
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sidebar: Skill Detail or Execution Log */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        {selectedSkill ? (
          <>
            <div className="panel__header">
              <Info size={14} color="var(--primary)" />
              <span className="panel__title">Skill Detail</span>
              <button onClick={() => setSelectedSkill(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}>×</button>
            </div>
            <div className="panel__body" style={{ flex: 1, overflowY: 'auto', fontSize: '0.65rem' }}>
              <div style={{ marginBottom: '1rem' }}>
                <div className="label" style={{ color: 'var(--primary)' }}>{selectedSkill.skill_name || selectedSkill.skill_id}</div>
                <div className="mono" style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: '0.55rem' }}>
                  ID: {selectedSkill.skill_id}
                </div>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <div className="label" style={{ fontSize: '0.6rem' }}>Description</div>
                <div style={{ marginTop: 4, color: 'var(--text)', lineHeight: 1.5 }}>{selectedSkill.description || 'No description available.'}</div>
              </div>
              <div style={{ marginBottom: '1rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div>
                  <div className="label" style={{ fontSize: '0.6rem' }}>Backend</div>
                  <div className="mono" style={{ color: 'var(--accent)', fontSize: '0.6rem' }}>{selectedSkill.backend || 'local'}</div>
                </div>
                <div>
                  <div className="label" style={{ fontSize: '0.6rem' }}>Source</div>
                  <div className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.6rem' }}>{selectedSkill.source_format || 'native'}</div>
                </div>
              </div>
              {selectedSkill.inputs && Object.keys(selectedSkill.inputs).length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <div className="label" style={{ fontSize: '0.6rem' }}>Input Parameters ({Object.keys(selectedSkill.inputs).length})</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                    {Object.entries(selectedSkill.inputs).map(([key, info]) => (
                      <div key={key} className="glass" style={{ padding: '0.4rem 0.6rem' }}>
                        <span className="mono" style={{ color: 'var(--primary)', fontSize: '0.6rem' }}>{key}</span>
                        <span className="mono" style={{ marginLeft: 8, color: 'var(--text-muted)', fontSize: '0.55rem' }}>{typeof info === 'string' ? info : JSON.stringify(info)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {selectedSkill.tools && selectedSkill.tools.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <div className="label" style={{ fontSize: '0.6rem' }}>Required Tools ({selectedSkill.tools.length})</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {selectedSkill.tools.map((t, i) => (
                      <span key={i} className="mono" style={{ background: 'rgba(0,184,255,0.1)', padding: '2px 6px', borderRadius: 3, fontSize: '0.55rem', color: 'var(--primary)' }}>{t}</span>
                    ))}
                  </div>
                </div>
              )}
              {selectedSkill.skill_path && (
                <div style={{ marginBottom: '1rem' }}>
                  <div className="label" style={{ fontSize: '0.6rem' }}>Skill Path</div>
                  <div className="mono" style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: '0.55rem', wordBreak: 'break-all' }}>{selectedSkill.skill_path}</div>
                </div>
              )}
              <button
                onClick={() => {
                  const hasInputs = selectedSkill.inputs && Object.keys(selectedSkill.inputs).length > 0;
                  if (hasInputs) {
                    setSelectedSkillForExecution(selectedSkill);
                    setShowInputs(true);
                  } else if (isDestructiveSkill(selectedSkill)) {
                    setSkillToConfirm(selectedSkill);
                    setShowConfirm(true);
                  } else {
                    runSkill(selectedSkill.skill_id);
                    setSelectedSkill(null);
                  }
                }}
                disabled={running === selectedSkill.skill_id}
                style={{
                  width: '100%', background: isDestructiveSkill(selectedSkill) ? 'rgba(255,69,0,0.1)' : 'rgba(0,184,255,0.1)',
                  border: `1px solid ${isDestructiveSkill(selectedSkill) ? 'var(--secondary)' : 'var(--primary)'}`,
                  borderRadius: 6, padding: '0.6rem',
                  color: isDestructiveSkill(selectedSkill) ? 'var(--secondary)' : 'var(--primary)',
                  cursor: 'pointer',
                  fontSize: '0.75rem', fontWeight: 700, marginTop: 'auto',
                }}
              >
                <Play size={14} style={{ display: 'inline', marginRight: 6 }} />
                {selectedSkill.inputs && Object.keys(selectedSkill.inputs).length > 0 ? 'CONFIGURE & RUN' : isDestructiveSkill(selectedSkill) ? 'CONFIRM & RUN' : 'EXECUTE THIS SKILL'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="panel__header">
              <Terminal size={14} color="var(--accent)" />
              <span className="panel__title">Execution Log</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-muted)' }}>{resultLog.length}</span>
            </div>
            <div className="panel__body mono" style={{ flex: 1, overflowY: 'auto', fontSize: '0.6rem' }}>
              {resultLog.length === 0 && <div className="label" style={{ textAlign: 'center', padding: '2rem' }}>Click a skill card to see details, or EXECUTE to run.</div>}
              {resultLog.map((entry, i) => (
                <div key={i} style={{ padding: '0.5rem', borderBottom: '1px solid var(--surface-border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ color: 'var(--text-muted)' }}>[{entry.ts}]</span>
                    <span style={{ color: entry.status === 'success' ? 'var(--accent)' : entry.status === 'failed' ? 'var(--secondary)' : 'var(--primary)' }}>
                      {entry.status === 'success' ? <CheckCircle size={10} style={{ display: 'inline' }} /> : entry.status === 'failed' ? <XCircle size={10} style={{ display: 'inline' }} /> : <Loader2 size={10} className="spin" style={{ display: 'inline' }} />}
                    </span>
                    <span style={{ fontWeight: 700 }}>{entry.skillId}</span>
                  </div>
                  <div style={{ color: 'var(--text-muted)', paddingLeft: 4 }}>{entry.msg}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

    </div>
  );
}

function tabStyle(active: boolean, large: boolean = false): string {
  return `${large ? styles.categoryTabLarge : styles.categoryTab} ${active ? styles.active : ''}`;
}

const createInputStyle = { flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.7rem', color: 'var(--text)', fontSize: '0.8rem' };
