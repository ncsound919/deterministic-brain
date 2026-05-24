import React, { useState, useCallback } from 'react';
import { BarChart3, FileText, TrendingUp, Target, Check, X, RefreshCw, Activity } from 'lucide-react';
import { getAcquisitionStatus, getAcquisitionLog, getAcquisitionProgress, getAcquisitionInsights, getAcquisitionMetrics } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

function MetricCard({ label, value, icon: Icon, color }) {
  return (
    <div style={{
      background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)',
      border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
        <Icon size={16} color={color} />
        <span>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function parseMarkdownTable(md) {
  const lines = md.split('\n').filter(l => l.trim() && l.startsWith('|'));
  if (lines.length < 3) return null;
  const headers = lines[0].split('|').map(h => h.trim()).filter(Boolean);
  const rows = lines.slice(2).map(line =>
    line.split('|').map(c => c.trim()).filter(Boolean)
  );
  return { headers, rows };
}

function parseInsightRows(md) {
  const lines = md.split('\n').filter(l => l.trim().startsWith('|'));
  const dataLines = lines.filter(l => l.includes('**') || l.match(/\d{4}-\d{2}-\d{2}/));
  return dataLines.map(l => l.split('|').map(c => c.trim()).filter(Boolean));
}

function parseDailyEntries(md) {
  const entries = [];
  const lines = md.split('\n');
  let current = [];
  for (const line of lines) {
    if (line.startsWith('### ')) {
      if (current.length) entries.push(current.join('\n'));
      current = [line];
    } else if (current.length) {
      current.push(line);
    }
  }
  if (current.length) entries.push(current.join('\n'));
  return entries;
}

export default function AcquisitionTracker() {
  const [status, setStatus] = useState(null);
  const [logContent, setLogContent] = useState('');
  const [progressContent, setProgressContent] = useState('');
  const [insightsContent, setInsightsContent] = useState('');
  const [metricsContent, setMetricsContent] = useState('');
  const [pageState, updatePageState] = usePageState('acquisition', { activeTab: 'overview' });

  const refresh = useCallback(async () => {
    const [s, log, prog, ins, met] = await Promise.all([
      getAcquisitionStatus(),
      getAcquisitionLog(),
      getAcquisitionProgress(),
      getAcquisitionInsights(),
      getAcquisitionMetrics(),
    ]);
    if (!s._error) setStatus(s);
    if (!log._error) setLogContent(log.content);
    if (!prog._error) setProgressContent(prog.content);
    if (!ins._error) setInsightsContent(ins.content);
    if (!met._error) setMetricsContent(met.content);
  }, []);

  useAutoRefresh(refresh, 10000, true);

  const progressTable = parseMarkdownTable(progressContent);
  const insightRows = parseInsightRows(insightsContent);
  const dailyEntries = parseDailyEntries(logContent);

  const filesOk = status?.files_present;
  const portfolioCount = progressTable?.rows?.length || 0;
  const insightCount = insightRows.length || 0;
  const entryCount = dailyEntries.length || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <Target size={24} color="#FF4500" />
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>Acquisition Tracker</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Portfolio health, daily ops, market intelligence</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {filesOk ? <Check size={14} color="var(--success)" /> : <X size={14} color="var(--danger)" />}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Tracker {filesOk ? 'Online' : 'Offline'}</span>
          <RefreshCw size={14} color="var(--text-muted)" style={{ cursor: 'pointer' }} onClick={refresh} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 'var(--gap-md)' }}>
        <MetricCard label="Portfolio Assets" value={portfolioCount} icon={BarChart3} color="var(--primary)" />
        <MetricCard label="Daily Entries" value={entryCount} icon={FileText} color="var(--accent)" />
        <MetricCard label="Insights Tracked" value={insightCount} icon={TrendingUp} color="var(--warning)" />
        <MetricCard label="Tracker Status" value={filesOk ? 'Active' : '—'} icon={Activity} color="var(--success)" />
      </div>

      {progressTable?.rows?.length > 0 && (
        <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Portfolio Deploy Readiness</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {progressTable.headers.map((h, i) => (
                    <th key={i} style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {progressTable.rows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    {row.map((cell, j) => (
                      <td key={j} style={{ padding: '6px 8px' }}>
                        {cell.includes('✅') ? <span style={{ color: 'var(--success)' }}>{cell}</span> :
                         cell.includes('⚠️') ? <span style={{ color: 'var(--warning)' }}>{cell}</span> :
                         cell.includes('**') ? <strong>{cell.replace(/\*\*/g, '')}</strong> : cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>
        {dailyEntries.length > 0 && (
          <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Daily Activity Log</div>
            <div style={{ maxHeight: 300, overflowY: 'auto', fontSize: 13, lineHeight: 1.6 }}>
              {dailyEntries.slice(0, 10).map((entry, i) => {
                const title = entry.split('\n')[0]?.replace(/^###\s*/, '') || '';
                const body = entry.split('\n').slice(1).filter(l => l.trim()).join('\n');
                return (
                  <div key={i} style={{ marginBottom: 12, padding: 8, background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--primary)', marginBottom: 4 }}>{title}</div>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-muted)' }}>{body}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {insightRows.length > 0 && (
          <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Market Intelligence</div>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Signal</th>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Implication</th>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {insightRows.slice(0, 10).map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      {row.slice(1, 4).map((cell, j) => (
                        <td key={j} style={{ padding: '4px 6px' }}>
                          {cell.replace(/\*\*/g, '').replace(/^\d{4}-\d{2}-\d{2}\s*/, '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
