import React, { useState, useEffect, useCallback } from 'react';
import { tradingPrice, tradingBalance, tradingExecute } from '../api';
import { DollarSign, TrendingUp, RefreshCw, Bitcoin, Wallet, ArrowUpRight, ArrowDownRight, Activity, Loader2, CheckCircle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { usePageState, useAutoRefresh } from '../stateManager';

const COINS = ['BTC-USD','ETH-USD','SOL-USD','DOGE-USD','XRP-USD','ADA-USD'];

export default function FinancePage() {
  const [prices, setPrices] = useState({});
  const [history, setHistory] = useState([]);
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [actionStatus, setActionStatus] = useState(null);
  const [pageState, updatePageState] = usePageState('finance', {
    selectedCoin: 'BTC-USD',
    tradeSide: 'BUY',
    tradeAmount: '',
  });
  const requestSeq = React.useRef(0);

  const fetchAll = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    try {
      const [bal, ...priceResults] = await Promise.all([
        tradingBalance(),
        ...COINS.map(c => tradingPrice(c))
      ]);

      if (seq !== requestSeq.current) return;

      if (!bal._error) setBalance(bal);
      
      const pMap = {};
      priceResults.forEach((res, i) => {
        if (!res._error) pMap[COINS[i]] = res.price;
      });
      setPrices(pMap);
      setHistory(prev => [...prev.slice(-29), { time: new Date().toLocaleTimeString(), ...pMap }]);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useAutoRefresh(fetchAll, 30000, true);

  const handleExecute = async () => {
    if (!pageState.tradeAmount || isNaN(pageState.tradeAmount)) return;
    setExecuting(true);
    const res = await tradingExecute(pageState.selectedCoin, pageState.tradeSide, parseFloat(pageState.tradeAmount));
    if (!res._error) {
      setActionStatus(`Order Executed: ${pageState.tradeSide} ${pageState.tradeAmount} ${pageState.selectedCoin}`);
      setTimeout(() => setActionStatus(null), 5000);
      fetchAll();
    }
    setExecuting(false);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 'var(--gap-md)', height: 'calc(100vh - 180px)' }}>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)', overflowY: 'auto' }}>
        {/* Market Overview */}
        <div className="glass panel">
          <div className="panel__header">
            <Activity size={14} color="var(--primary)" />
            <span className="panel__title">Real-Time Market Feed</span>
            <button onClick={fetchAll} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>
          <div className="panel__body">
             <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--gap-sm)', marginBottom: '1.5rem' }}>
              {COINS.map(c => (
                <div key={c} className="glass" style={{ padding: '0.8rem', cursor: 'pointer', border: pageState.selectedCoin === c ? '1px solid var(--primary)' : '1px solid var(--surface-border)', background: pageState.selectedCoin === c ? 'rgba(0,184,255,0.05)' : 'transparent' }}
                  onClick={() => updatePageState({ selectedCoin: c })}>
                  <div className="label" style={{ fontSize: '0.6rem' }}>{c.replace('-USD','')}</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: pageState.selectedCoin === c ? 'var(--primary)' : 'var(--text)' }}>
                    {prices[c] !== undefined ? `$${Number(prices[c]).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" tick={{ fill: '#666', fontSize: 10 }} axisLine={false} />
                  <YAxis tick={{ fill: '#666', fontSize: 10 }} axisLine={false} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8 }} />
                  <Area type="monotone" dataKey={pageState.selectedCoin} stroke="var(--primary)" fill="url(#grad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Assets & Wallet */}
        <div className="glass panel">
          <div className="panel__header">
            <Wallet size={14} color="var(--accent)" />
            <span className="panel__title">Wallet Inventory</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
              {balance?.assets?.map(asset => (
                <div key={asset.symbol} className="glass" style={{ padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '1rem' }}>{asset.symbol}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{asset.amount} units</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--accent)' }}>${asset.value_usd.toLocaleString()}</div>
                    <div className="label" style={{ fontSize: '0.55rem' }}>EST. VALUE</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
        {/* Total Balance Card */}
        <div className="glass" style={{ padding: '1.5rem', background: 'linear-gradient(135deg, rgba(0,184,255,0.1), rgba(0,255,159,0.05))', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', right: -20, top: -20, opacity: 0.1 }}><DollarSign size={100} /></div>
          <div className="label">Total Liquidity (USD)</div>
          <div style={{ fontSize: '2.2rem', fontWeight: 900, marginTop: 4 }}>${balance?.balance_usd?.toLocaleString() || '0.00'}</div>
          <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--accent)', fontSize: '0.7rem', fontWeight: 700 }}>
              <ArrowUpRight size={14} /> +2.4%
            </div>
            <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>SESSION PNL</div>
          </div>
        </div>

        {/* Trade Execution */}
        <div className="glass panel" style={{ flex: 1 }}>
          <div className="panel__header">
            <TrendingUp size={14} color="var(--primary)" />
            <span className="panel__title">Trade Execution</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={() => updatePageState({ tradeSide: 'BUY' })}
                style={{ flex: 1, padding: '0.8rem', borderRadius: 8, background: pageState.tradeSide === 'BUY' ? 'var(--accent)' : 'rgba(255,255,255,0.05)', border: 'none', color: pageState.tradeSide === 'BUY' ? '#000' : 'var(--text)', fontWeight: 800, cursor: 'pointer' }}
              >BUY</button>
              <button 
                onClick={() => updatePageState({ tradeSide: 'SELL' })}
                style={{ flex: 1, padding: '0.8rem', borderRadius: 8, background: pageState.tradeSide === 'SELL' ? 'var(--secondary)' : 'rgba(255,255,255,0.05)', border: 'none', color: pageState.tradeSide === 'SELL' ? '#fff' : 'var(--text)', fontWeight: 800, cursor: 'pointer' }}
              >SELL</button>
            </div>

            <div>
              <div className="label" style={{ marginBottom: 8 }}>Asset</div>
              <div className="glass" style={{ padding: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 800 }}>{pageState.selectedCoin}</span>
                <span className="mono" style={{ color: 'var(--primary)' }}>${prices[pageState.selectedCoin]?.toLocaleString()}</span>
              </div>
            </div>

            <div>
              <div className="label" style={{ marginBottom: 8 }}>Amount ({pageState.selectedCoin.replace('-USD','')})</div>
              <input 
                type="number"
                value={pageState.tradeAmount}
                onChange={e => updatePageState({ tradeAmount: e.target.value })}
                placeholder="0.00"
                style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 8, padding: '1rem', color: 'var(--text)', fontSize: '1.2rem', fontWeight: 800 }}
              />
            </div>

            <div style={{ marginTop: 'auto' }}>
              {actionStatus && (
                <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--accent)', marginBottom: '1rem', textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                  <CheckCircle size={12} /> {actionStatus}
                </div>
              )}
              <button 
                onClick={handleExecute}
                disabled={executing || !tradeAmount}
                style={{ 
                  width: '100%', padding: '1.2rem', borderRadius: 12, 
                  background: pageState.tradeSide === 'BUY' ? 'linear-gradient(135deg, var(--accent), #00CC7A)' : 'linear-gradient(135deg, var(--secondary), #CC0044)', 
                  border: 'none', color: pageState.tradeSide === 'BUY' ? '#000' : '#fff', fontWeight: 900, fontSize: '1rem', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                  boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                  opacity: executing || !pageState.tradeAmount ? 0.5 : 1
                }}
              >
                {executing ? <Loader2 size={20} className="spin" /> : `${pageState.tradeSide} ${pageState.selectedCoin.replace('-USD','')}`}
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
