# Skill: Financial Domain Knowledge

Reference this skill when working on valuation logic, ratio calculations,
prompt writing for analyst agents, or interpreting financial data in this codebase.

## Key Valuation Ratios

| Ratio | Formula | What "Good" Looks Like |
|-------|---------|----------------------|
| **P/E** | Price / EPS | Below sector median by >20% = potential undervaluation |
| **Forward P/E** | Price / Next-Year EPS | Lower than trailing P/E = earnings growth expected |
| **P/B** | Price / Book Value per Share | < 1.0 can signal deep value (common in Financials) |
| **EV/EBITDA** | (Market Cap + Debt - Cash) / EBITDA | < 8x for mature companies; sector-relative comparison |
| **Debt/Equity** | Total Debt / Shareholders' Equity | < 1.5x preferred; > 2.0x is a red flag |
| **Current Ratio** | Current Assets / Current Liabilities | > 1.0 required; > 2.0 is conservative |
| **ROE** | Net Income / Shareholders' Equity | > 15% indicates strong returns |
| **ROIC** | NOPAT / Invested Capital | > WACC means the company creates value |

## What "Undervalued" Means in This System

A stock is flagged as **undervalued** when TWO OR MORE of:
1. **Below intrinsic value** — DCF intrinsic value > current market price by ≥15% (margin of safety)
2. **Peer discount** — P/E or EV/EBITDA is >20% below sector median with no fundamental deterioration
3. **Positive sentiment divergence** — stock is down but fundamental analysis is strong and sentiment is turning positive (contrarian signal)

A positive `margin_of_safety` (e.g., 0.25 = 25%) means the stock trades 25% below estimated intrinsic value.

## DCF Model Defaults

When building DCF prompts or tools, use these defaults unless overridden by data:
- **WACC / Discount Rate**: 10% (risk-free 4.5% + equity risk premium 5.5%)
- **Terminal Growth Rate**: 3% (long-run nominal GDP growth)
- **Forecast Horizon**: 5 years of explicit FCF projections
- **FCF Growth**: Use last 3-year CAGR capped at 20% for the first 5 years

## Data Sources Used in This Project

| Source | What It Provides | Tool / Library |
|--------|-----------------|---------------|
| **yfinance** | Price history, market cap, income statement, balance sheet, cash flow | `tools/market_data.py` |
| **SEC EDGAR** | 10-K (annual), 10-Q (quarterly) filings — MD&A, risk factors, guidance | `tools/sec_filings.py` |
| **Alpha Vantage** | Fed funds rate, CPI, real GDP growth, unemployment | `tools/market_data.fetch_macro_data()` |
| **Web search** | News headlines, analyst rating changes, insider activity | `tools/web_search.py` |

## Daily Report Output Conventions

- Report file: `outputs/YYYY-MM-DD_analyst_report.md`
- Monetary values: USD millions in data dicts; USD per share in report text
- Dates: ISO 8601 (`YYYY-MM-DD`) everywhere in code; "April 4, 2026" style in report prose
- Recommendations: exactly one of `BUY` / `HOLD` / `AVOID` (never "Sell" — this is a long-only system)
- Sentiment score range: -1.0 (very bearish) to +1.0 (very bullish); displayed as e.g. "+0.62 (Bullish)"
- Margin of safety: positive = upside, negative = downside; displayed as percentage

## Sector Benchmarks for Peer Comparison

| Sector | Typical P/E | Typical EV/EBITDA |
|--------|------------|-----------------|
| Technology | 20–35x | 15–25x |
| Financials | 10–15x | N/A (use P/B instead) |
| Healthcare | 15–25x | 12–18x |
| Energy | 8–15x | 5–10x |
| Consumer Staples | 20–28x | 12–16x |

Use these as rough baselines; always compare to the most recent 12-month sector median when available.
