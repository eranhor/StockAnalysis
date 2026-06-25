# Quantified LQRP Model Paper

**Title:** Quantified LQRP Framework for ASX Micro and Small Caps
**Version:** v2.0 — Factor review applied
**Date:** 26 June 2026

---

## 1) Purpose and guiding principles

### 1.1 Objective

The LQRP framework is designed to rank ASX micro and small-cap stocks on a **stock-specific** basis using four independent dimensions:

- **L — Liftoff:** how much rerating capacity exists if execution goes right;
- **Q — Quality:** how real and durable the underlying business or commercial validation is;
- **R — Robustness:** how likely the company is to survive long enough to realise the upside thesis;
- **P — Positioning / Alignment:** whether ownership, supply, and crowding conditions are supportive rather than destructive.

The framework is intended for **alpha generation in a micro/small-cap sleeve**, not for broad diversification or benchmark-relative portfolio construction.

### 1.2 Why the framework exists

Micro and small-cap investing repeatedly fails for the same reasons:

- **Story stocks with weak economics** are mistaken for multi-baggers;
- **Quality businesses with low convexity** are mistaken for asymmetric opportunities;
- **Capital-structure and dilution risk** are ignored until the thesis is diluted away;
- **Crowding and bad ownership structure** distort otherwise reasonable ideas.

The LQRP framework is explicitly built to avoid those traps.

### 1.3 Design rules

The framework follows six rules:

- **Stock selection is separate from portfolio construction.** LQRP is stock-specific only.
- **Quantify everything that can be quantified.** Residual qualitative judgement should be minimal, explicit, and auditable.
- **Use hard gates only for existential failure modes.** A low Liftoff score should not auto-exclude a stock; a broken balance sheet should.
- **Compare like with like where required.** Some metrics (such as valuation multiples and gross margins) should be interpreted within business-model archetypes, not raw sectors.
- **Preserve asymmetry.** This is an alpha sleeve, so Liftoff must remain the largest component.
- **Avoid hidden manual overrides.** Any adjustment should be formulaic, documented, and repeatable.

---

## 2) Final model architecture

### 2.1 Final stock score

```text
LQRP = 0.45L + 0.25Q + 0.20R + 0.10P
```

Where:

- all component scores are scaled **0–100**;
- all sub-factor scores are scaled **0–100**;
- no portfolio-level diversification, overlap, or sector logic is included inside LQRP.

### 2.2 Why these top-level weights

#### Liftoff = 45%

This sleeve exists to find names that can rerate materially. A lower weight would pull the model toward safe small industrials and away from asymmetric upside.

#### Quality = 25%

A quarter of the score goes to economic reality: recurring revenue, commercial proof, improving margins, and scalability.

#### Robustness = 20%

A fifth of the score goes to survivability. This is enough to penalise fragile balance sheets and dilution traps without turning the framework into a pure quality screen.

#### Positioning = 10%

Positioning and ownership matter, but they are supportive signals, not the core thesis. They should tilt ranking and sizing, not dominate them.

---

## 3) Key implementation concepts

### 3.1 Business-model archetypes

To make the model quantitative without comparing unlike businesses incorrectly, the framework classifies each stock into an archetype before normalising a subset of metrics.

#### Archetypes

- **A. Recurring Software / Platform**
  Example profile: ARR, recurring revenue, gross margin > 60%, low asset intensity
- **B. Mixed Software / Services**
  Example profile: recurring contracts but meaningful implementation/services component
- **C. Industrial / Hardware / Manufacturing**
  Example profile: equipment, components, consumables, project/hardware mix
- **D. Financial Platforms**
  Example profile: fintech platforms, marketplace fee models, FUM-linked economics
- **E. Pre-revenue Clinical / Regulatory Technology**
  Generally excluded from core selection unless unusual proof exists

### 3.2 Which sub-factors use archetype normalisation

Archetypes are applied **only where business-model differences materially distort the metric**.

| Sub-factor | Archetype? | Rationale |
|---|---|---|
| L1 (valuation compression) | **Yes** | EV/Revenue for software ≠ industrial |
| L2 (growth velocity) | **Yes** | 20% growth is concerning for SaaS, exceptional for industrials |
| L3 (growth acceleration) | **Yes** | Acceleration context differs by model |
| L4 (operating leverage) | **Yes** | Margins and opex dynamics differ by model |
| L5 (commercial maturity) | No | Universal checklist, not model-dependent |
| Q1 (revenue quality mix) | **Yes** | 60% recurring for SaaS is low; for industrial it is exceptional |
| Q2 (gross margin) | **Yes** | 40% GM is great for hardware, weak for software |
| Q3 (cash conversion) | No | Cash is cash regardless of model |
| Q4 (commercial proof scale) | **Yes** | "Meaningful" scale differs: $5M ARR SaaS vs $50M revenue industrial |
| R1–R5 (robustness) | No | Survivability is model-agnostic |
| P1–P4 (positioning) | No | Ownership and crowding are model-agnostic |

**Summary**: 7 of 17 sub-factors use archetype normalisation. The remaining 10 are universe-wide.

### 3.3 Quantification method

For each raw metric:

#### Step 1 — winsorise

Clip extreme outliers within the full investable universe or archetype subset:

```text
x_clipped = min(max(x, p5), p95)
```

Where p5 and p95 are the 5th and 95th percentile boundaries.

#### Step 2 — normalise to 0–100

If higher is better:

```text
score = 100 × percentile_rank(x_clipped)
```

If lower is better:

```text
score = 100 × (1 - percentile_rank(x_clipped))
```

#### Step 3 — apply weights

Compute the weighted component score.

**Important rule for composite sub-factors**: When a sub-factor combines multiple raw metrics, each ingredient is **percentile-ranked independently before weighting and summing**. Raw values with incompatible units are never added directly.

---

## 4) Metric dictionary and scoring blueprint

### 4.1 L — Liftoff score

#### Purpose

Measures the stock's capacity to rerate sharply if execution works and the market notices.

#### Formula

```text
L = 0.30L1 + 0.20L2 + 0.20L3 + 0.15L4 + 0.15L5
```

*Note: L1 weight increased from 25% to 30% (valuation compression is the most reliable rerating signal). L3 reduced from 25% to 20% (growth acceleration is noisier than absolute valuation).*

---

#### L1 — Valuation compression (30%)

**What it measures:** rerating room implied by current valuation vs existing operating base.

**Primary raw metric hierarchy:**

- EV / ARR if recurring revenue > 50% and ARR disclosed
- Else EV / Gross Profit if gross profit positive
- Else EV / Revenue if revenue positive
- Else EV / Cash only as last resort (usually not suitable for core selection)

**Direction:** lower is better

**Normalisation:** within business-model archetype

**Formula rule:**

```text
L1_score = 100 × (1 - percentile_rank(selected valuation multiple))
```

**Rationale:** A name already trading on a rich multiple has less rerating headroom than a name with similar fundamentals on a low multiple.

---

#### L2 — Growth velocity (20%)

**What it measures:** how fast the business is currently scaling.

**Primary raw metric hierarchy:**

- ARR growth YoY
- Else Recurring revenue growth YoY
- Else Contracted revenue growth YoY
- Else Revenue growth YoY

**Direction:** higher is better

**Normalisation:** within business-model archetype

**Formula rule:**

```text
L2_score = percentile_rank(latest growth rate)
```

**Rationale:** Faster current growth creates more perception change and more room for valuation rerating. Normalising within archetype prevents SaaS companies from automatically dominating industrials on growth rate alone.

---

#### L3 — Growth acceleration (20%)

**What it measures:** whether the growth profile is improving or slowing.

**Raw metric:**

```text
Acceleration = Latest YoY growth - Prior YoY growth
```

Where "growth" should use the highest-quality growth measure available from the L2 hierarchy.

**Direction:** higher is better

**Normalisation:** within business-model archetype

**Formula rule:**

```text
L3_score = percentile_rank(growth acceleration)
```

**Rationale:** Markets rerate improvements in momentum faster than static growth. Normalising within archetype accounts for the fact that acceleration from 5% to 10% for an industrial is structurally different from 30% to 40% for SaaS. Weight reduced from 25% to 20% because acceleration is inherently noisier quarter-to-quarter than absolute valuation or growth rate.

---

#### L4 — Operating leverage potential (15%)

**What it measures:** the capacity for revenue growth to convert into earnings growth.

**Raw ingredients (each percentile-ranked independently, then combined):**

```text
L4_score = 0.6 × percentile_rank(Gross Margin %)
         + 0.4 × percentile_rank(EBITDA margin change YoY)
```

Where EBITDA margin change is the difference between current-period and prior-period EBITDA margins.

If EBITDA margin change is not available, use gross margin only and note reduced precision.

**Direction:** higher is better

**Normalisation:** within archetype (each ingredient is percentile-ranked within the archetype subset)

**Rationale:** A company with high margin and improving EBITDA conversion has stronger rerating potential than one where growth must be bought with rising costs. EBITDA margin change replaces the previous opex growth spread — it captures operating leverage more cleanly and is less volatile quarter-to-quarter. The 60/40 split gives primary weight to the structural margin level with a meaningful adjustment for margin direction.

---

#### L5 — Commercial maturity & realisation (15%)

**What it measures:** whether the business has crossed commercial validation thresholds AND is likely to convert its opportunity into visible progress in the next 12–24 months.

**This sub-factor requires structured judgement**, because public disclosures often do not provide a clean quantitative proxy. It consolidates the previous separate L5 (realisation likelihood) and Q5 (validation maturity) checklists into a single unified assessment to eliminate redundancy.

**Use the following checklist:**

- +20 if product is already commercially launched
- +20 if there are at least 3 paying customers / active commercial deployments disclosed
- +20 if there is at least one signed multi-year paying customer / contract already live
- +20 if the sales motion is already proven (repeatable enterprise contracts, active customer base, or clearly monetised installed base)
- +20 if the next 12–24 months contain visible milestone-driven revenue conversion rather than only "potential" conversion

**Direction:** higher is better

**Rationale:** A stock can have enormous notional upside but low probability of actual commercial conversion. This unified factor corrects that, combining both backward-looking validation and forward-looking realisation into a single structured assessment.

---

### 4.2 Q — Quality score

#### Purpose

Measures business reality, durability, and commercial maturity.

#### Formula

```text
Q = 0.34Q1 + 0.28Q2 + 0.22Q3 + 0.16Q4
```

*Note: Q5 (validation) merged into L5. Its 10% weight redistributed proportionally: Q1 +4%, Q2 +3%, Q3 +2%, Q4 +1%.*

---

#### Q1 — Revenue quality mix (34%)

**What it measures:** how repeatable and defendable the revenue base is.

**Raw metric (primary):**

```text
Q1_manual = 0.6 × Recurring Revenue % + 0.4 × Contracted Revenue %
```

If only one of the two is available, use that metric directly.

**Quantitative supplement (when manual data unavailable):**

```text
Q1_volatility = 100 - percentile_rank(CV of quarterly revenue over 8 quarters)
```

Where CV = coefficient of variation (std dev / mean). Lower revenue volatility suggests recurring/contracted revenue.

**Combined rule:**

```text
If recurring_revenue_pct available:
    Q1_raw = 0.7 × Q1_manual + 0.3 × Q1_volatility
Else:
    Q1_raw = Q1_volatility
```

**Direction:** higher is better

**Normalisation:** within business-model archetype (for both the manual and volatility components)

**Formula rule:**

```text
Q1_score = percentile_rank(Q1_raw)
```

**Rationale:** Recurring and contracted revenue is materially higher quality than project or one-off sales. The revenue volatility supplement provides a data-driven floor when manual recurring revenue % is unavailable (as it often is for microcaps). The 70/30 split weights the direct metric higher when available, while the volatility component ensures the factor never goes entirely dark.

---

#### Q2 — Gross margin level and trend (28%)

**What it measures:** economic quality and whether it is improving.

**Raw metric:**

```text
Q2_raw = 0.7 × Gross Margin % + 0.3 × Gross Margin change YoY
```

**Direction:** higher is better

**Normalisation:** within archetype

**Formula rule:**

```text
Q2_score = percentile_rank(Q2_raw)
```

**Rationale:** Strong and improving gross margins indicate better pricing power, economics, and scale quality. A 40% GM is excellent for hardware but weak for software — archetype normalisation handles this.

---

#### Q3 — Cash conversion / earnings quality (22%)

**What it measures:** whether reported progress becomes usable cash.

**Primary raw metric hierarchy:**

- Operating Cash Flow / Revenue
- Else Free Cash Flow / Revenue
- Else CFO / EBITDA

**Direction:** higher is better

**Normalisation:** universe-wide

**Formula rule:**

```text
Q3_score = percentile_rank(selected cash conversion metric)
```

**Rationale:** This penalises businesses where revenue growth exists but cash economics are still poor. Cash conversion is model-agnostic.

---

#### Q4 — Commercial proof scale (16%)

**What it measures:** how commercially substantial the business already is.

**Primary raw metric hierarchy:**

- ARR
- Else Recurring Revenue
- Else Revenue
- Else Contract value signed in last 12 months

**Raw transform:**

```text
Q4_raw = log(1 + selected scale metric)
```

**Direction:** higher is better

**Normalisation:** within business-model archetype

**Formula rule:**

```text
Q4_score = percentile_rank(Q4_raw)
```

**Rationale:** Log scaling avoids large mature names dominating solely by size. Normalising within archetype ensures that "meaningful scale" is judged relative to peers.

---

### 4.3 R — Robustness score

#### Purpose

Measures survivability and resistance to dilution, fragility, and concentration failure.

#### Formula

```text
R = 0.30R1 + 0.20R2 + 0.20R3 + 0.15R4 + 0.15R5
```

---

#### R1 — Cash runway (30%)

**What it measures:** capacity to survive without fresh external capital.

**Raw metric:**
If operating cash flow is negative:

```text
Runway_months = Cash / abs(Quarterly operating cash outflow) × 3
```

If operating cash flow is positive, score as maximum.

**Scoring map:**

- \>24 months → 100
- 18–24 → 80
- 12–18 → 60
- 6–12 → 30
- <6 → 0

**Normalisation:** universe-wide

**Rationale:** Companies do not die because the story is bad; they die because they run out of time and money.

---

#### R2 — Leverage and liquidity (20%)

**What it measures:** financial stress.

**Raw ingredients (each percentile-ranked independently, then combined):**

```text
R2_score = 0.6 × percentile_rank(inverse(Net Debt / EBITDA))
         + 0.4 × percentile_rank(Current Ratio)
```

If EBITDA is negative, use Net Debt / Gross Profit instead for the first ingredient.

**Direction:** lower leverage and higher liquidity are better (handled by inverse for ND/EBITDA)

**Normalisation:** universe-wide

**Rationale:** A stock with strong growth but stressed leverage is more fragile than it looks. Percentile-ranking each ingredient before combining prevents incompatible units from distorting the composite.

---

#### R3 — Dilution risk (20%)

**What it measures:** capital markets dependency — both backward-looking (realised dilution) and forward-looking (impending dilution risk).

**Raw ingredients (each percentile-ranked independently, then combined):**

```text
R3_score = 0.40 × (100 - percentile_rank(Share count growth over 12 months))
         + 0.30 × (100 - percentile_rank(Capital raised in last 12 months / current market cap))
         + 0.30 × (100 - percentile_rank(Quarterly cash burn rate / Cash balance))
```

Where cash burn rate = abs(quarterly operating cash outflow) for cash-negative companies, and 0 for cash-positive companies.

**Direction:** less dilution and lower burn are better (handled by inverting the percentile ranks)

**Normalisation:** universe-wide

**Rationale:** The first two ingredients capture realised dilution. The third (cash burn rate) is a leading indicator of future dilution — a company burning cash fast relative to its balance sheet WILL dilute, even if it hasn't yet. This makes R3 forward-looking rather than purely reactive.

---

#### R4 — Execution & asset intensity (15%)

**What it measures:** how operationally complex and asset-heavy the business is.

**Raw ingredients (each percentile-ranked independently, then combined):**

```text
R4_score = 0.5 × (100 - percentile_rank(CapEx / Revenue))
         + 0.5 × (100 - percentile_rank(PP&E / Revenue))
```

**Direction:** lower asset intensity is better (less complex execution)

**Normalisation:** universe-wide

**Rationale:** Asset-light businesses are inherently less complex to execute and require fewer things to go right operationally. CapEx/Revenue captures ongoing investment burden; PP&E/Revenue captures structural asset intensity. The previous customer concentration component has been removed because it is almost never disclosed for sub-$100M companies and was almost always scored via subjective fallback buckets. The structured judgement buckets have been eliminated — this factor is now fully quantitative.

---

#### R5 — Cash flow stability (15%)

**What it measures:** whether the business repeatedly generates cash, not just occasionally.

**Raw metric:**

```text
R5_raw = % of last 4 quarters (or 2 half-year periods) with positive operating cash flow
```

**Scoring map:**

- 4/4 positive → 100
- 3/4 → 75
- 2/4 → 50
- 1/4 → 25
- 0/4 → 0

**Normalisation:** universe-wide

**Rationale:** Stability of internal funding materially reduces both dilution risk and execution fragility.

---

### 4.4 P — Positioning / Alignment score

#### Purpose

Measures how supportive ownership and supply conditions are.

#### Formula

```text
P = 0.35P1 + 0.25P2 + 0.20P3 + 0.20P4
```

---

#### P1 — Insider net buying (35%)

**What it measures:** whether insiders are adding or reducing exposure.

**Raw metric:**

```text
P1_raw = Net insider buy value over 12 months / free-float market cap
```

Where insider buys/sells refer to disclosed on-market director or key-insider transactions.

**Direction:** higher is better

**Normalisation:** universe-wide

**Rationale:** Net insider buying is one of the strongest alignment signals in microcaps.

---

#### P2 — Register quality (25%)

**What it measures:** whether the holder mix is supportive rather than dangerous.

**Raw ingredients:** insider ownership %, institutional ownership %.

**Goldilocks scoring function:**

```text
Goldilocks(x, lo, hi) = 100 - abs(50 - 100 × (x - lo) / (hi - lo))
```

Clipped to [0, 100]. This scores highest when x is in the middle of the ideal range and falls off toward either extreme.

**Formula:**

```text
P2_score = 0.5 × Goldilocks(insider_pct, 10%, 30%)
         + 0.5 × Goldilocks(insto_pct, 10%, 40%)
```

**Ideal ranges:**
- Insider ownership: **10–30%** (enough skin in the game, not so much that liquidity suffers)
- Institutional ownership: **10–40%** (professional oversight without crowding)

**Normalisation:** universe-wide

**Rationale:** The top-holder concentration component has been removed — it was rarely available and the Goldilocks function already indirectly captures concentration risk (extreme insider ownership implies concentration). The explicit formula replaces the previously vague "triangular function" description.

---

#### P3 — Crowding / underfollowed (20%)

**What it measures:** whether the stock is underfollowed or already crowded.

**Raw metric:**

```text
P3_raw = 100 - percentile_rank(Average daily volume / Shares outstanding)
```

Where average daily volume is measured over the last 6 months. This is **share turnover** — the percentage of the company that trades each day.

**Direction:** lower turnover is better (more underfollowed/undiscovered)

**Normalisation:** universe-wide

**Rationale:** Low share turnover indicates an underfollowed, under-owned stock with more potential for rerating when discovered. High turnover indicates a crowded, trader-dominated stock where the story is already widely known. This replaces the previous HotCopper-based crowding proxy — share turnover is objective, computable from price + volume data, historically available, and not dependent on a single platform's activity. HotCopper thread views were noisy (one viral post can spike views), platform-specific, and cannot be reliably automated.

---

#### P4 — Supply overhang (20%)

**What it measures:** whether new stock supply is likely to weigh on near-term returns.

**Raw metric:**

```text
P4_raw = 100 - percentile_rank(Share count growth over 6 months)
```

**Direction:** lower share growth is better

**Normalisation:** universe-wide

**Rationale:** Even good fundamentals can underperform when the register is absorbing continuous new supply. The 6-month horizon focuses on near-term supply pressure (distinct from R3's 12-month dilution risk which focuses on structural capital dependency). The previous substantial-holder sell notices and option/escrow release components have been removed — they were inconsistently available and the share count growth metric captures their net effect. This factor now uses a single clean, computable metric.

---

## 5) Hard gates and tier restrictions

These are **not optional**. They exist because some failure modes are existential.

### 5.1 Hard exclusion gates

```text
If R < 35 → EXCLUDE
If Q < 35 → EXCLUDE
If P < 20 → EXCLUDE
```

#### Rationale

- **R < 35** means the company is too fragile to survive long enough for the thesis to matter.
- **Q < 35** means there is not enough business reality or validation to justify inclusion.
- **P < 20** means ownership/supply/crowding conditions are structurally hostile.

### 5.2 Soft tier gates

These allow a stock to remain in the universe, but restrict its role:

```text
If R < 50 → cannot be Top Tier and max portfolio weight = 10%
If Q < 50 → cannot be Top Tier and max portfolio weight = 10%
If P < 40 → cannot be Top Tier and max portfolio weight = 8–10%
```

### 5.3 No gate on L

There is **no hard gate on Liftoff**.

#### Rationale

A low-L stock can still serve a useful structural role in a high-alpha sleeve — for example, a quality anchor such as XRF. Low Liftoff should reduce final score naturally, not automatically exclude the name.

---

## 6) Data source hierarchy

### 6.1 Primary sources

These should be preferred whenever possible.

- **ASX announcements / company filings**
  - quarterly activities and cash flow reports
  - half-year / full-year financial statements
  - Appendix 3Y director interest notices
  - substantial holder notices
  - issue of shares / cleansing notice / application for quotation notices
- **Company investor presentations**
  - used for ARR, contracted revenue, customer counts, and milestone disclosure
- **Official ASX company pages / company investor pages**
  - useful for announcements chronology

### 6.2 Secondary sources

Used only when the primary source is unavailable or difficult to extract quickly.

- **Market Index**
  - market cap, announcement index, quick summaries
- **StockAnalysis**
  - market cap, enterprise value, balance sheet snapshots
- **Yahoo Finance**
  - holdings, insider transaction snapshots, market cap, price history
- **Simply Wall St**
  - ownership structure, dilution flag, insider trading summaries
- **HotCopper**
  - supplementary context only, not primary data

### 6.3 Source hierarchy rule

For any disputed data point:

```text
ASX filing > company investor materials > ASX page > Market Index > StockAnalysis / Yahoo / Simply Wall St > forum-derived proxies
```

---

## 7) Scoring workflow

### 7.1 Step-by-step process

#### Step 1 — classify the stock into an archetype

Assign one of:

- Recurring Software / Platform
- Mixed Software / Services
- Industrial / Hardware / Manufacturing
- Financial Platform
- Pre-revenue Clinical / Regulatory Technology

#### Step 2 — collect raw metrics

Collect the full metric dictionary values from the data source hierarchy (Section 6).

#### Step 3 — winsorise and normalise

Apply winsorisation (p5–p95) and percentile ranking. For sub-factors marked "within archetype" in Section 3.2, normalise within the archetype subset. For all others, normalise universe-wide.

#### Step 4 — compute each sub-factor score

Use the formulas in Section 4. For composite sub-factors (L4, R2, R3, R4), percentile-rank each ingredient independently before combining.

#### Step 5 — compute L, Q, R, P

Apply component-level formulas.

#### Step 6 — apply hard gates and soft tier gates

This step occurs **before final portfolio selection**.

#### Step 7 — compute final LQRP score

Apply:

```text
LQRP = 0.45L + 0.25Q + 0.20R + 0.10P
```

#### Step 8 — rank stocks

Use the following practical buckets:

- **70+** = Top tier
- **65–69.9** = Near-miss / reserve bench
- **<65** = do not force

---

## 8) Residual judgement items

The framework is intended to be **~90% quantitative, ~10% structured judgement**.

### Remaining judgement areas

- **Archetype classification**
- **L5 commercial maturity & realisation** (structured checklist — the only remaining judgement-based sub-factor)
- **Q1 recurring/contracted revenue %** (when manual data from company disclosures is available to supplement the quantitative volatility proxy)

### Why these remain judgement-based

Public company disclosure is inconsistent. The L5 checklist requires reading investor presentations and contract announcements to assess commercial maturity. Q1's recurring revenue % is company-disclosed and not available in any standardised database — it must be manually extracted from 4C filings and investor presentations. The framework therefore uses a hybrid: quantitative volatility proxy as the default, with manual recurring % as a quality upgrade when available.

---

## 9) Backtest-ready proxy model

This section defines a **fully computable approximation** of the LQRP model for automated scoring. It maps each sub-factor to a quantitative proxy available from free data sources (primarily yfinance), with a data quality flag.

### 9.1 Proxy mapping table

| Sub-factor | Free data proxy | Source | Quality | Notes |
|---|---|---|---|---|
| **L1** | EV/Revenue percentile within sector | yfinance | High | Sector used as archetype proxy |
| **L2** | Revenue growth YoY, percentile within sector | yfinance | High | Sector used as archetype proxy |
| **L3** | Growth acceleration from quarterly data, within sector | yfinance quarterly | Medium | Requires 8+ quarters |
| **L4** | 0.6×pct_rank(GM%) + 0.4×pct_rank(EBITDA margin change), within sector | yfinance | Medium | EBITDA from income statement |
| **L5** | Revenue growth × GM% interaction, percentile-ranked | yfinance | Low | Weak proxy for commercial maturity |
| **Q1** | 70% recurring_manual + 30% revenue_volatility_proxy. Falls back to 100% volatility if no manual data | yfinance quarterly | Medium | Volatility = CV of quarterly revenue |
| **Q2** | 0.7×GM% + 0.3×GM_change_YoY, within sector | yfinance | High | Directly computable |
| **Q3** | OCF/Revenue, percentile-ranked | yfinance | Medium | From cash flow statement |
| **Q4** | log(1 + revenue), percentile within sector | yfinance | High | Directly computable |
| **R1** | Current ratio as cash runway proxy | yfinance | Medium | True runway needs quarterly OCF |
| **R2** | 0.6×pct_rank(inv(ND/EBITDA)) + 0.4×pct_rank(CR) | yfinance | High | Directly computable |
| **R3** | 0.4×(100−pct_rank(share_growth)) + 0.3×(100−pct_rank(capital/MC)) + 0.3×(100−pct_rank(burn/cash)) | yfinance | Medium | Share count from BS; burn from CF |
| **R4** | 0.5×(100−pct_rank(CapEx/Rev)) + 0.5×(100−pct_rank(PP&E/Rev)) | yfinance | High | Fully computable |
| **R5** | % of last 4 quarters with positive OCF, scoring map | yfinance | Medium | From quarterly CF |
| **P1** | Insider ownership %, percentile-ranked | yfinance | Low | Ownership ≠ buying. Needs ASX 3Y filings to upgrade |
| **P2** | 0.5×Goldilocks(insider%,10,30) + 0.5×Goldilocks(insto%,10,40) | yfinance | Medium | Explicit Goldilocks formula |
| **P3** | 100 − pct_rank(avg_daily_vol/shares_outstanding) | yfinance | High | Share turnover — fully computable |
| **P4** | 100 − pct_rank(share_count_growth_6m) | yfinance | Medium | From quarterly BS |

### 9.2 Proxy model limitations

The proxy model is an **approximation**. Key differences from the full model:

1. **L5 (commercial maturity)** uses a weak proxy — the structured checklist requires manual reading of company materials.
2. **P1 (insider buying)** uses insider ownership % rather than net buying activity. Upgrading to actual director transaction data requires parsing ASX Appendix 3Y filings.
3. **Q1 (recurring revenue %)** falls back to revenue volatility when manual data is unavailable.
4. **Archetypes** are approximated by GICS sectors rather than the five business-model archetypes.
5. **R1 (cash runway)** uses current ratio as a simplified proxy where quarterly cash flow data is sparse.

---

## 10) Data provenance flags

Each stock receives a data quality assessment per sub-factor:

| Flag | Meaning |
|---|---|
| **OK** | Full data from primary or reliable secondary source |
| **PROXY** | Approximation used (e.g., sector for archetype, GM for recurring %) |
| **WEAK** | Known weak proxy (e.g., insider ownership for insider buying) |
| **MISSING** | No data available, neutral score assigned |
| **MANUAL** | Human-collected data from ASX filings (highest quality) |

The overall data coverage % is reported as: `sum(OK + MANUAL weights) / sum(all weights)`.

---

## 11) Portfolio sizing methodology

### 11.1 Purpose

This section defines a **repeatable, formula-based portfolio sizing method** kept separate from the stock-specific LQRP score.

### 11.2 Inputs required

For each stock *i*, define:

- `LQRP_i` = final stock-specific score
- `Role_i` = one of: `Anchor`, `CoreBridge`, `LiftoffEngine`, `Optionality`
- `GateCap_i` = maximum weight allowed by hard/soft gate rules
- `RoleCap_i` = maximum weight allowed for the portfolio role

### 11.3 Role cap framework

| Role | Hard cap | Rationale |
|---|---:|---|
| Anchor | 20% | Stability and downside dampening |
| CoreBridge | 17.5% | Real businesses supporting the sleeve |
| LiftoffEngine | 17.5% | Main upside drivers |
| Optionality | 10% | Convex upside, structurally fragile |

**Cap rationale**: The 17.5% cap on engines and bridges ensures a minimum of ~6 positions. The 20% cap on anchors allows a larger quality ballast. The 10% cap on optionality reflects structural fragility.

### 11.4 Sizing algorithm

```text
T = 65  (investability threshold)
RawConviction_i = max(LQRP_i - T, 0)²
RawWeight_i = RawConviction_i / Σ RawConviction
Cap_i = min(RoleCap_i, GateCap_i)
CappedWeight_i = min(RawWeight_i, Cap_i)
If optionality included: scale core positions to (100% - optionality_weight)
FinalWeight_i = renormalise(CappedWeight_i)
```

---

## 12) Final summary

The quantified LQRP framework ranks ASX micro and small-cap stocks using four stock-specific dimensions:

- **Liftoff** — rerating capacity (45%)
- **Quality** — business reality (25%)
- **Robustness** — survivability (20%)
- **Positioning** — ownership and supply conditions (10%)

The v2.0 model incorporates factor review improvements:
- **L1** strengthened (25→30% of L) — valuation compression is the most reliable rerating signal
- **L3** moderated (25→20%) — growth acceleration is noisier
- **L4** simplified — EBITDA margin change replaces opex growth spread
- **L5+Q5 merged** — unified commercial maturity checklist eliminates redundancy (18→17 sub-factors)
- **Q1** supplemented — revenue volatility provides data-driven floor when recurring % unavailable
- **R3** made forward-looking — cash burn rate added as leading dilution indicator
- **R4** quantified — CapEx+PP&E intensity replaces subjective complexity buckets
- **P2** simplified — explicit Goldilocks formula, top-holder concentration dropped
- **P3** replaced — share turnover replaces HotCopper as objective crowding proxy
- **P4** simplified — 6-month share growth as single supply overhang metric

The model is now ~90% quantitative with one remaining structured-judgement factor (L5 commercial maturity).

---