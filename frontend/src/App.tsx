import { useState, useEffect, useMemo } from 'react'

interface Stock {
  ticker: string; name: string; sector: string; market_cap_m: number;
  L_score: number; Q_score: number; R_score: number; P_score: number;
  LQRP_score: number; role: string; final_weight: number;
  gate_status: string; data_coverage_pct: number; announcement_scraped: number;
}

interface CompanyDetail {
  score: any; company: any; ratios: any[]; announcements: any[];
}

type SortKey = keyof Stock;
const API = import.meta.env.PROD ? 'https://stockanalysis-api.eranhor.workers.dev/api' : '/api';
const MODEL = 'lqrp_v2';

async function fetchJSON(path: string) {
  const sep = path.includes('?') ? '&' : '?';
  const r = await fetch(`${API}${path}${sep}model=${MODEL}`);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

function badgeColor(role: string) {
  switch (role) {
    case 'LiftoffEngine': return 'bg-purple-900/50 text-purple-300 border-purple-700';
    case 'CoreBridge': return 'bg-blue-900/50 text-blue-300 border-blue-700';
    case 'Anchor': return 'bg-green-900/50 text-green-300 border-green-700';
    case 'Optionality': return 'bg-amber-900/50 text-amber-300 border-amber-700';
    default: return 'bg-gray-800 text-gray-400 border-gray-700';
  }
}

function scoreColor(v: number) {
  if (v >= 70) return 'text-green-400';
  if (v >= 60) return 'text-yellow-400';
  if (v >= 50) return 'text-orange-400';
  return 'text-red-400';
}

function SubBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex items-center gap-2 mb-0.5">
      <span className="w-12 text-xs text-gray-400 text-right">{label}</span>
      <span className="w-8 text-xs tabular-nums">{value?.toFixed(0)}</span>
      <div className="flex-1 h-3 bg-gray-800 rounded overflow-hidden">
        <div className={`h-full rounded ${pct > 70 ? 'bg-green-600' : pct > 50 ? 'bg-yellow-600' : 'bg-red-600'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DetailDrawer({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchJSON(`/company/${ticker}`)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="text-gray-400">Loading {ticker}...</div>
      </div>
    </div>
  );

  if (!detail?.score) return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-2xl" onClick={e => e.stopPropagation()}>
        <div className="text-red-400">No data for {ticker}</div>
        <button onClick={onClose} className="mt-4 text-sm text-gray-500 hover:text-white">Close</button>
      </div>
    </div>
  );

  const s = detail.score;
  const c = detail.company || {};
  const ratios = detail.ratios?.[0] || {};
  const anns = detail.announcements || [];

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold">{ticker} <span className="text-gray-400 text-sm">{c.name}</span></h2>
            <p className="text-xs text-gray-500">{c.sector} · ${(c.market_cap/1e6)?.toFixed(0) || '?'}M</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-lg">✕</button>
        </div>

        {/* LQRP Score */}
        <div className="mb-4 p-3 bg-gray-950 rounded border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">LQRP SCORE</div>
          <div className="flex items-center gap-3">
            <span className={`text-2xl font-bold ${scoreColor(s.LQRP_score)}`}>{s.LQRP_score?.toFixed(1)}</span>
            <span className={`text-[10px] px-1 py-0.5 rounded border ${badgeColor(s.role)}`}>{s.role}</span>
            <span className="text-xs text-gray-500">{s.gate_status}</span>
          </div>
        </div>

        {/* Component scores */}
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">COMPONENT SCORES</div>
          <div className="grid grid-cols-4 gap-2">
            {[
              ['Liftoff', s.L_score, s.L1_score, s.L2_score, s.L3_score, s.L4_score, s.L5_score],
              ['Quality', s.Q_score, s.Q1_score, s.Q2_score, s.Q3_score, s.Q4_score],
              ['Robust', s.R_score, s.R1_score, s.R2_score, s.R3_score, s.R4_score, s.R5_score],
              ['Position', s.P_score, s.P1_score, s.P2_score, s.P3_score, s.P4_score],
            ].map(([label, total, ...subs]: any[]) => (
              <div key={label} className="p-2 bg-gray-950 rounded border border-gray-800">
                <div className="flex justify-between mb-1">
                  <span className="text-[10px] text-gray-400">{label}</span>
                  <span className={`text-xs font-bold ${scoreColor(total)}`}>{total?.toFixed(0)}</span>
                </div>
                {subs.map((v: number, i: number) => (
                  <div key={i} className="flex justify-between text-[10px]">
                    <span className="text-gray-600">{label[0]}{i+1}</span>
                    <span className="text-gray-400">{v?.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Formula */}
        <div className="mb-4 p-2 bg-gray-950 rounded border border-gray-800 text-[10px] text-gray-500">
          0.45×{s.L_score?.toFixed(0)} + 0.25×{s.Q_score?.toFixed(0)} + 0.20×{s.R_score?.toFixed(0)} + 0.10×{s.P_score?.toFixed(0)} = {s.LQRP_score?.toFixed(1)}
        </div>

        {/* Raw Financial Ratios */}
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">RAW DATA (from financial_ratios table)</div>
          <div className="grid grid-cols-2 gap-1 text-[10px]">
            {Object.entries(ratios)
              .filter(([k]) => !['ticker','period_end','data_quality'].includes(k))
              .map(([k, v]: any) => (
                <div key={k} className="flex justify-between p-1 bg-gray-950 rounded">
                  <span className="text-gray-500">{k}</span>
                  <span className="text-gray-300 tabular-nums">{typeof v === 'number' ? v.toFixed(3) : v || '—'}</span>
                </div>
              ))}
          </div>
        </div>

        {/* Announcements */}
        {anns.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-2">RECENT ANNOUNCEMENTS ({anns.length})</div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {anns.map((a: any, i: number) => (
                <div key={i} className="text-[10px] p-1 bg-gray-950 rounded flex justify-between">
                  <span className="text-gray-400">{a.date} · {a.type}</span>
                  <span className="text-gray-600 truncate ml-2">{a.headline?.slice(0, 60)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


export default function App() {
  const [rankings, setRankings] = useState<Stock[]>([]);
  const [portfolio, setPortfolio] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [sortKey, setSortKey] = useState<SortKey>('LQRP_score');
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc');
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchJSON('/rankings?limit=100'),
      fetchJSON('/portfolio'),
      fetchJSON('/health'),
    ]).then(([r, p, h]) => {
      setRankings(r);
      setPortfolio(p.holdings || []);
      setHealth(h);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const sorted = useMemo(() => {
    return [...rankings].sort((a, b) => {
      const va = a[sortKey] ?? 0, vb = b[sortKey] ?? 0;
      if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb as string) : (vb as string).localeCompare(va);
      return sortDir === 'asc' ? (va as number) - (vb as number) : (vb as number) - (va as number);
    });
  }, [rankings, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const SortHeader = ({ label, col }: { label: string; col: SortKey }) => (
    <th className="p-2 text-left cursor-pointer hover:text-white select-none" onClick={() => handleSort(col)}>
      {label} {sortKey === col ? (sortDir === 'desc' ? '↓' : '↑') : ''}
    </th>
  );

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading…</div>;

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6">
      {selectedTicker && <DetailDrawer ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />}

      {/* Header */}
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">StockAnalysis</h1>
          <span className="text-xs px-2 py-0.5 rounded border border-purple-800 bg-purple-900/30 text-purple-300">LQRP v2.0</span>
        </div>
        <p className="text-gray-500 text-sm mt-1">
          ASX Micro/Small Cap Rocket Screener
          {health && ` — ${health.stocks_scored} stocks scored`}
        </p>
      </header>

      {/* Portfolio Card */}
      {portfolio.length > 0 && (
        <div className="mb-6 p-4 border border-gray-800 rounded-lg bg-gray-900/50">
          <h2 className="text-sm font-semibold text-gray-400 mb-3">SUGGESTED PORTFOLIO</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {portfolio.map(h => (
              <div key={h.ticker} className="p-2 border border-gray-800 rounded bg-gray-900 cursor-pointer hover:border-gray-600" onClick={() => setSelectedTicker(h.ticker)}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="font-bold text-sm">{h.ticker}</span>
                  <span className={`text-[10px] px-1 py-0.5 rounded border ${badgeColor(h.role)}`}>{h.role}</span>
                </div>
                <div className="text-xs text-gray-500">{h.name?.slice(0, 20)}</div>
                <div className="flex justify-between text-xs mt-1">
                  <span className={scoreColor(h.LQRP_score)}>{h.LQRP_score.toFixed(1)}</span>
                  <span className="text-gray-400">{h.final_weight.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rankings Table */}
      <div className="overflow-x-auto border border-gray-800 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-gray-900 text-gray-400 uppercase tracking-wider">
            <tr>
              <SortHeader label="#" col="LQRP_score" />
              <SortHeader label="Ticker" col="ticker" />
              <th className="p-2 text-left">Sector</th>
              <SortHeader label="MCap" col="market_cap_m" />
              <SortHeader label="LQRP" col="LQRP_score" />
              <SortHeader label="L" col="L_score" />
              <SortHeader label="Q" col="Q_score" />
              <SortHeader label="R" col="R_score" />
              <SortHeader label="P" col="P_score" />
              <SortHeader label="Role" col="role" />
              <SortHeader label="Wt" col="final_weight" />
              <SortHeader label="Cov%" col="data_coverage_pct" />
              <th className="p-2 text-left">Scraped</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s, i) => (
              <tr key={s.ticker} onClick={() => setSelectedTicker(s.ticker)}
                  className={`border-t border-gray-800 hover:bg-gray-900/50 cursor-pointer ${i % 2 === 0 ? 'bg-transparent' : 'bg-gray-950/30'}`}>
                <td className="p-2 text-gray-500">{i + 1}</td>
                <td className="p-2 font-medium hover:text-white">{s.ticker}</td>
                <td className="p-2 text-gray-400 max-w-[120px] truncate">{s.sector}</td>
                <td className="p-2 text-gray-400">${s.market_cap_m?.toFixed(0)}M</td>
                <td className={`p-2 font-bold ${scoreColor(s.LQRP_score)}`}>{s.LQRP_score?.toFixed(1)}</td>
                <td className="p-2">{s.L_score?.toFixed(0)}</td>
                <td className="p-2">{s.Q_score?.toFixed(0)}</td>
                <td className="p-2">{s.R_score?.toFixed(0)}</td>
                <td className="p-2">{s.P_score?.toFixed(0)}</td>
                <td className="p-2"><span className={`text-[10px] px-1 py-0.5 rounded border ${badgeColor(s.role)}`}>{s.role}</span></td>
                <td className="p-2 text-gray-400">{s.final_weight > 0.5 ? s.final_weight?.toFixed(1) + '%' : '—'}</td>
                <td className="p-2 text-gray-500">{s.data_coverage_pct}%</td>
                <td className="p-2">{s.announcement_scraped ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="mt-6 text-xs text-gray-600">
        <p>Click a ticker for detail view. Coverage = % of sub-factor weight with non-proxy data.</p>
        <p className="mt-1">Model: 0.45L + 0.25Q + 0.20R + 0.10P</p>
      </footer>
    </div>
  );
}