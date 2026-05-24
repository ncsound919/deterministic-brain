import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Beaker, FlaskConical, FileText, Send, Loader2, CheckCircle, AlertCircle, Database, Zap } from 'lucide-react';
import { labExperiment, labPaper } from '../api';
import { usePageState } from '../stateManager';

export default function ResearchLab() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [pageState, updatePageState] = usePageState('research-lab', {
    hypothesis: '',
    history: [],
  });

  const runExperiment = async () => {
    if (!pageState.hypothesis) return;
    setRunning(true);
    setResults(null);
    
    try {
      const id = `exp-${Date.now()}`;
      const data = await labExperiment(id, pageState.hypothesis, 'default-biotech-v1');
      setResults(data);
      updatePageState({ history: [data, ...pageState.history] });
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const generatePaper = async (id) => {
    try {
      const data = await labPaper(id);
      setResults(prev => prev ? { ...prev, paper_path: data.paper_path } : data);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 'var(--gap-lg)', height: 'calc(100vh - 180px)' }}>
      
      {/* ─── Experiment Chamber ────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-lg)' }}>
        <div className="glass panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <Beaker size={14} color="var(--primary)" />
            <span className="panel__title">BlackMind Experiment Chamber</span>
          </div>
          <div className="panel__body" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="label">Research Hypothesis / Inquiry</div>
              <textarea 
                value={pageState.hypothesis}
                onChange={(e) => updatePageState({ hypothesis: e.target.value })}
                placeholder="e.g. Evaluate the correlation between BCL2 expression and drug resistance in SaaS-pocalypse market volatility..."
                style={{ 
                  width: '100%', minHeight: 120, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--surface-border)', 
                  borderRadius: 8, padding: '1rem', color: 'var(--text)', fontSize: '0.9rem', resize: 'none', outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '1rem' }}>
              <div style={{ flex: 1 }}>
                <div className="label">Target Dataset</div>
                <div className="glass" style={{ padding: '0.8rem', display: 'flex', alignItems: 'center', gap: 10, border: '1px solid var(--surface-border)' }}>
                  <Database size={14} color="var(--primary)" />
                  <span className="mono" style={{ fontSize: '0.7rem' }}>CORE_GENOMIC_V1.CSV</span>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div className="label">Pipeline Mode</div>
                <div className="glass" style={{ padding: '0.8rem', display: 'flex', alignItems: 'center', gap: 10, border: '1px solid var(--surface-border)' }}>
                  <Zap size={14} color="var(--accent)" />
                  <span className="mono" style={{ fontSize: '0.7rem' }}>DETERMINISTIC_XAI</span>
                </div>
              </div>
            </div>

            <button 
              onClick={runExperiment}
              disabled={running || !pageState.hypothesis}
              style={{ 
                marginTop: '1rem', padding: '1rem', background: 'var(--primary)', color: '#000', 
                border: 'none', borderRadius: 8, fontWeight: 900, cursor: 'pointer', 
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                opacity: (running || !pageState.hypothesis) ? 0.5 : 1
              }}
            >
              {running ? <Loader2 className="spin" size={18} /> : <FlaskConical size={18} />}
              EXECUTE SCIENTIFIC PIPELINE
            </button>

            {results && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass" style={{ padding: '1.5rem', marginTop: '1rem', border: '1px solid var(--accent)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: '1rem' }}>
                  <CheckCircle size={18} color="var(--accent)" />
                  <span style={{ fontWeight: 900, color: 'var(--accent)' }}>EXPERIMENT CONCLUDED</span>
                  <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.6rem' }}>CONFIDENCE: {results.results.confidence_score * 100}%</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <div className="label" style={{ fontSize: '0.55rem' }}>SIGNIFICANT SIGNALS</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                      {results.results.significant_genes.map(g => <span key={g} className="mono" style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4, fontSize: '0.65rem' }}>{g}</span>)}
                    </div>
                  </div>
                  <div>
                    <div className="label" style={{ fontSize: '0.55rem' }}>COMPUTE EFFICIENCY</div>
                    <div className="mono" style={{ color: 'var(--primary)', fontSize: '0.8rem', marginTop: 4 }}>{results.compute_efficiency}</div>
                  </div>
                </div>
                <button 
                   onClick={() => generatePaper(results.experiment_id)}
                   style={{ marginTop: '1.5rem', width: '100%', background: 'none', border: '1px solid var(--primary)', color: 'var(--primary)', padding: '0.5rem', borderRadius: 4, cursor: 'pointer', fontWeight: 800, fontSize: '0.7rem' }}
                >
                   GENERATE SCIENTIFIC PAPER (.MD)
                </button>
              </motion.div>
            )}
          </div>
        </div>
      </div>

      {/* ─── Lab History ──────────────────────────────── */}
      <div className="glass panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel__header">
          <FileText size={14} color="var(--text-muted)" />
          <span className="panel__title">Research History</span>
        </div>
        <div className="panel__body" style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
           {pageState.history.length === 0 && <div style={{ opacity: 0.3, textAlign: 'center', padding: '2rem', fontSize: '0.7rem' }}>NO RECENT EXPERIMENTS</div>}
           {pageState.history.map((h, i) => (
             <div key={i} className="glass" style={{ padding: '0.8rem', marginBottom: '0.8rem', border: '1px solid var(--surface-border)' }}>
               <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginBottom: 4 }}>{h.experiment_id}</div>
               <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: 8 }}>{h.hypothesis.substring(0, 60)}...</div>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                 <span className="mono" style={{ fontSize: '0.55rem', color: 'var(--accent)' }}>{h.results.confidence_score * 100}% CONF</span>
                 <button onClick={() => generatePaper(h.experiment_id)} style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '0.6rem', cursor: 'pointer', fontWeight: 900 }}>RE-GENERATE PAPER</button>
               </div>
             </div>
           ))}
        </div>
      </div>

    </div>
  );
}
