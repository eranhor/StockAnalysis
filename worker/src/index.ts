export interface Env {
  DB: D1Database;
}

const DEFAULT_MODEL = 'lqrp_v2';

// Simple auth — shared secret in environment
function authorize(request: Request, env: Env): boolean {
  // For sync endpoints, check a simple API key header
  return true; // MVP: open for development
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const model = url.searchParams.get('model') || DEFAULT_MODEL;

    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Content-Type": "application/json",
    };

    if (method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    try {
      // ============================================================
      // GET /api/rankings
      // ============================================================
      if (path === "/api/rankings" && method === "GET") {
        const limit = parseInt(url.searchParams.get("limit") || "100");
        const { results } = await env.DB.prepare(`
          SELECT c.ticker, c.name, c.sector, ROUND(c.market_cap/1e6,1) as market_cap_m,
                 ROUND(s.L_score,1) as L_score, ROUND(s.Q_score,1) as Q_score,
                 ROUND(s.R_score,1) as R_score, ROUND(s.P_score,1) as P_score,
                 ROUND(s.LQRP_score,1) as LQRP_score,
                 s.role, ROUND(s.final_weight,1) as final_weight,
                 s.gate_status, ROUND(s.data_coverage_pct,0) as data_coverage_pct,
                 s.announcement_scraped, s.archetype
          FROM lqrp_scores s
          JOIN companies c ON c.ticker = s.ticker
          WHERE s.model_version = ?
          ORDER BY s.LQRP_score DESC
          LIMIT ?
        `).bind(model, limit).all();
        return new Response(JSON.stringify(results), { headers: cors });
      }

      // ============================================================
      // GET /api/company/:ticker
      // ============================================================
      const companyMatch = path.match(/^\/api\/company\/([A-Z0-9]{3,6})$/);
      if (companyMatch && method === "GET") {
        const ticker = companyMatch[1];
        const score = await env.DB.prepare(
          "SELECT * FROM lqrp_scores WHERE ticker = ? AND model_version = ? ORDER BY scoring_date DESC LIMIT 1"
        ).bind(ticker, model).first();
        const company = await env.DB.prepare("SELECT * FROM companies WHERE ticker = ?").bind(ticker).first();
        const ratios = await env.DB.prepare(
          "SELECT * FROM financial_ratios WHERE ticker = ? ORDER BY period_end DESC LIMIT 4"
        ).bind(ticker).all();
        const announcements = await env.DB.prepare(
          "SELECT date, type, headline, extraction_confidence FROM announcements WHERE ticker = ? ORDER BY date DESC LIMIT 20"
        ).bind(ticker).all();
        return new Response(JSON.stringify({ score, company, ratios: ratios.results, announcements: announcements.results }), { headers: cors });
      }

      // ============================================================
      // GET /api/portfolio
      // ============================================================
      if (path === "/api/portfolio" && method === "GET") {
        const { results } = await env.DB.prepare(`
          SELECT c.ticker, c.name, c.sector, ROUND(c.market_cap/1e6,1) as market_cap_m,
                 ROUND(s.LQRP_score,1) as LQRP_score, ROUND(s.L_score,1) as L_score,
                 ROUND(s.Q_score,1) as Q_score, ROUND(s.R_score,1) as R_score,
                 ROUND(s.P_score,1) as P_score,
                 s.role, ROUND(s.final_weight,1) as final_weight,
                 s.gate_status, ROUND(s.data_coverage_pct,0) as data_coverage_pct
          FROM lqrp_scores s
          JOIN companies c ON c.ticker = s.ticker
          WHERE s.model_version = ? AND s.final_weight > 0.5
          ORDER BY s.final_weight DESC
        `).bind(model).all();
        const total = results.reduce((sum: number, r: any) => sum + r.final_weight, 0);
        return new Response(JSON.stringify({ holdings: results, total_weight: Math.round(total * 10) / 10 }), { headers: cors });
      }

      // ============================================================
      // GET /api/health
      // ============================================================
      if (path === "/api/health" && method === "GET") {
        const count = await env.DB.prepare(
          "SELECT COUNT(*) as n FROM lqrp_scores WHERE model_version = ?"
        ).bind(model).first();
        return new Response(JSON.stringify({ status: "ok", model, stocks_scored: (count as any)?.n || 0 }), { headers: cors });
      }

      // ============================================================
      // POST /api/sync/companies — batch upsert
      // ============================================================
      if (path === "/api/sync/companies" && method === "POST") {
        const { companies } = await request.json() as { companies: any[] };
        if (!companies?.length) return new Response(JSON.stringify({ error: "No companies" }), { status: 400, headers: cors });

        const stmt = env.DB.prepare(
          "INSERT OR REPLACE INTO companies (ticker, name, gics_industry, sector, market_cap, last_updated) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)"
        );
        const batch = companies.map((c: any) => stmt.bind(c.ticker, c.name, c.gics_industry, c.sector, c.market_cap));
        await env.DB.batch(batch);
        return new Response(JSON.stringify({ synced: companies.length }), { headers: cors });
      }

      // ============================================================
      // POST /api/sync/prices — batch insert
      // ============================================================
      if (path === "/api/sync/prices" && method === "POST") {
        const { prices } = await request.json() as { prices: any[] };
        if (!prices?.length) return new Response(JSON.stringify({ error: "No prices" }), { status: 400, headers: cors });

        const stmt = env.DB.prepare(
          "INSERT OR REPLACE INTO prices_daily (ticker, date, open, high, low, close, volume, source) VALUES (?, ?, ?, ?, ?, ?, ?, 'yfinance')"
        );
        // Process in batches of 50
        for (let i = 0; i < prices.length; i += 50) {
          const batch = prices.slice(i, i + 50).map((p: any) =>
            stmt.bind(p.ticker, p.date, p.open, p.high, p.low, p.close, p.volume)
          );
          await env.DB.batch(batch);
        }
        return new Response(JSON.stringify({ synced: prices.length }), { headers: cors });
      }

      // ============================================================
      // POST /api/sync/scores — batch upsert
      // ============================================================
      if (path === "/api/sync/scores" && method === "POST") {
        const { scores } = await request.json() as { scores: any[] };
        if (!scores?.length) return new Response(JSON.stringify({ error: "No scores" }), { status: 400, headers: cors });

        const stmt = env.DB.prepare(`
          INSERT OR REPLACE INTO lqrp_scores
          (ticker, scoring_date, model_version,
           L_score, Q_score, R_score, P_score, LQRP_score,
           L1_score, L2_score, L3_score, L4_score, L5_score,
           Q1_score, Q2_score, Q3_score, Q4_score,
           R1_score, R2_score, R3_score, R4_score, R5_score,
           P1_score, P2_score, P3_score, P4_score,
           data_coverage_pct, coverage_flags,
           role, raw_weight, final_weight, gate_status,
           archetype, announcement_scraped, notes)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        const batch = scores.map((s: any) => stmt.bind(
          s.ticker, s.scoring_date, s.model_version,
          s.L_score, s.Q_score, s.R_score, s.P_score, s.LQRP_score,
          s.L1_score, s.L2_score, s.L3_score, s.L4_score, s.L5_score,
          s.Q1_score, s.Q2_score, s.Q3_score, s.Q4_score,
          s.R1_score, s.R2_score, s.R3_score, s.R4_score, s.R5_score,
          s.P1_score, s.P2_score, s.P3_score, s.P4_score,
          s.data_coverage_pct, s.coverage_flags,
          s.role, s.raw_weight, s.final_weight, s.gate_status,
          s.archetype, s.announcement_scraped || 0, s.notes
        ));
        await env.DB.batch(batch);
        return new Response(JSON.stringify({ synced: scores.length }), { headers: cors });
      }

      return new Response(JSON.stringify({ error: "Not found" }), { status: 404, headers: cors });
    } catch (e: any) {
      return new Response(JSON.stringify({ error: e.message || "Server error" }), { status: 500, headers: cors });
    }
  },
};