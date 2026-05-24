import React from 'react';
import { motion } from 'framer-motion';
import { 
  Terminal, Shield, Zap, Activity, Cpu, Check, X, Clock,
  TrendingUp, TrendingDown, ChevronRight, Radio, Loader2
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════
   MetricCard – Top-level KPI cards
   ═══════════════════════════════════════════════════════════════ */
export const MetricCard = ({ label, value, trend, trendLabel, icon: Icon, color = 'var(--primary)' }) => (
  <div className="glass metric-card">
    <div className="metric-card__icon-wrap" style={{ background: `${color}15` }}>
      <Icon size={18} color={color} />
    </div>
    <div className="label">{label}</div>
    <div className="metric-card__value">{value}</div>
    {trend !== undefined && (
      <div className={`metric-card__trend ${trend >= 0 ? 'metric-card__trend--up' : 'metric-card__trend--down'}`} style={{ whiteSpace: 'nowrap' }}>
        {trend >= 0 ? <TrendingUp size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> : <TrendingDown size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />}
        {Math.abs(trend)}% {trendLabel || ''}
      </div>
    )}
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   ArcGauge – SVG arc gauge for confidence/thresholds
   ═══════════════════════════════════════════════════════════════ */
export const ArcGauge = ({ label, value, max = 100, color = 'var(--primary)', size = 100 }) => {
  const pct = Math.min(value / max, 1);
  const r = 40;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.75; // 270 degree arc
  const offset = arc - arc * pct;

  return (
    <div className="gauge-wrap glass">
      <div className="gauge-label">{label}</div>
      <svg width={size} height={size} viewBox="0 0 100 100">
        {/* background arc */}
        <circle
          cx="50" cy="50" r={r}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7"
          strokeDasharray={`${arc} ${circ}`}
          strokeLinecap="round"
          transform="rotate(135 50 50)"
        />
        {/* value arc */}
        <motion.circle
          cx="50" cy="50" r={r}
          fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={`${arc} ${circ}`}
          strokeLinecap="round"
          transform="rotate(135 50 50)"
          initial={{ strokeDashoffset: arc }}
          animate={{ strokeDashoffset: offset }}
          transition={{ type: 'spring', stiffness: 40, damping: 15 }}
        />
      </svg>
      <div className="gauge-value" style={{ color, marginTop: -20 }}>{typeof value === 'number' ? value.toFixed(value < 1 ? 2 : 0) : value}</div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   SparklineBars – Mini bar chart
   ═══════════════════════════════════════════════════════════════ */
export const SparklineBars = ({ data = [], color = 'var(--primary)', height = 40 }) => {
  const max = Math.max(...data, 1);
  return (
    <div className="sparkline-bars" style={{ height }}>
      {data.map((v, i) => (
        <motion.div
          key={i}
          className="sparkline-bar"
          style={{ background: color }}
          initial={{ height: 0 }}
          animate={{ height: `${(v / max) * 100}%` }}
          transition={{ delay: i * 0.03, type: 'spring', stiffness: 80 }}
        />
      ))}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   ComponentCard – Shows status of an engine component
   ═══════════════════════════════════════════════════════════════ */
export const ComponentCard = ({ name, status, meta }) => (
  <motion.div 
    className="comp-card"
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ type: 'spring', stiffness: 100 }}
  >
    <div>
      <span className={`comp-card__dot ${status === 'active' ? 'comp-card__dot--active' : 'comp-card__dot--inactive'}`} />
      <span className="comp-card__name">{name}</span>
    </div>
    <div className="comp-card__meta">{meta}</div>
  </motion.div>
);

/* ═══════════════════════════════════════════════════════════════
   CronQueuePanel – Shows the work queue / cron tasks
   ═══════════════════════════════════════════════════════════════ */
export const CronQueuePanel = ({ tasks = [] }) => (
  <div className="glass panel" style={{ height: '100%' }}>
    <div className="panel__header">
      <Clock size={14} color="var(--primary)" />
      <span className="panel__title">Work Queue / Cron Schedule</span>
      <span className="label" style={{ marginLeft: 'auto' }}>{tasks.length} tasks</span>
    </div>
    <div className="panel__body">
      {tasks.length === 0 && <div className="label">No tasks loaded</div>}
      {tasks.map((t, i) => (
        <div className="queue-item" key={i}>
          <span className={`queue-item__badge ${t.enabled ? 'queue-item__badge--cron' : 'queue-item__badge--disabled'}`}>
            {t.cron || 'N/A'}
          </span>
          <div className="queue-item__info">
            <div className="queue-item__name">{t.id}</div>
            <div className="queue-item__desc">{t.description}</div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   ResultsBank – Shows completed work results
   ═══════════════════════════════════════════════════════════════ */
export const ResultsBank = ({ results = [] }) => (
  <div className="glass panel" style={{ height: '100%' }}>
    <div className="panel__header">
      <Check size={14} color="var(--accent)" />
      <span className="panel__title">Results Bank</span>
      <span className="label" style={{ marginLeft: 'auto' }}>{results.length} entries</span>
    </div>
    <div className="panel__body">
      {results.length === 0 && (
        <div className="feed-empty">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
            style={{ marginBottom: 12 }}
          >
            <Loader2 size={28} color="var(--primary)" />
          </motion.div>
          <div className="feed-empty__title">No results yet</div>
          <div className="feed-empty__sub">Submit a query below to populate results</div>
        </div>
      )}
      {[...results].reverse().map((r, i) => {
        const res = r.result || {};
        const status = res.status || 'unknown';
        return (
          <div className="result-row" key={i}>
            <div className={`result-row__status ${status === 'success' ? 'result-row__status--success' : 'result-row__status--failed'}`} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="result-row__query">{res.query || 'N/A'}</div>
              <div className="result-row__detail">
                {res.action_taken || res.skill_executed || res.message || JSON.stringify(res).slice(0, 80)}
              </div>
            </div>
            <div className="result-row__time">{new Date(r.ts * 1000).toLocaleTimeString()}</div>
          </div>
        );
      })}
    </div>
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   EventFeed – Live event log terminal
   ═══════════════════════════════════════════════════════════════ */
export const EventFeed = ({ events = [] }) => (
  <div className="glass panel" style={{ height: '100%' }}>
    <div className="panel__header">
      <Terminal size={14} color="var(--accent)" />
      <span className="panel__title">Live Event Feed</span>
    </div>
    <div className="panel__body mono" style={{ fontSize: '0.72rem' }}>
      {events.length === 0 && (
        <div className="feed-empty">
          <motion.div
            animate={{ opacity: [0.2, 0.6, 0.2] }}
            transition={{ repeat: Infinity, duration: 2 }}
            style={{ marginBottom: 12 }}
          >
            <Radio size={28} color="var(--accent)" />
          </motion.div>
          <div className="feed-empty__title">Waiting for events…</div>
          <div className="feed-empty__sub">Event bus listening — events will stream here</div>
        </div>
      )}
      {[...events].reverse().slice(0, 40).map((e, i) => (
        <div className="event-line" key={i}>
          <span className="event-line__ts">[{new Date(e.ts * 1000).toLocaleTimeString()}]</span>{' '}
          <span className="event-line__type">{e.type?.toUpperCase()}</span>{' '}
          <span className="event-line__data">{JSON.stringify(e.data).slice(0, 120)}</span>
        </div>
      ))}
      <span className="cursor-blink" />
    </div>
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   QueryInput – Interactive input bar
   ═══════════════════════════════════════════════════════════════ */
export const QueryInput = ({ onSubmit, disabled }) => {
  const [query, setQuery] = React.useState('');
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query.trim());
      setQuery('');
    }
  };
  return (
    <form className="glass input-bar" onSubmit={handleSubmit}>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Send a query to the Hybrid Engine…"
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !query.trim()}>Execute</button>
    </form>
  );
};
