"""FundamentalAnalystAgent — runs valuation models on collected financial data."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.calculations import calculate_dcf, calculate_ev_ebitda, calculate_pe_ratio

logger = logging.getLogger(__name__)

_DEFAULT_WACC = 0.10
_DEFAULT_TERMINAL_GROWTH = 0.03
_MAX_FCF_GROWTH = 0.20


class FundamentalAnalystInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]


class FundamentalAnalystOutput(TypedDict):
    fundamental_analysis: dict[str, Any]


class FundamentalAnalystAgent(BaseAgent):
    """Computes valuation ratios and asks Claude to score each ticker."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        t0 = self._log_run_start()

        fundamental_analysis: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Analysing {ticker}")
            logger.info("[%s] Analysing %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                metrics = self._compute_metrics(ticker, td)
                verdict = self._get_claude_verdict(ticker, metrics, td)
                result = {**metrics, **verdict}
                fundamental_analysis[ticker] = result
                self._emit("agent_ticker_complete", {
                    "valuation_verdict": result.get("valuation_verdict"),
                    "confidence": result.get("confidence"),
                    "current_price": result.get("current_price"),
                    "market_cap_b": result.get("market_cap_b"),
                    "pe_ratio": result.get("pe_ratio"),
                    "ev_ebitda": result.get("ev_ebitda"),
                    "dcf_intrinsic_value": result.get("dcf_intrinsic_value"),
                    "dcf_margin_of_safety": result.get("dcf_margin_of_safety"),
                    "reasoning": result.get("reasoning", ""),
                    "key_risks": result.get("key_risks", []),
                    "key_strengths": result.get("key_strengths", []),
                }, ticker=ticker, message=f"{ticker}: {result.get('valuation_verdict', 'unknown')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                fundamental_analysis[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["fundamental_analysis"] = fundamental_analysis
        self._log_run_end(t0)
        return context

    def _compute_metrics(self, ticker: str, td: dict[str, Any]) -> dict[str, Any]:
        prices = td.get("prices", {})
        fins = td.get("financials", {})
        current_price = prices.get("current_price")
        market_cap = prices.get("market_cap")
        shares_outstanding = prices.get("shares_outstanding")

        trailing_eps = fins.get("trailing_eps")
        pe_ratio = (calculate_pe_ratio(current_price, trailing_eps)
                    if current_price and trailing_eps else fins.get("pe_ratio"))

        ebitda = fins.get("ebitda")
        total_debt = fins.get("total_debt")
        total_cash = fins.get("total_cash")
        ev_ebitda = None
        if market_cap and total_debt is not None and total_cash is not None and ebitda:
            ev_ebitda = calculate_ev_ebitda(
                market_cap / 1e6, total_debt / 1e6, total_cash / 1e6, ebitda / 1e6)

        dcf_intrinsic_value = None
        dcf_margin_of_safety = None
        fcf_history = self._extract_fcf_history(fins.get("cash_flow", []))
        if fcf_history and shares_outstanding and shares_outstanding > 0:
            projected = self._project_fcf(fcf_history)
            if projected:
                try:
                    dcf_intrinsic_value = calculate_dcf(
                        free_cash_flows=projected,
                        terminal_growth_rate=_DEFAULT_TERMINAL_GROWTH,
                        discount_rate=_DEFAULT_WACC,
                        shares_outstanding=shares_outstanding / 1e6,
                    )
                    if dcf_intrinsic_value and current_price:
                        dcf_margin_of_safety = round(
                            (dcf_intrinsic_value - current_price) / dcf_intrinsic_value, 4)
                except Exception:
                    pass

        roe = fins.get("return_on_equity")
        ratio_scorecard: dict[str, Any] = {}
        if roe is not None:
            ratio_scorecard["roe"] = {"value": round(roe * 100, 2), "pass": roe >= 0.15}
        d_e = fins.get("debt_to_equity")
        if d_e is not None:
            ratio_scorecard["debt_to_equity"] = {"value": round(d_e, 2), "pass": d_e <= 150}
        cr = fins.get("current_ratio")
        if cr is not None:
            ratio_scorecard["current_ratio"] = {"value": round(cr, 2), "pass": cr >= 1.0}

        return {
            "current_price": current_price,
            "market_cap_b": round(market_cap / 1e9, 2) if market_cap else None,
            "pe_ratio": pe_ratio,
            "forward_pe": fins.get("forward_pe"),
            "ev_ebitda": ev_ebitda,
            "dcf_intrinsic_value": dcf_intrinsic_value,
            "dcf_margin_of_safety": dcf_margin_of_safety,
            "ratio_scorecard": ratio_scorecard,
            "revenue_growth_pct": round(fins.get("revenue_growth", 0) * 100, 2) if fins.get("revenue_growth") else None,
            "gross_margin_pct": round(fins.get("gross_margins", 0) * 100, 2) if fins.get("gross_margins") else None,
            "operating_margin_pct": round(fins.get("operating_margins", 0) * 100, 2) if fins.get("operating_margins") else None,
            "free_cash_flow_b": round(fins.get("free_cash_flow", 0) / 1e9, 2) if fins.get("free_cash_flow") else None,
        }

    def _extract_fcf_history(self, records: list[dict[str, Any]]) -> list[float]:
        values = []
        for r in records[:4]:
            v = r.get("Free Cash Flow") or r.get("FreeCashFlow")
            if v is not None and v == v:
                values.append(float(v) / 1e6)
        return values

    def _project_fcf(self, history: list[float], years: int = 5) -> list[float]:
        pos = [v for v in history if v > 0]
        if not pos:
            return []
        cagr = ((pos[0] / pos[-1]) ** (1 / max(len(pos) - 1, 1)) - 1) if len(pos) >= 2 else 0.05
        cagr = max(-0.10, min(cagr, _MAX_FCF_GROWTH))
        return [pos[0] * (1 + cagr) ** i for i in range(1, years + 1)]

    def _get_claude_verdict(self, ticker: str, metrics: dict[str, Any], td: dict[str, Any]) -> dict[str, Any]:
        sec = td.get("sec_filing", {})
        overview = ((sec.get("key_sections") or {}).get("business_overview") or "")[:1500]

        prompt = f"""You are a CFA-level analyst. Evaluate {ticker} based on these metrics and return ONLY valid JSON.

## Metrics
{json.dumps(metrics, indent=2)}

## Business Context (10-K excerpt)
{overview or "Not available"}

Return this exact JSON structure:
{{
  "valuation_verdict": "undervalued" | "fairly_valued" | "overvalued",
  "confidence": "high" | "medium" | "low",
  "reasoning": "<2-3 sentences>",
  "key_risks": ["<risk 1>", "<risk 2>"],
  "key_strengths": ["<strength 1>", "<strength 2>"]
}}"""

        raw = self.call_claude([{"role": "user", "content": prompt}], temperature=0.1)
        return _parse_json(raw, ticker, fallback={"valuation_verdict": "unknown", "confidence": "low"})


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
