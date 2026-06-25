import { useState, useEffect, useMemo } from 'react'

interface Stock {
  ticker: string; name: string; sector: string; market_cap_m: number;
  L_score: number; Q_score: number; R_score: number; P_score: number;
  LQRP_score: number; role: string; final_weight: number;
  gate_status: string; data_coverage_pct: number; announcement_scraped: number;
}

interface PortfolioHolding extends Stock {}

type SortKey = keyof Stock;

// API base — proxied to worker in dev, same origin in prod
const API = '/api';

async function fetchJSON(path: string) {
  const r = await fetch(`${API}${path}`);
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

export default function App() {
  const [rankings, setRankings] = useState<Stock[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioHolding[]>([]);
  const [health, setHealth] = useState<{stocks_scored: number} | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('LQRP_score');
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc');
  const [loading, setLoading] = useState(true);

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

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading...</div>;

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6">
      {/* Header */}
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">
          LQRP <span className="text-gray-500">v2.0</span>
        </h1>
        <p className="text-gray-500 text-sm">
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
              <div key={h.ticker} className="p-2 border border-gray-800 rounded bg-gray-900">
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
              <tr key={s.ticker} className={`border-t border-gray-800 hover:bg-gray-900/50 ${i % 2 === 0 ? 'bg-transparent' : 'bg-gray-950/30'}`}>
                <td className="p-2 text-gray-500">{i + 1}</td>
                <td className="p-2 font-medium">{s.ticker}</td>
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

      {/* Footer */}
      <footer className="mt-6 text-xs text-gray-600">
        <p>Data coverage shows % of sub-factor weight with non-proxy data. "Scraped" = ASX announcements processed.</p>
        <p className="mt-1">LQRP v2.0 — Model: 0.45L + 0.25Q + 0.20R + 0.10P</p>
      </footer>
    </div>
  );
}