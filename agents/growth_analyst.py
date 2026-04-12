"""GrowthAnalystAgent — assesses revenue, EPS, and FCF growth quality per ticker."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.calculations import calculate_peg_ratio

logger = logging.getLogger(__name__)


class GrowthAnalystInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]


class GrowthAnalystOutput(TypedDict):
    growth_analysis: dict[str, Any]


class GrowthAnalystAgent(BaseAgent):
    """Computes 3-year CAGRs for revenue, EPS, and FCF; classifies growth quality.

    Expected context keys (GrowthAnalystInput):
        tickers: list of ticker symbols
        raw_data: dict keyed by ticker with prices, financials sub-dicts
        fundamental_analysis: dict keyed by ticker (for pe_ratio, forward_pe)

    Adds to context (GrowthAnalystOutput):
        growth_analysis: dict keyed by ticker with growth metrics + Claude verdict
    """

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        t0 = self._log_run_start()

        growth_analysis: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Analysing growth for {ticker}")
            logger.info("[%s] Growth analysis for %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                metrics = self._compute_growth_metrics(ticker, td, fa)
                verdict = self._get_claude_verdict(ticker, metrics, td)
                result = {**metrics, **verdict}
                growth_analysis[ticker] = result
                self._emit("agent_ticker_complete", {
                    "growth_verdict": result.get("growth_verdict"),
                    "growth_quality_score": result.get("growth_quality_score"),
                    "revenue_cagr_3y_pct": result.get("revenue_cagr_3y_pct"),
                    "eps_cagr_3y_pct": result.get("eps_cagr_3y_pct"),
                    "fcf_cagr_3y_pct": result.get("fcf_cagr_3y_pct"),
                    "peg_ratio": result.get("peg_ratio"),
                    "revenue_trend": result.get("revenue_trend"),
                    "reasoning": result.get("reasoning", ""),
                    "growth_catalysts": result.get("growth_catalysts", []),
                    "growth_risks": result.get("growth_risks", []),
                }, ticker=ticker, message=f"{ticker}: {result.get('growth_verdict', 'unknown')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                growth_analysis[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["growth_analysis"] = growth_analysis
        self._log_run_end(t0)
        return context

    def _compute_growth_metrics(
        self, ticker: str, td: dict[str, Any], fa: dict[str, Any]
    ) -> dict[str, Any]:
        fins = td.get("financials", {})
        income_stmts = fins.get("income_statement", [])
        cash_flows = fins.get("cash_flow", [])

        # ── Revenue CAGR ──────────────────────────────────────────────────────
        revenue_cagr = self._compute_cagr(
            records=income_stmts,
            keys=["Total Revenue", "TotalRevenue", "Revenue"],
            years=3,
        )

        # ── EPS CAGR ──────────────────────────────────────────────────────────
        # Use diluted EPS from income statement if available, else derive from net income
        eps_cagr = self._compute_cagr(
            records=income_stmts,
            keys=["Diluted EPS", "Basic EPS", "EPS"],
            years=3,
        )
        if eps_cagr is None:
            # Fallback: derive from net income CAGR (proxy)
            eps_cagr = self._compute_cagr(
                records=income_stmts,
                keys=["Net Income", "NetIncome", "Net Income Common Stockholders"],
                years=3,
            )

        # ── FCF CAGR ──────────────────────────────────────────────────────────
        fcf_cagr = self._compute_cagr(
            records=cash_flows,
            keys=["Free Cash Flow", "FreeCashFlow"],
            years=3,
        )

        # ── Revenue trend (last 2 years vs prior 2 years) ─────────────────────
        revenue_values = self._extract_series(income_stmts, ["Total Revenue", "TotalRevenue", "Revenue"])
        revenue_trend = self._classify_trend(revenue_values)

        # ── EPS trend ─────────────────────────────────────────────────────────
        eps_values = self._extract_series(income_stmts, ["Diluted EPS", "Basic EPS", "Net Income", "NetIncome"])
        eps_trend = self._classify_trend(eps_values)

        # ── FCF trend ─────────────────────────────────────────────────────────
        fcf_values = self._extract_series(cash_flows, ["Free Cash Flow", "FreeCashFlow"])
        fcf_trend = self._classify_trend(fcf_values)

        # ── PEG ratio ─────────────────────────────────────────────────────────
        peg_ratio = fa.get("peg_ratio")
        if peg_ratio is None and fa.get("pe_ratio") and eps_cagr and eps_cagr > 0:
            peg_ratio = calculate_peg_ratio(fa["pe_ratio"], eps_cagr)

        # ── Forward growth estimate ───────────────────────────────────────────
        trailing_eps = fins.get("trailing_eps")
        forward_eps = fins.get("forward_eps")
        forward_growth_est = None
        if trailing_eps and forward_eps and trailing_eps > 0:
            forward_growth_est = round(((forward_eps - trailing_eps) / abs(trailing_eps)) * 100, 2)

        return {
            "revenue_cagr_3y_pct": revenue_cagr,
            "eps_cagr_3y_pct": eps_cagr,
            "fcf_cagr_3y_pct": fcf_cagr,
            "revenue_trend": revenue_trend,
            "eps_trend": eps_trend,
            "fcf_trend": fcf_trend,
            "peg_ratio": peg_ratio,
            "forward_growth_estimate_pct": forward_growth_est,
            "revenue_history": [round(v / 1e9, 2) for v in revenue_values if v][:4],
            "fcf_history": [round(v / 1e9, 2) for v in fcf_values if v][:4],
        }

    def _extract_series(self, records: list[dict[str, Any]], keys: list[str]) -> list[float | None]:
        """Extract a time series from financial statement records (newest first)."""
        values: list[float | None] = []
        for r in records[:4]:
            found = None
            for k in keys:
                v = r.get(k)
                if v is not None and v == v:  # not NaN
                    try:
                        found = float(v)
                        break
                    except (TypeError, ValueError):
                        pass
            values.append(found)
        return values

    def _compute_cagr(
        self, records: list[dict[str, Any]], keys: list[str], years: int = 3
    ) -> float | None:
        """Compute CAGR over `years` years from financial statement records."""
        values = self._extract_series(records, keys)
        # records are newest-first; we want [newest, ..., oldest]
        valid = [(i, v) for i, v in enumerate(values) if v is not None and v > 0]
        if len(valid) < 2:
            return None
        newest_idx, newest_val = valid[0]
        oldest_idx, oldest_val = valid[-1]
        n_years = oldest_idx - newest_idx
        if n_years <= 0:
            return None
        n_years = min(n_years, years)
        try:
            cagr = ((newest_val / oldest_val) ** (1 / n_years) - 1) * 100
            return round(cagr, 2)
        except (ZeroDivisionError, ValueError):
            return None

    def _classify_trend(self, values: list[float | None]) -> str:
        """Classify trend direction from a newest-first series."""
        clean = [v for v in values if v is not None]
        if len(clean) < 2:
            return "stable"
        # Compare most recent to oldest available
        if clean[0] > clean[-1] * 1.05:
            # Check if growth is accelerating (recent growth > earlier growth)
            if len(clean) >= 3:
                recent_growth = (clean[0] - clean[1]) / abs(clean[1]) if clean[1] != 0 else 0
                earlier_growth = (clean[1] - clean[-1]) / abs(clean[-1]) if clean[-1] != 0 else 0
                return "accelerating" if recent_growth > earlier_growth else "stable"
            return "stable"
        elif clean[0] < clean[-1] * 0.95:
            return "declining"
        else:
            return "stable"

    def _get_claude_verdict(
        self, ticker: str, metrics: dict[str, Any], td: dict[str, Any]
    ) -> dict[str, Any]:
        sec = td.get("sec_filing", {})
        mda = ((sec.get("key_sections") or {}).get("mda") or "")[:1000]

        prompt = f"""Evaluate the growth quality of {ticker} and return ONLY valid JSON (no markdown fences).

## Computed Growth Metrics
{json.dumps(metrics, indent=2)}

## Management Discussion & Analysis (excerpt)
{mda or "Not available"}

## Task
1. Classify the growth verdict (high_quality_growth / steady_growth / slowing_growth / value_trap_risk / turnaround)
2. Assign a growth quality score (1–10)
3. Identify 2 growth catalysts and 2 growth risks
4. Write 3-4 sentences of reasoning

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return _parse_json(raw, ticker, fallback={
            "growth_verdict": "steady_growth",
            "growth_quality_score": 5,
            "growth_risks": [],
            "growth_catalysts": [],
        })


def _parse_json(raw: str, ticker: str, fallback: dict) -> dict[str, Any]:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse JSON for %s", ticker)
    return {**fallback, "reasoning": raw[:300]}
