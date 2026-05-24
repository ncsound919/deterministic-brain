import React, { useState, useEffect, useCallback } from 'react';
import { bettingOdds, bettingEnhanced, bettingPrizePicks, bettingTrends, bettingPlace } from '../api';
import { TrendingUp, DollarSign, Target, Search, RefreshCw, Loader2, CheckCircle } from 'lucide-react';
import { usePageState, useAutoRefresh } from '../stateManager';

const sports = ['basketball_nba','americanfootball_nfl','baseball_mlb','icehockey_nhl','soccer_epl','mma_mixed_martial_arts'];

export default function SportsBetting() {
  const [pageState, updatePageState] = usePageState('sports-betting', {
    sport: 'basketball_nba',
    bankroll: 1000,
    trendPlayer: '',
  });
  const [odds, setOdds] = useState([]);
  const [enhanced, setEnhanced] = useState(null);
  const [prizeData, setPrizeData] = useState(null);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState({});
  const [actionStatus, setActionStatus] = useState(null);

  const fetchOdds = useCallback(async () => {
    setLoading(true);
    const [o, e] = await Promise.all([bettingOdds(pageState.sport), bettingEnhanced(pageState.sport, pageState.bankroll)]);
    if (!o._error) setOdds(o.lines || []);
    if (!e._error) setEnhanced(e);
    setLoading(false);
  }, [pageState.sport, pageState.bankroll]);

  useAutoRefresh(fetchOdds, 30000, true);

  const fetchPrize = async () => { const d = await bettingPrizePicks(); if (!d._error) setPrizeData(d); };
  const fetchTrends = async () => {
    if (!pageState.trendPlayer) return;
    const d = await bettingTrends(pageState.trendPlayer);
    if (!d._error) setTrends(d);
  };

  useEffect(() => { fetchOdds(); fetchPrize(); }, [fetchOdds]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
      {/* Controls */}
      <div className="glass" style={{ padding: '1.2rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Sport</div>
          <select value={pageState.sport} onChange={e => updatePageState({ sport: e.target.value })}
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.5rem 1rem', color: 'var(--text)', fontSize: '0.8rem' }}>
            {sports.map(s => <option key={s} value={s}>{s.replace(/_/g,' ').toUpperCase()}</option>)}
          </select>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Bankroll ($)</div>
          <input type="number" value={pageState.bankroll} onChange={e => updatePageState({ bankroll: +e.target.value })}
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.5rem 1rem', color: 'var(--text)', width: 120 }} />
        </div>
        <button onClick={fetchOdds} style={{ marginTop: 16, background: 'linear-gradient(135deg, var(--primary), #0090CC)', border: 'none', borderRadius: 8, padding: '0.6rem 1.5rem', color: '#fff', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={14} /> {loading ? 'Loading…' : 'Refresh Odds'}
        </button>
        {actionStatus && (
          <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--accent)', marginTop: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle size={14} /> {actionStatus}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>
        {/* Odds Table */}
        <div className="glass panel" style={{ maxHeight: 500 }}>
          <div className="panel__header"><DollarSign size={14} color="var(--accent)" /><span className="panel__title">Live Odds ({odds.length} lines)</span></div>
          <div className="panel__body" style={{ fontSize: '0.72rem' }}>
            {odds.length === 0 && <div className="label">No odds loaded — check API key or try another sport.</div>}
            {odds.slice(0, 30).map((line, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ fontWeight: 600 }}>{line.home_team} vs {line.away_team}</span>
                <span className="mono" style={{ color: 'var(--primary)' }}>{line.commence_time ? new Date(line.commence_time).toLocaleDateString() : '—'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Enhanced Analysis */}
        <div className="glass panel" style={{ maxHeight: 500 }}>
          <div className="panel__header"><Target size={14} color="var(--secondary)" /><span className="panel__title">Enhanced Analysis</span></div>
          <div className="panel__body mono" style={{ fontSize: '0.7rem', whiteSpace: 'pre-wrap' }}>
            {enhanced ? JSON.stringify(enhanced, null, 2).slice(0, 3000) : 'Loading analysis…'}
          </div>
        </div>

        {/* PrizePicks */}
        <div className="glass panel" style={{ maxHeight: 600, display: 'flex', flexDirection: 'column' }}>
          <div className="panel__header">
            <TrendingUp size={14} color="var(--warning)" />
            <span className="panel__title">PrizePicks Board ({prizeData?.total_props || 0})</span>
            <button onClick={fetchPrize} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <RefreshCw size={12} className={loading ? 'spin' : ''} />
            </button>
          </div>
          <div className="panel__body" style={{ flex: 1, overflowY: 'auto' }}>
            {prizeData?.props?.slice(0, 50).map((p, i) => (
              <div key={i} className="glass" style={{ padding: '0.8rem', marginBottom: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid rgba(255,255,255,0.03)' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 800, fontSize: '0.85rem' }}>{p.player_name || p.name}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'flex', gap: 8, marginTop: 2 }}>
                    <span>{p.market.toUpperCase()}</span>
                    <span className="mono" style={{ color: 'var(--accent)', fontWeight: 800 }}>{p.line}</span>
                  </div>
                </div>
                <button 
                  onClick={async () => {
                    setActing(prev => ({ ...prev, [`bet-${i}`]: true }));
                    const res = await bettingPlace(p.player_name || p.name, p.market, p.line);
                    if (!res._error) {
                      setActionStatus(`Bet placed for ${p.player_name || p.name}! Check CEO terminal for trace.`);
                      setTimeout(() => setActionStatus(null), 5000);
                    }
                    setActing(prev => ({ ...prev, [`bet-${i}`]: false }));
                  }}
                  disabled={acting[`bet-${i}`]}
                  style={{ 
                    background: 'rgba(0,255,159,0.1)', border: '1px solid var(--accent)', borderRadius: 6, 
                    padding: '0.4rem 0.8rem', color: 'var(--accent)', fontSize: '0.65rem', fontWeight: 800, 
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 
                  }}
                >
                  {acting[`bet-${i}`] ? <Loader2 size={12} className="spin" /> : 'PLACE BET'}
                </button>
              </div>
            )) || <div className="label" style={{ textAlign: 'center', padding: '2rem' }}>No PrizePicks data loaded</div>}
          </div>
        </div>

        {/* Trend Lookup */}
        <div className="glass panel" style={{ maxHeight: 400 }}>
          <div className="panel__header"><Search size={14} color="var(--primary)" /><span className="panel__title">Player Trend Lookup</span></div>
          <div className="panel__body">
            <div style={{ display: 'flex', gap: 8, marginBottom: '1rem' }}>
              <input value={pageState.trendPlayer} onChange={e => updatePageState({ trendPlayer: e.target.value })} placeholder="Player name…"
                style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '0.5rem', color: 'var(--text)', fontSize: '0.8rem' }} />
              <button onClick={fetchTrends}
                style={{ background: 'var(--primary)', border: 'none', borderRadius: 8, padding: '0.5rem 1rem', color: '#fff', fontWeight: 700, cursor: 'pointer' }}>Search</button>
            </div>
            {trends && <pre className="mono" style={{ fontSize: '0.65rem', whiteSpace: 'pre-wrap', color: 'var(--text-muted)' }}>{JSON.stringify(trends, null, 2).slice(0, 2000)}</pre>}
          </div>
        </div>
      </div>
    </div>
  );
}
