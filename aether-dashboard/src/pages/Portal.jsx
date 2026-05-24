import React, { useState, useEffect, useCallback } from 'react';
import { FolderUp, UserPlus, Upload, FileJson, CheckCircle, AlertCircle, Loader2, Database, FileText, ChevronRight, RefreshCw, Trash2, Code } from 'lucide-react';
import { uploadAgent, uploadFolder, knowledgeStats, knowledgeSynthesize } from '../api';
import { usePageState } from '../stateManager';

export default function Portal() {
  const [pageState, updatePageState] = usePageState('portal', {
    agentName: '',
    agentCode: '',
    folderName: '',
    status: null,
  });
  const [uploading, setUploading] = useState(false);
  const [inventory, setInventory] = useState(null);
  const requestSeq = React.useRef(0);

  const refreshInventory = useCallback(async () => {
    const seq = ++requestSeq.current;
    const res = await knowledgeStats();
    if (seq !== requestSeq.current) return;
    if (!res._error) setInventory(res);
  }, []);

  useEffect(() => { 
    refreshInventory(); 
    return () => { requestSeq.current++; };
  }, [refreshInventory]);

  const handleAgentUpload = async () => {
    if (!pageState.agentName || !pageState.agentCode) return;
    setUploading(true);
    const r = await uploadAgent(pageState.agentName, pageState.agentCode);
    if (!r._error) {
      updatePageState({ status: { type: 'success', msg: `Agent ${pageState.agentName} is now LIVE.` }, agentName: '', agentCode: '' });
      refreshInventory();
    } else {
      updatePageState({ status: { type: 'error', msg: 'Upload failed.' } });
    }
    setUploading(false);
  };

  const handleFolderUpload = async () => {
    if (!pageState.folderName) return;
    setUploading(true);
    const r = await uploadFolder(pageState.folderName);
    if (!r._error) {
      updatePageState({ status: { type: 'success', msg: `Folder ${pageState.folderName} queued for ingestion.` }, folderName: '' });
      refreshInventory();
    } else {
      updatePageState({ status: { type: 'error', msg: 'Ingestion failed.' } });
    }
    setUploading(false);
  };

  const handleSynthesize = async (tag) => {
    setUploading(true);
    const r = await knowledgeSynthesize(tag);
    if (!r._error) {
      updatePageState({ status: { type: 'success', msg: `Briefing synthesized: ${r.title}` } });
      refreshInventory();
    } else {
      updatePageState({ status: { type: 'error', msg: 'Synthesis failed.' } });
    }
    setUploading(false);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>
        {/* Agent Hot-Swap */}
        <div className="glass panel">
          <div className="panel__header">
            <UserPlus size={14} color="var(--primary)" />
            <span className="panel__title">Sovereign Skill Injection</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div className="label" style={{ marginBottom: 6 }}>Skill ID</div>
                <input
                  value={pageState.agentName}
                  onChange={(e) => updatePageState({ agentName: e.target.value })}
                  placeholder="e.g. data_cruncher"
                  style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
                />
              </div>
            </div>
            
            <div>
              <div className="label" style={{ marginBottom: 6 }}>Source Code (Python)</div>
              <textarea
                value={pageState.agentCode}
                onChange={(e) => updatePageState({ agentCode: e.target.value })}
                placeholder="class SkillImplementation: ..."
                style={{ width: '100%', height: 350, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '1rem', color: '#00ff9f', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', resize: 'vertical' }}
              />
            </div>

            <button
              onClick={handleAgentUpload}
              disabled={uploading || !pageState.agentName || !pageState.agentCode}
              style={{
                width: '100%',
                background: 'linear-gradient(135deg, var(--primary), var(--accent))',
                border: 'none', borderRadius: 8, padding: '1.2rem',
                color: '#fff', fontWeight: 900, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                boxShadow: '0 10px 20px rgba(0,0,0,0.2)',
                opacity: uploading || !pageState.agentName || !pageState.agentCode ? 0.5 : 1
              }}
            >
              {uploading ? <Loader2 size={20} className="spin" /> : <Upload size={20} />} HOT-DEPLOY SOVEREIGN SKILL
            </button>
          </div>
        </div>

        {/* Folder Ingestion */}
        <div className="glass panel">
          <div className="panel__header">
            <FolderUp size={14} color="var(--accent)" />
            <span className="panel__title">Knowledge Ingestion</span>
          </div>
          <div className="panel__body">
            <div className="label" style={{ marginBottom: '1rem' }}>Local Path Ingestion</div>
            <div style={{ display: 'flex', gap: '0.8rem' }}>
              <input
                value={pageState.folderName}
                onChange={(e) => updatePageState({ folderName: e.target.value })}
                placeholder="C:/Business/Internal/Reports_2024"
                style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.8rem', color: 'var(--text)', fontSize: '0.8rem' }}
              />
              <button
                onClick={handleFolderUpload}
                disabled={uploading || !pageState.folderName}
                style={{
                  background: 'var(--accent)', border: 'none', borderRadius: 8, padding: '0.8rem 1.5rem',
                  color: '#000', fontWeight: 900, cursor: 'pointer', opacity: uploading || !pageState.folderName ? 0.5 : 1
                }}
              >
                INGEST
              </button>
            </div>
            {pageState.status && (
              <div style={{ marginTop: '1.5rem', padding: '1rem', borderRadius: 8, background: pageState.status.type === 'success' ? 'rgba(0,255,159,0.05)' : 'rgba(255,107,107,0.05)', border: `1px solid ${pageState.status.type === 'success' ? 'var(--accent)' : 'var(--secondary)'}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                {pageState.status.type === 'success' ? <CheckCircle size={16} color="var(--accent)" /> : <AlertCircle size={16} color="var(--secondary)" />}
                <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{pageState.status.msg}</span>
                <button onClick={() => updatePageState({ status: null })} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>✕</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Knowledge Sidebar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
        <div className="glass panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <Database size={14} color="var(--primary)" />
            <span className="panel__title">Knowledge Inventory</span>
            <button onClick={refreshInventory} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><RefreshCw size={14} /></button>
          </div>
          <div className="panel__body" style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
            <div className="label" style={{ margin: '1.5rem 0 0.8rem', fontSize: '0.6rem' }}>TAGS & TAXONOMY</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {inventory?.tags?.map((tag, i) => (
                <div key={i} className="glass" style={{ padding: '0.4rem 0.6rem', display: 'flex', alignItems: 'center', gap: 8, border: '1px solid var(--surface-border)' }}>
                  <span className="mono" style={{ fontSize: '0.6rem', color: 'var(--primary)' }}>#{tag}</span>
                  <button 
                    onClick={() => handleSynthesize(tag)}
                    disabled={uploading}
                    style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.55rem', fontWeight: 900 }}
                  >
                    SYNTHESIZE
                  </button>
                </div>
              ))}
            </div>

            <div className="label" style={{ margin: '1.5rem 0 0.8rem', fontSize: '0.6rem' }}>ACTIVE SKILLS</div>
            {inventory?.skills?.map((skill, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.4rem', borderBottom: '1px solid var(--surface-border)' }}>
                <Code size={12} color="var(--accent)" />
                <span className="mono" style={{ fontSize: '0.65rem' }}>{skill}</span>
                <div className="status-dot status-dot--online" style={{ marginLeft: 'auto', width: 4, height: 4 }} />
              </div>
            ))}
            
            {(!inventory || inventory.collections?.length === 0) && (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                Brain is empty. Ingest data to begin building intelligence.
              </div>
            )}
          </div>
        </div>

        {/* System Stats */}
        <div className="glass" style={{ padding: '1rem' }}>
          <div className="label">Total Vector Storage</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 900, color: 'var(--primary)', marginTop: 4 }}>
            {inventory?.total_points?.toLocaleString() || 0} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 500 }}>Points</span>
          </div>
          <div className="mono" style={{ fontSize: '0.6rem', marginTop: 8, opacity: 0.6 }}>ENGINE: QDRANT_HYBRID_V2</div>
        </div>
      </div>

    </div>
  );
}
