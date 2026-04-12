# Financial Analyst Enhancement Plan

**Created:** 2026-04-11  
**Status:** All Phases Complete ✅

---

## API Inventory (What We Have)

| Data | Source | API Key Required | Tool File |
|------|--------|-----------------|-----------|
| Price history, OHLCV | yfinance | None | `tools/market_data.py` |
| Income Statement (損益表) | yfinance `stock.income_stmt` | None | `tools/market_data.py` |
| Balance Sheet (資產負債表) | yfinance `stock.balance_sheet` | None | `tools/market_data.py` |
| Cash Flow Statement (現金流量表) | yfinance `stock.cash_flow` | None | `tools/market_data.py` |
| EPS (每股盈餘), Revenue, Net Income, Shareholders' Equity | yfinance `stock.info` | None | `tools/market_data.py` |
| Analyst price targets, upgrades/downgrades | yfinance | None | `tools/market_data.py` |
| 10-K / 10-Q filings (年報/季報) | SEC EDGAR (public REST API) | None | `tools/sec_filings.py` |
| Fed Funds Rate, CPI, GDP, Unemployment | Alpha Vantage | `ALPHA_VANTAGE_API_KEY` (free tier) | `tools/market_data.py` |
| News search, insider activity | Anthropic web_search tool | `ANTHROPIC_API_KEY` | `tools/web_search.py` |
| Sector peers (S&P 500, Nasdaq-100) | Built-in universe lists | None | `tools/screener.py` |

**Missing APIs (not yet integrated):**
- No dedicated earnings calendar API (could add via yfinance `stock.calendar`)
- No options flow / short interest data
- No institutional ownership data (available via yfinance `stock.institutional_holders`)

---

## Goals

1. **Analyze provided tickers** → verdict (undervalued/fairly valued/overvalued) + **target buy price**
2. **Find top N undervalued stocks** from S&P 500 / Nasdaq-100 universe
3. **Comprehensive analysis**: cash flow quality, growth estimation, peer comparison, key financial metrics
4. **Show agent reasoning** in a graphical UI with per-agent thinking steps

---

## Phase 1 — Core Valuation Completeness + Phase 2 UI ✅ COMPLETED

### What was built

#### `tools/calculations.py` additions
- `calculate_target_price(fcf_history, shares_outstanding, beta, ...)` — bull/base/bear DCF with sensitivity table
- `calculate_peg_ratio(pe_ratio, eps_growth_rate_pct)` — PEG < 1.0 signals growth-adjusted undervaluation
- `calculate_pfcf_ratio(price, fcf_per_share)` — P/FCF strips accounting noise from earnings

#### `agents/fundamental_analyst.py` enhancements
- Added `target_price_low`, `target_price_base`, `target_price_high`, `buy_below_price` to output
- Added `peg_ratio`, `pfcf_ratio`, `cash_flow_quality` (FCF/Net Income ratio) to metrics
- Extended Claude verdict to include `target_price_rationale` and `entry_strategy`
- Wired `prompts/fundamental_analyst.md` as system prompt (was using inline prompt before)

#### `prompts/fundamental_analyst.md` rewrite
- Added target price output requirements
- Added PEG, P/FCF, cash flow quality instructions
- Added entry strategy / buy-below-price output field

#### New: `agents/growth_analyst.py`
- Computes 3-year revenue CAGR, EPS CAGR, FCF CAGR from yfinance income_stmt / cash_flow
- Computes PEG ratio (P/E ÷ forward EPS growth)
- Flags growth acceleration vs. deceleration
- Outputs: `revenue_cagr_3y`, `eps_cagr_3y`, `fcf_cagr_3y`, `growth_verdict`, `growth_quality`

#### New: `agents/peer_comparison.py`
- Fetches 5–8 sector peers from `tools/screener.py` universe
- Computes sector median P/E, EV/EBITDA, P/FCF, P/B
- Outputs `peer_discount_pct` (negative = trading at discount to peers = potential undervaluation)
- Outputs `peer_verdict`: "significant_discount" | "slight_discount" | "at_par" | "premium"

#### `agents/orchestrator.py` updates
- Stage 2b: GrowthAnalystAgent (after FundamentalAnalyst, before Sentiment)
- Stage 2c: PeerComparisonAgent
- Passes `growth_analysis` and `peer_comparison` context keys to ReportWriter

#### `agents/report_writer.py` updates
- Includes target price range in report
- Includes growth metrics section
- Includes peer comparison table

#### `config/agents.yaml` additions
- `growth_analyst` block
- `peer_comparison` block

---

## Phase 2 — UI Visualization ✅ COMPLETED

### Goals
- Show each agent's reasoning as a collapsible accordion per ticker
- Target price gauge: current price vs. buy_below / base / high target
- Key metrics dashboard: cash flow waterfall, revenue/EPS sparklines, ratio scorecard
- "Top N Undervalued" ranked table with composite score

### Files to modify
- `web/static/index.html` — main UI (single-file app)
- `web/app.py` — add `/api/screen/top-n` endpoint

### UI Components to add

#### 1. Reasoning Accordion (per ticker, per agent)
Each agent emits `reasoning` in its `agent_ticker_complete` event.
Currently displayed as plain text. Needs:
- Collapsible section per agent (Fundamental / Growth / Peer / Sentiment)
- Syntax-highlighted JSON for metrics
- Confidence badge (high=green, medium=yellow, low=red)

#### 2. Target Price Gauge
Visual range bar showing:
- `buy_below_price` (green zone entry point)
- `target_price_base` (fair value)  
- `target_price_high` (bull case)
- Current price marker
- Analyst consensus target (from yfinance)

#### 3. Key Metrics Cards
Per ticker:
- Cash flow waterfall: Operating CF → CapEx → FCF (bar chart)
- Revenue/EPS 3-year trend (sparkline)
- Ratio scorecard table with sector benchmark column
- Peer comparison bar chart (ticker vs. sector median)

#### 4. Top N Undervalued Table
- Composite score = weighted avg of: margin_of_safety (40%) + peer_discount (30%) + growth_quality (20%) + sentiment (10%)
- Sortable columns
- One-click to run full analysis on selected ticker

### Event types to add/use
- `agent_ticker_complete` already has `reasoning` — just needs UI rendering
- Add `target_price` object to fundamental `agent_ticker_complete` data
- Add `growth_summary` to growth agent event
- Add `peer_summary` to peer agent event

---

## Phase 3 — Technical Analysis ✅ COMPLETED

### New agent: `agents/technical_analyst.py`
Uses price history already in `raw_data[ticker]["prices"]["history"]`.

Computes:
- RSI (14-day) — above 70 = overbought, below 30 = oversold
- 50-day / 200-day moving average — golden cross / death cross
- 52-week position: `(current - 52w_low) / (52w_high - 52w_low)` — 0.0 to 1.0
- Volume trend: avg volume last 20 days vs. 90-day avg
- Outputs: `technical_verdict`: "strong_entry" | "neutral" | "avoid_entry" | "overbought"

### What was built
- `tools/calculations.py`: `calculate_rsi`, `calculate_moving_averages`, `calculate_52w_position`, `calculate_volume_trend`
- `agents/technical_analyst.py`: TechnicalAnalystAgent inheriting BaseAgent
- `prompts/technical_analyst.md`: system prompt
- `config/agents.yaml`: `technical_analyst` block added
- `agents/orchestrator.py`: Stage 2d inserted; total_stages bumped to 7
- `web/static/index.html`: live feed card, Technical Analysis result section, reasoning accordion entry, 7th pipeline stage indicator

---

## Phase 4 — "Find Top N" Full Pipeline ✅ COMPLETED

### Goal
User selects universe (S&P 500 / Nasdaq-100 / Watchlist), picks N (e.g. 10), system:
1. Runs screener to score all tickers (fast, no LLM) ✅ `tools/screener.py`
2. Takes top N candidates ✅ `top_n` param via `/ws/screen`
3. Runs full pipeline (all agents) on those candidates ✅ `OrchestratorAgent` in `/ws/screen`
4. Returns ranked table sorted by composite score ✅ leaderboard in Results tab

### What was built (gap filled)
The pipeline infrastructure was already in place via `/ws/screen` + Discover UI mode.
The missing piece — **post-pipeline composite re-ranking** — was added to `web/static/index.html`:

- `computeCompositeScore(ticker)` — computes weighted score from agent outputs:
  `0.40 × margin_of_safety + 0.30 × peer_discount + 0.20 × growth_quality + 0.10 × sentiment`
  Each component normalised to 0–1; final score is 0–100.
- `renderCompositeLeaderboard(tickers, scored)` — builds a ranked leaderboard panel at the
  top of the Results tab with: rank medal, ticker + verdict badges, 4-component bar breakdown,
  animated SVG score ring, buy-below price, click-to-scroll to full analysis card.
- `renderResults()` updated to sort ticker cards by composite score (best first) and prepend
  the leaderboard when 2+ tickers are present.
- `scrollToTicker(ticker)` — leaderboard rows click to jump to the full ticker card.
- Stage reset loops fixed to cover all 7 stages.

---

## Conventions Reminder

- All agents inherit `BaseAgent` from `agents/base_agent.py`
- TypedDict for all inputs/outputs
- System prompts in `prompts/*.md` — never inline in Python
- Errors caught in `run()`, written to `context["<agent>_error"]`
- Log start/end via `_log_run_start()` / `_log_run_end()`
- Emit events via `_emit()` for UI streaming

## File Map

```
agents/
  base_agent.py          ← do not modify
  orchestrator.py        ← add new agents here
  data_collector.py      ← do not modify (Phase 1)
  fundamental_analyst.py ← Phase 1 enhanced ✅
  growth_analyst.py      ← Phase 1 new ✅
  peer_comparison.py     ← Phase 1 new ✅
  technical_analyst.py   ← Phase 3 new ✅
  sentiment_analyst.py   ← do not modify (Phase 1)
  report_writer.py       ← Phase 1 updated ✅

tools/
  calculations.py        ← Phase 1 enhanced ✅
  market_data.py         ← do not modify (Phase 1)
  sec_filings.py         ← do not modify
  screener.py            ← used by PeerComparisonAgent
  web_search.py          ← do not modify

prompts/
  fundamental_analyst.md ← Phase 1 rewritten ✅
  growth_analyst.md      ← Phase 1 new ✅
  peer_comparison.md     ← Phase 1 new ✅
  report_writer.md       ← Phase 1 updated ✅

config/
  agents.yaml            ← Phase 1 updated ✅
  watchlist.yaml         ← do not modify

web/
  app.py                 ← Phase 2
  static/index.html      ← Phase 2
```
