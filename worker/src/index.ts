export interface Env {
  DB: D1Database;
}

const DEFAULT_MODEL = 'lqrp_v2';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const model = url.searchParams.get('model') || DEFAULT_MODEL;

    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET",
      "Content-Type": "application/json",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    try {
      // GET /api/rankings?model=lqrp_v2&limit=100
      if (path === "/api/rankings") {
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

      // GET /api/company/:ticker?model=lqrp_v2
      const companyMatch = path.match(/^\/api\/company\/([A-Z0-9]{3,6})$/);
      if (companyMatch) {
        const ticker = companyMatch[1];
        const score = await env.DB.prepare(
          "SELECT * FROM lqrp_scores WHERE ticker = ? AND model_version = ? ORDER BY scoring_date DESC LIMIT 1"
        ).bind(ticker, model).first();
        const company = await env.DB.prepare(
          "SELECT * FROM companies WHERE ticker = ?"
        ).bind(ticker).first();
        const ratios = await env.DB.prepare(
          "SELECT * FROM financial_ratios WHERE ticker = ? ORDER BY period_end DESC LIMIT 4"
        ).bind(ticker).all();
        const announcements = await env.DB.prepare(
          "SELECT date, type, headline, extraction_confidence FROM announcements WHERE ticker = ? ORDER BY date DESC LIMIT 20"
        ).bind(ticker).all();

        return new Response(JSON.stringify({
          score, company, ratios: ratios.results, announcements: announcements.results
        }), { headers: cors });
      }

      // GET /api/portfolio?model=lqrp_v2
      if (path === "/api/portfolio") {
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

      // GET /api/health
      if (path === "/api/health") {
        const count = await env.DB.prepare(
          "SELECT COUNT(*) as n FROM lqrp_scores WHERE model_version = ?"
        ).bind(model).first();
        return new Response(JSON.stringify({ status: "ok", model, stocks_scored: (count as any)?.n || 0 }), { headers: cors });
      }

      return new Response(JSON.stringify({ error: "Not found" }), { status: 404, headers: cors });
    } catch (e: any) {
      return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: cors });
    }
  },
};