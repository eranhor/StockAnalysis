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

const FACTORS: Record<string, {name: string; desc: string}> = {
  L1: {name:'Valuation Compression', desc:'Rerating room from current valuation (lower multiple = more room)'},
  L2: {name:'Growth Velocity', desc:'How fast the business is currently scaling'},
  L3: {name:'Growth Acceleration', desc:'Whether growth is improving or slowing'},
  L4: {name:'Operating Leverage', desc:'Capacity for revenue to convert to earnings'},
  L5: {name:'Commercial Maturity', desc:'Likelihood of commercial conversion in 12-24 months'},
  Q1: {name:'Revenue Quality Mix', desc:'Repeatability of revenue (recurring vs project-based)'},
  Q2: {name:'Gross Margin Level+Trend', desc:'Economic quality and direction'},
  Q3: {name:'Cash Conversion', desc:'Whether reported progress becomes cash'},
  Q4: {name:'Commercial Proof Scale', desc:'How commercially substantial the business is'},
  R1: {name:'Cash Runway', desc:'Capacity to survive without fresh capital'},
  R2: {name:'Leverage & Liquidity', desc:'Financial stress and flexibility'},
  R3: {name:'Dilution Risk', desc:'Capital markets dependency'},
  R4: {name:'Asset Intensity', desc:'Operational complexity from asset intensity'},
  R5: {name:'Cash Flow Stability', desc:'Consistency of cash generation'},
  P1: {name:'Insider Net Buying', desc:'Whether insiders are adding exposure'},
  P2: {name:'Register Quality', desc:'Supportive holder mix'},
  P3: {name:'Underfollowed / Crowding', desc:'How crowded or undiscovered the stock is'},
  P4: {name:'Supply Overhang', desc:'Near-term dilution pressure'},
}

const RATIO_LABELS: Record<string, string> = {
  gross_margin: 'Gross Margin',
  ebitda_margin: 'EBITDA Margin',
  net_margin: 'Net Margin',
  revenue_growth_yoy: 'Revenue Growth YoY',
  revenue_growth_qoq: 'Revenue Growth QoQ',
  revenue_growth_accel: 'Growth Acceleration',
  ocf_to_revenue: 'OCF / Revenue',
  fcf_to_revenue: 'FCF / Revenue',
  current_ratio: 'Current Ratio',
  debt_to_equity: 'Debt / Equity',
  nd_to_ebitda: 'Net Debt / EBITDA',
  revenue_volatility_cv: 'Revenue Volatility CV',
  share_count_growth_yoy: 'Share Growth YoY',
  share_count_growth_6m: 'Share Growth 6m',
  cash_burn_rate: 'Cash Burn Rate',
  cash_runway_months: 'Cash Runway (months)',
  ebitda_margin_change: 'EBITDA Margin Change',
  capex_to_revenue: 'CapEx / Revenue',
  ppe_to_revenue: 'PP&E / Revenue',
  avg_daily_volume: 'Avg Daily Volume',
  share_turnover: 'Share Turnover',
}
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

function SubBar({ label, value, desc, max=100 }: { label: string; value: number; desc?: string; max?: number }) {
  const pct = Math.min(100, Math.abs(value) / max * 100);
  return (
    <div className="mb-1">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-300 font-medium min-w-[220px]">{label}</span>
        <span className={`text-xs font-bold tabular-nums min-w-[28px] ${value >= 70 ? 'text-green-400' : value >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{value?.toFixed(0)}</span>
        <div className="flex-1 h-2 bg-gray-800 rounded overflow-hidden">
          <div className={`h-full rounded ${value >= 70 ? 'bg-green-600' : value >= 50 ? 'bg-yellow-600' : 'bg-red-600'}`} style={{width:`${pct}%`}}/>
        </div>
      </div>
      {desc && <div className="text-[10px] text-gray-600 ml-[248px]">{desc}</div>}
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
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="text-gray-400">Loading {ticker}...</div>
      </div>
    </div>
  );

  if (!detail?.score) return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-3xl" onClick={e => e.stopPropagation()}>
        <div className="text-red-400">No data for {ticker}</div>
        <button onClick={onClose} className="mt-4 text-sm text-gray-500 hover:text-white">Close</button>
      </div>
    </div>
  );

  const s = detail.score;
  const c = detail.company || {};
  const ratios = detail.ratios?.[0] || {};
  const anns = detail.announcements || [];

  const groups: [string, string, any[]][] = [
    ['L', 'Liftoff (45%)', [['L1','L1_score'],['L2','L2_score'],['L3','L3_score'],['L4','L4_score'],['L5','L5_score']]],
    ['Q', 'Quality (25%)', [['Q1','Q1_score'],['Q2','Q2_score'],['Q3','Q3_score'],['Q4','Q4_score']]],
    ['R', 'Robustness (20%)', [['R1','R1_score'],['R2','R2_score'],['R3','R3_score'],['R4','R4_score'],['R5','R5_score']]],
    ['P', 'Positioning (10%)', [['P1','P1_score'],['P2','P2_score'],['P3','P3_score'],['P4','P4_score']]],
  ];

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold">{ticker} <span className="text-gray-400 text-sm">{c.name}</span></h2>
            <p className="text-xs text-gray-500">{c.sector} · ${(c.market_cap/1e6)?.toFixed(0) || '?'}M mc · ${(c.enterprise_value/1e6)?.toFixed(0) || '?'}M ev</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-lg">✕</button>
        </div>

        <div className="mb-4 p-3 bg-gray-950 rounded border border-gray-800">
          <div className="flex items-center gap-3">
            <span className={`text-3xl font-bold ${scoreColor(s.LQRP_score)}`}>{s.LQRP_score?.toFixed(1)}</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">LQRP</span>
                <span className={`text-[10px] px-1 py-0.5 rounded border ${badgeColor(s.role)}`}>{s.role}</span>
                <span className="text-[10px] text-gray-500">{s.gate_status}</span>
              </div>
              <div className="text-[10px] text-gray-600 mt-0.5">
                0.45×{s.L_score?.toFixed(0)} + 0.25×{s.Q_score?.toFixed(0)} + 0.20×{s.R_score?.toFixed(0)} + 0.10×{s.P_score?.toFixed(0)} = {s.LQRP_score?.toFixed(1)}
              </div>
            </div>
          </div>
        </div>

        {groups.map(([letter, label, subs]) => (
          <div key={letter} className="mb-4">
            <div className="text-sm font-semibold text-gray-300 mb-2">{label} · <span className={scoreColor(s[letter+'_score'])}>{s[letter+'_score']?.toFixed(0)}</span></div>
            {subs.map(([key, scoreKey]: any) => (
              <SubBar key={key}
                label={`${key} · ${FACTORS[key]?.name || key}`}
                value={s[scoreKey] || 0}
                desc={FACTORS[key]?.desc}
              />
            ))}
          </div>
        ))}

        <div className="mb-4">
          <div className="text-sm font-semibold text-gray-300 mb-2">RAW DATA — Financial Ratios</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[10px]">
            {Object.entries(ratios)
              .filter(([k]) => RATIO_LABELS[k])
              .map(([k, v]: any) => (
                <div key={k} className="flex justify-between p-1.5 bg-gray-950 rounded">
                  <span className="text-gray-500">{RATIO_LABELS[k] || k}</span>
                  <span className="text-gray-300 tabular-nums font-medium">{typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(4) : v.toFixed(1)) : v || '—'}</span>
                </div>
              ))}
          </div>
        </div>

        {anns.length > 0 && (
          <div>
            <div className="text-sm font-semibold text-gray-300 mb-2">ASX ANNOUNCEMENTS ({anns.length})</div>
            <div className="space-y-1 max-h-36 overflow-y-auto">
              {anns.map((a: any, i: number) => (
                <div key={i} className="text-[10px] p-1.5 bg-gray-950 rounded flex justify-between">
                  <span className="text-gray-400">{a.date} · {a.type}</span>
                  <span className="text-gray-500 truncate ml-2 max-w-[300px]">{a.headline}</span>
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