import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, DollarSign, Briefcase, MessageSquare, Settings,
  Radio, ChevronRight, BarChart3, Zap, Image, Globe, Folder, Rocket, Music,
  Brain, Code, Timer, Heart, MousePointer, FolderGit2, Clock, Cpu, Target
} from 'lucide-react';
import { AppProvider, useAppContext, useKeyboardShortcuts, sessionManager } from './stateManager';
import ToastNotifications from './components/ToastNotifications';

import CommandCenter from './pages/CommandCenter';
import SportsBetting from './pages/SportsBetting';
import FinancePage from './pages/Finance';
import ContentSocial from './pages/ContentSocial';
import SettingsPage from './pages/Settings';
import MediaStudio from './pages/MediaStudio';
import IntelHub from './pages/IntelHub';
import Draymond from './pages/Draymond';
import ResearchLab from './pages/ResearchLab';
import Portal from './pages/Portal';
import BrainOps from './pages/BrainOps';
import SkillMarketplace from './pages/SkillMarketplace';
import CronManager from './pages/CronManager';
import SystemsHealth from './pages/SystemsHealth';
import BrowserAutomation from './pages/BrowserAutomation';
import GitHubManager from './pages/GitHubManager';
import ChatPage from './pages/Chat';
import ModelsPage from './pages/Models';
import AcquisitionTracker from './pages/AcquisitionTracker';

const PAGES = [
  // ── Overview ──────────────────────────────────────────
  { id: 'command', label: 'Dashboard', icon: Activity, color: 'var(--primary)', section: 'Overview' },
  
  // ── Operations ────────────────────────────────────────
  { id: 'brain', label: 'Agents', icon: Brain, color: '#00B8FF', section: 'Operations' },
  { id: 'skills', label: 'Skills', icon: Code, color: '#FF00D4', section: 'Operations' },
  { id: 'cron', label: 'Scheduler', icon: Timer, color: '#00F0FF', section: 'Operations' },
  { id: 'systems', label: 'Health', icon: Heart, color: '#FF6B6B', section: 'Operations' },
  { id: 'chat', label: 'Chat', icon: MessageSquare, color: '#00FF9F', section: 'Operations' },
  { id: 'models', label: 'Models', icon: Cpu, color: '#A78BFA', section: 'Operations' },
  
  // ── Knowledge ─────────────────────────────────────────
  { id: 'research', label: 'Research', icon: Briefcase, color: '#7B68EE', section: 'Knowledge' },
  { id: 'intel', label: 'Signals', icon: Globe, color: '#A78BFA', section: 'Knowledge' },
  { id: 'portal', label: 'Library', icon: Folder, color: '#00CED1', section: 'Knowledge' },
  
  // ── Business ──────────────────────────────────────────
  { id: 'social', label: 'Content', icon: MessageSquare, color: '#FF6B6B', section: 'Business' },
  { id: 'media', label: 'Media', icon: Image, color: '#FFD700', section: 'Business' },
  { id: 'betting', label: 'Betting', icon: BarChart3, color: 'var(--accent)', section: 'Business' },
  { id: 'finance', label: 'Finance', icon: DollarSign, color: 'var(--warning)', section: 'Business' },
  { id: 'acquisition', label: 'Acquisition', icon: Target, color: '#FF4500', section: 'Business' },
  
  // ── Tools ─────────────────────────────────────────────
  { id: 'browser', label: 'Browser', icon: MousePointer, color: '#00FF9F', section: 'Tools' },
  { id: 'github', label: 'GitHub', icon: FolderGit2, color: '#FF8C00', section: 'Tools' },
  { id: 'draymond', label: 'Agents Registry', icon: Radio, color: '#FF69B4', section: 'Tools' },
  
  // ── System ────────────────────────────────────────────
  { id: 'settings', label: 'Settings', icon: Settings, color: 'var(--text-muted)', section: 'System' },
];

const PAGE_MAP = {
  command: CommandCenter,
  brain: BrainOps,
  skills: SkillMarketplace,
  cron: CronManager,
  systems: SystemsHealth,
  media: MediaStudio,
  intel: IntelHub,
  browser: BrowserAutomation,
  github: GitHubManager,
  draymond: Draymond,
  research: ResearchLab,
  social: ContentSocial,
  betting: SportsBetting,
  finance: FinancePage,
  acquisition: AcquisitionTracker,
  portal: Portal,
  settings: SettingsPage,
  chat: ChatPage,
  models: ModelsPage,
};

const HASH_TO_PAGE = Object.fromEntries(PAGES.map(p => [p.id, p.id]));
function getPageFromHash() {
  const hash = window.location.hash.replace('#', '');
  return HASH_TO_PAGE[hash] || 'command';
}

function AppContent() {
  const [active, setActive] = useState(getPageFromHash);
  const [collapsed, setCollapsed] = useState(false);
  const { session, preferences, actionLog } = useAppContext();

  useEffect(() => {
    const onHashChange = () => setActive(getPageFromHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Track visits
  useEffect(() => {
    sessionManager.incrementVisit();
    actionLog.add('session_start', { page: active });
  }, []);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    'cmd+1': () => navigateTo('command'),
    'cmd+2': () => navigateTo('brain'),
    'cmd+3': () => navigateTo('cron'),
    'cmd+4': () => navigateTo('skills'),
    'cmd+5': () => navigateTo('betting'),
    'cmd+6': () => navigateTo('social'),
    'cmd+7': () => navigateTo('systems'),
    'cmd+8': () => navigateTo('settings'),
    'cmd+k': () => setCollapsed(c => !c),
    'escape': () => navigateTo('command'),
  });

  const navigateTo = (pageId) => {
    window.location.hash = `#${pageId}`;
    setActive(pageId);
    actionLog.add('navigate', { from: active, to: pageId });
  };

  const ActivePage = PAGE_MAP[active] || CommandCenter;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-main)' }}>
      {/* ─── Toast Notifications ─────────────────────── */}
      <ToastNotifications />

      {/* ─── Sidebar ─────────────────────────────────── */}
      <nav style={{
        width: collapsed ? 70 : 240,
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        background: 'rgba(5, 5, 10, 0.98)',
        borderRight: '1px solid var(--surface-border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.2rem 0',
        flexShrink: 0,
        overflow: 'hidden',
        boxShadow: '10px 0 30px rgba(0,0,0,0.5)',
        zIndex: 100
      }}>
        {/* Logo */}
        <div style={{ padding: '0.5rem 1.2rem 2rem', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }} onClick={() => setCollapsed(c => !c)}>
          <div style={{ 
            width: 32, height: 32, borderRadius: 8, 
            background: 'linear-gradient(135deg, var(--primary), var(--accent))',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Zap size={20} color="#fff" />
          </div>
          {!collapsed && (
            <span style={{
              fontSize: '1rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.15em',
              background: 'linear-gradient(135deg, #fff, #888)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              whiteSpace: 'nowrap',
            }}>AETHER OS</span>
          )}
        </div>

        {/* Nav Items — Grouped by Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto', flex: 1 }}>
          {(() => {
            const sections = {};
            PAGES.forEach(p => {
              if (!sections[p.section]) sections[p.section] = [];
              sections[p.section].push(p);
            });
            return Object.entries(sections).map(([sectionName, pages]) => (
              <div key={sectionName} style={{ marginBottom: '0.5rem' }}>
                {!collapsed && (
                  <div style={{
                    padding: '0.6rem 1.4rem 0.3rem',
                    fontSize: '0.6rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    color: 'var(--text-muted)',
                    opacity: 0.5,
                  }}>
                    {sectionName}
                  </div>
                )}
                {pages.map(page => (
                  <button
                    key={page.id}
                    onClick={() => navigateTo(page.id)}
                    aria-current={active === page.id ? 'page' : undefined}
                    title={page.label}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: collapsed ? '0.7rem 0' : '0.7rem 1.4rem',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      background: active === page.id ? 'rgba(255,255,255,0.03)' : 'transparent',
                      border: 'none',
                      color: active === page.id ? 'var(--text)' : 'var(--text-muted)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      width: '100%',
                      position: 'relative'
                    }}
                  >
                    {active === page.id && (
                      <motion.div layoutId="nav-pill" style={{ position: 'absolute', left: 0, width: 3, height: '100%', background: page.color }} />
                    )}
                    <page.icon size={18} color={active === page.id ? page.color : 'var(--text-muted)'} style={{ opacity: active === page.id ? 1 : 0.6 }} />
                    {!collapsed && <span style={{ fontSize: '0.78rem', fontWeight: active === page.id ? 700 : 500, whiteSpace: 'nowrap', letterSpacing: '0.02em' }}>{page.label}</span>}
                  </button>
                ))}
              </div>
            ));
          })()}
        </div>

        {/* Status */}
        <div style={{ marginTop: 'auto', padding: '1rem 1.4rem', borderTop: '1px solid var(--surface-border)' }}>
          {!collapsed ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="status-dot status-dot--online" />
              <span className="mono" style={{ fontSize: '0.65rem', color: 'var(--accent)', fontWeight: 800 }}>ONLINE</span>
            </div>
          ) : <div className="status-dot status-dot--online" style={{ margin: '0 auto' }} />}
        </div>
      </nav>

      {/* ─── Main Content ────────────────────────────── */}
      <main style={{ flex: 1, padding: 'var(--gap-lg)', overflow: 'auto', maxHeight: '100vh', position: 'relative' }}>
        {/* Ambient background glow */}
        <div style={{ position: 'fixed', top: '-10%', right: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(0, 184, 255, 0.03) 0%, transparent 70%)', pointerEvents: 'none' }} />
        
        {/* Page Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--gap-lg)' }}>
          <div>
            <h1 style={{
              fontSize: '1.8rem', fontWeight: 900,
              color: 'var(--text)',
              letterSpacing: '-0.02em'
            }}>{PAGES.find(p => p.id === active)?.label}</h1>
            <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4, opacity: 0.6 }}>
              {active.toUpperCase() || '—'}
            </div>
          </div>
          <div className="glass" style={{ padding: '0.6rem 1.2rem', fontSize: '0.7rem', fontFamily: "'JetBrains Mono', monospace", borderRadius: 12, border: '1px solid var(--surface-border)', minWidth: 180, whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={14} color="var(--primary)" />
            {new Date().toLocaleTimeString() || '—'}
          </div>
        </div>

        {/* Page Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          >
            <ActivePage />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
