import React, { useState, useEffect, useCallback } from 'react';
import { Globe, Cpu, DollarSign, Zap, ExternalLink, RefreshCw, Filter, MessageSquare, Search, FileText, CheckCircle, Loader2 } from 'lucide-react';
import { newsUnified, newsSummarize, newsAction, healthCheck, opportunitiesList } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

export default function IntelHub() {
  const [categories, setCategories] = useState(null);
  const [pageState, updatePageState] = usePageState('intel-hub', {
    activeCat: 'ai',
    summaries: {},
    actionStatus: null,
  });
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState({});
  const [cacheSize, setCacheSize] = useState(0);
  const [opportunities, setOpportunities] = useState([]);
  const requestSeq = React.useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    try {
      const [d, h, o] = await Promise.all([newsUnified(), healthCheck(), opportunitiesList()]);
      if (seq !== requestSeq.current) return;
      if (!d._error) setCategories(d.categories);
      if (!h._error) setCacheSize(h.cache_size || 0);
      if (!o._error) setOpportunities(o.opportunities || []);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useAutoRefresh(refresh, 30000, true);

  const handleSummarize = async (item, i) => {
    setActing(prev => ({ ...prev, [`sum-${i}`]: true }));
    const res = await newsSummarize(item.title, item.url);
    if (!res._error) {
      updatePageState({ summaries: { ...pageState.summaries, [i]: res.summary } });
    }
    setActing(prev => ({ ...prev, [`sum-${i}`]: false }));
  };

  const handleAction = async (item, i, action) => {
    setActing(prev => ({ ...prev, [`act-${i}-${action}`]: true }));
    const res = await newsAction(action, item.title);
    if (!res._error) {
      updatePageState({ actionStatus: `Success: ${action.toUpperCase()} completed for "${item.title.substring(0, 20)}..."` });
      setTimeout(() => updatePageState({ actionStatus: null }), 5000);
    }
    setActing(prev => ({ ...prev, [`act-${i}-${action}`]: false }));
  };

  const items = categories?.[pageState.activeCat] || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>
      {/* Left Column: Category Tabs + News Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflow: 'hidden' }}>
        {/* Category Tabs & Global Controls */}
        <div className="glass" style={{ padding: '0.8rem', display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <Filter size={14} color="var(--primary)" style={{ marginLeft: '0.5rem' }} />
          {['ai', 'tech', 'finance', 'general'].map(cat => (
            <button
              key={cat}
              onClick={() => updatePageState({ activeCat: cat })}
              style={{
                padding: '0.5rem 1.2rem',
                borderRadius: 8,
                background: pageState.activeCat === cat ? 'rgba(0, 184, 255, 0.1)' : 'transparent',
                border: '1px solid',
                borderColor: pageState.activeCat === cat ? 'var(--primary)' : 'transparent',
                color: pageState.activeCat === cat ? 'var(--primary)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                transition: 'all 0.2s'
              }}
            >
              {cat}
            </button>
          ))}
          
          <div className="glass" style={{ padding: '0.2rem 0.6rem', fontSize: '0.6rem', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Zap size={10} fill="var(--accent)" /> {cacheSize} CACHED
          </div>

          {pageState.actionStatus && (
            <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--accent)', marginLeft: '1rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <CheckCircle size={12} /> {pageState.actionStatus}
            </div>
          )}

          <button onClick={refresh} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>

        {/* News Grid (scrollable) */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 'var(--gap-md)' }}>
            {items.map((item, i) => (
              <div key={i} className="glass panel" style={{ display: 'flex', flexDirection: 'column', transition: 'all 0.3s ease' }}>
                <div className="panel__header">
                  {pageState.activeCat === 'ai' && <Cpu size={12} color="var(--primary)" />}
                  {pageState.activeCat === 'finance' && <DollarSign size={12} color="var(--accent)" />}
                  {pageState.activeCat === 'tech' && <Zap size={12} color="var(--warning)" />}
                  {pageState.activeCat === 'general' && <Globe size={12} color="var(--text-muted)" />}
                  <span className="panel__title" style={{ fontSize: '0.65rem', textTransform: 'uppercase' }}>{item.source || 'Intel Report'}</span>
                  <span className="mono" style={{ fontSize: '0.55rem', marginLeft: 'auto', opacity: 0.5 }}>{item.publishedAt?.split('T')[0] || 'LIVE'}</span>
                </div>
                <div className="panel__body" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', lineHeight: 1.4 }}>{item.title}</div>
                  
                  {!pageState.summaries[i] ? (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>{item.summary || item.description}</div>
                  ) : (
                    <div style={{ padding: '0.8rem', background: 'rgba(0,184,255,0.05)', borderRadius: 8, fontSize: '0.8rem', borderLeft: '3px solid var(--primary)', lineHeight: 1.6 }}>
                      <div className="label" style={{ marginBottom: 6, fontSize: '0.55rem' }}>AI SUMMARY</div>
                      {pageState.summaries[i]}
                    </div>
                  )}

                  {/* Action Toolbar */}
                  <div style={{ marginTop: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap', paddingTop: '0.5rem', borderTop: '1px solid var(--surface-border)' }}>
                    <button 
                      onClick={() => handleSummarize(item, i)}
                      disabled={acting[`sum-${i}`]}
                      style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 6, padding: '0.4rem', color: 'var(--text)', fontSize: '0.65rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
                    >
                      {acting[`sum-${i}`] ? <Loader2 size={12} className="spin" /> : <FileText size={12} />} SUMMARIZE
                    </button>
                    
                    <button 
                      onClick={() => handleAction(item, i, 'social')}
                      disabled={acting[`act-${i}-social`]}
                      style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 6, padding: '0.4rem', color: 'var(--text)', fontSize: '0.65rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
                    >
                      {acting[`act-${i}-social`] ? <Loader2 size={12} className="spin" /> : <MessageSquare size={12} />} DRAFT POST
                    </button>

                    <button 
                      onClick={() => handleAction(item, i, 'research')}
                      disabled={acting[`act-${i}-research`]}
                      style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 6, padding: '0.4rem', color: 'var(--text)', fontSize: '0.65rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
                    >
                      {acting[`act-${i}-research`] ? <Loader2 size={12} className="spin" /> : <Search size={12} />} RESEARCH
                    </button>

                    <a href={item.url} target="_blank" rel="noreferrer" style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,184,255,0.1)', borderRadius: 6, color: 'var(--primary)' }}>
                      <ExternalLink size={14} />
                    </a>
                  </div>
                </div>
              </div>
            ))}
            {items.length === 0 && !loading && (
              <div className="glass" style={{ gridColumn: '1/-1', padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No intel gathered for this sector yet. The background collectors are active.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Opportunity Scout Sidebar */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <Zap size={14} color="var(--accent)" />
          <span className="panel__title">Opportunity Scout</span>
          <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text-muted)' }}>Autonomous Agent</span>
        </div>
        
        <div className="panel__body" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {opportunities.length === 0 ? (
            <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 1rem' }}>
              Scanning news and goals for market opportunities...
            </div>
          ) : (
            opportunities.map(opp => (
              <div key={opp.id} className="glass" style={{ padding: '1rem', borderLeft: '3px solid var(--accent)' }}>
                <div className="mono" style={{ fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.5rem', color: 'var(--primary)' }}>
                  {opp.title}
                </div>
                <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.4' }}>
                  {opp.description}
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div className="mono" style={{ fontSize: '0.6rem', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 1 }}>Action Plan</div>
                  {opp.action_plan.map((step, i) => (
                    <div key={i} className="mono" style={{ fontSize: '0.65rem', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent)' }} /> {step}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
