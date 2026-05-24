import React, { useState, useEffect, useCallback } from 'react';
import { socialPosts, socialSchedule, socialPostDue, mediaGenerate, mediaLibrary, contentGenerateText } from '../api';
import { Send, Calendar, Clock, CheckCircle, AlertCircle, Sparkles, Image as ImageIcon, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { usePageState, useAutoRefresh } from '../stateManager';

const PLATFORMS = ['twitter', 'linkedin', 'bluesky', 'discord', 'facebook', 'instagram'];

export default function ContentSocial() {
  const [pageState, updatePageState] = usePageState('content-social', {
    platform: 'twitter',
    content: '',
    delay: 0,
    topic: '',
    selectedAsset: null,
  });
  const [posts, setPosts] = useState([]);
  const [posting, setPosting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [assets, setAssets] = useState([]);
  const requestSeq = React.useRef(0);

  const refresh = useCallback(async () => { 
    const seq = ++requestSeq.current;
    const [p, a] = await Promise.all([socialPosts(), mediaLibrary()]);
    if (seq !== requestSeq.current) return;
    if (!p._error) setPosts(p.posts || []); 
    if (!a._error) setAssets(a.files || []);
  }, []);
  
  useAutoRefresh(refresh, 15000, true);

  const handleSchedule = async () => {
    if (!pageState.content.trim()) return;
    setPosting(true);
    try {
      let finalContent = pageState.content;
      if (pageState.selectedAsset) {
        finalContent += `\n[Asset: ${pageState.selectedAsset.name}]`;
      }
      await socialSchedule(pageState.platform, finalContent, pageState.delay);
      updatePageState({ content: '', selectedAsset: null });
      await refresh();
    } finally {
      setPosting(false);
    }
  };

  const handlePostDue = async () => {
    setPosting(true);
    try {
      await socialPostDue();
      await refresh();
    } finally {
      setPosting(false);
    }
  };

  const generateAIContent = async () => {
    if (!pageState.topic) return;
    setGenerating(true);
    try {
      const res = await contentGenerateText(pageState.topic, pageState.platform);
      if (res.result || res.final_output) {
        updatePageState({ content: res.result?.output || res.final_output || "Generation failed." });
      }
    } finally {
      setGenerating(false);
    }
  };

  const generateAIImage = async () => {
    if (!pageState.topic) return;
    setGenerating(true);
    try {
      const res = await mediaGenerate({ prompt: `Vibrant social media graphic for: ${pageState.topic}`, type: 'image', aspect_ratio: '1:1' });
      if (!res._error) {
        setTimeout(refresh, 5000);
      }
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>
        {/* Composer */}
        <div className="glass panel">
          <div className="panel__header">
            <Send size={14} color="var(--primary)" />
            <span className="panel__title">Multi-Platform Composer</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <textarea 
              value={pageState.content} 
              onChange={e => updatePageState({ content: e.target.value })} 
              placeholder="What's happening in the business?"
              style={{ width: '100%', minHeight: 180, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--surface-border)', borderRadius: 12, padding: '1rem', color: 'var(--text)', fontFamily: "'Outfit', sans-serif", fontSize: '0.9rem', resize: 'vertical', lineHeight: 1.6 }} 
            />
            
            {pageState.selectedAsset && (
              <div className="glass" style={{ padding: '0.6rem', display: 'flex', alignItems: 'center', gap: 12, border: '1px solid var(--primary)', background: 'rgba(0,184,255,0.05)' }}>
                <div style={{ width: 40, height: 40, borderRadius: 6, background: '#111', overflow: 'hidden' }}>
                  <img src={`http://localhost:8000/exports/${pageState.selectedAsset.name}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div style={{ flex: 1, fontSize: '0.7rem' }}>
                  <div style={{ fontWeight: 800 }}>{pageState.selectedAsset.name}</div>
                  <div style={{ color: 'var(--text-muted)' }}>Image Attachment</div>
                </div>
                <button onClick={() => updatePageState({ selectedAsset: null })} style={{ background: 'none', border: 'none', color: 'var(--secondary)', cursor: 'pointer' }}><Trash2 size={16} /></button>
              </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', borderTop: '1px solid var(--surface-border)', paddingTop: '1rem' }}>
              <div style={{ flex: 1 }}>
                <div className="label" style={{ marginBottom: 4 }}>Destination</div>
                <select value={pageState.platform} onChange={e => updatePageState({ platform: e.target.value })}
                  style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.6rem 1rem', color: 'var(--text)', fontSize: '0.8rem' }}>
                  {PLATFORMS.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
                </select>
              </div>
              <div style={{ width: 100 }}>
                <div className="label" style={{ marginBottom: 4 }}>Schedule (m)</div>
                <input type="number" value={pageState.delay} onChange={e => updatePageState({ delay: +e.target.value })} min={0}
                  style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.6rem', color: 'var(--text)', fontSize: '0.8rem' }} />
              </div>
              <button 
                onClick={handleSchedule} 
                disabled={posting || !pageState.content.trim()}
                style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', border: 'none', borderRadius: 8, padding: '0.7rem 1.8rem', color: '#fff', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
              >
                {posting ? <Loader2 size={16} className="spin" /> : <Calendar size={16} />} 
                {pageState.delay > 0 ? 'SCHEDULE POST' : 'POST NOW'}
              </button>
            </div>
          </div>
        </div>

        {/* Content Queue */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <Clock size={14} color="var(--warning)" />
            <span className="panel__title">Automation Queue</span>
            <button onClick={handlePostDue} disabled={posting} style={{ marginLeft: 'auto', background: 'rgba(0,255,159,0.1)', border: '1px solid var(--accent)', borderRadius: 6, padding: '0.3rem 0.8rem', color: 'var(--accent)', fontSize: '0.6rem', fontWeight: 800, cursor: 'pointer' }}>
              PROCESS DUE POSTS
            </button>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              {posts.map((p, i) => (
                <div key={i} className="glass" style={{ padding: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <div style={{ width: 32, height: 32, borderRadius: 100, background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {p.status === 'posted' ? <CheckCircle size={16} color="var(--accent)" /> : <Clock size={16} color="var(--primary)" />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--primary)', fontWeight: 800, textTransform: 'uppercase' }}>{p.platform}</span>
                      <span className="label" style={{ fontSize: '0.55rem' }}>• {p.status.toUpperCase()}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', marginTop: 4, opacity: 0.8 }}>{p.content}</div>
                  </div>
                </div>
              ))}
              {posts.length === 0 && <div className="label" style={{ textAlign: 'center', padding: '2rem' }}>No posts in the queue.</div>}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
        {/* AI Content Factory */}
        <div className="glass panel" style={{ background: 'linear-gradient(135deg, rgba(255,0,212,0.05), rgba(0,184,255,0.05))' }}>
          <div className="panel__header">
            <Sparkles size={14} color="#FF00D4" />
            <span className="panel__title">AI Content Factory</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="label" style={{ fontSize: '0.65rem' }}>Campaign Topic / Concept</div>
            <input 
              value={pageState.topic}
              onChange={e => updatePageState({ topic: e.target.value })}
              placeholder="e.g. New SaaS launch, AI ethics, Bitcoin pump"
              style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={generateAIContent}
                disabled={generating || !pageState.topic}
                style={{ flex: 1, padding: '0.6rem', borderRadius: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', color: 'var(--text)', fontSize: '0.7rem', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                {generating ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} color="#FF00D4" />} DRAFT TEXT
              </button>
              <button 
                onClick={generateAIImage}
                disabled={generating || !pageState.topic}
                style={{ flex: 1, padding: '0.6rem', borderRadius: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', color: 'var(--text)', fontSize: '0.7rem', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                {generating ? <Loader2 size={12} className="spin" /> : <ImageIcon size={12} color="var(--primary)" />} GEN IMAGE
              </button>
            </div>
          </div>
        </div>

        {/* Assets Sidebar */}
        <div className="glass panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <ImageIcon size={14} color="var(--primary)" />
            <span className="panel__title">Marketing Assets</span>
            <button onClick={refresh} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><RefreshCw size={12} /></button>
          </div>
          <div className="panel__body" style={{ flex: 1, overflowY: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
              {assets.filter(a => a.name.endsWith('.png') || a.name.endsWith('.jpg')).map((a, i) => (
                <div 
                  key={i} 
                  onClick={() => updatePageState({ selectedAsset: a })}
                  className="glass" 
                  style={{ 
                    aspectRatio: '1/1', padding: 0, overflow: 'hidden', cursor: 'pointer', 
                    border: pageState.selectedAsset?.name === a.name ? '2px solid var(--primary)' : '1px solid transparent',
                    transition: 'all 0.2s'
                  }}
                >
                  <img src={`http://localhost:8000/exports/${a.name}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
