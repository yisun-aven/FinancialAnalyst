"""FundamentalAnalystAgent — runs valuation models on collected financial data."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.calculations import (
    calculate_cash_flow_quality,
    calculate_dcf,
    calculate_ev_ebitda,
    calculate_pe_ratio,
    calculate_pfcf_ratio,
    calculate_peg_ratio,
    calculate_target_price,
)

logger = logging.getLogger(__name__)

_DEFAULT_WACC = 0.10
_DEFAULT_TERMINAL_GROWTH = 0.03
_MAX_FCF_GROWTH = 0.20
_DEFAULT_RISK_FREE_RATE = 0.045
_DEFAULT_ERP = 0.055


class FundamentalAnalystInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]


class FundamentalAnalystOutput(TypedDict):
    fundamental_analysis: dict[str, Any]


class FundamentalAnalystAgent(BaseAgent):
    """Computes valuation ratios and asks Claude to score each ticker.

    Expected context keys (FundamentalAnalystInput):
        tickers: list of ticker symbols
        raw_data: dict keyed by ticker with prices, financials, sec_filing sub-dicts

    Adds to context (FundamentalAnalystOutput):
        fundamental_analysis: dict keyed by ticker with metrics + Claude verdict
    """

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
                    "peg_ratio": result.get("peg_ratio"),
                    "pfcf_ratio": result.get("pfcf_ratio"),
                    "target_price_bear": result.get("target_price_bear"),
                    "target_price_base": result.get("target_price_base"),
                    "target_price_bull": result.get("target_price_bull"),
                    "buy_below_price": result.get("buy_below_price"),
                    "cash_flow_quality": result.get("cash_flow_quality"),
                    "reasoning": result.get("reasoning", ""),
                    "key_risks": result.get("key_risks", []),
                    "key_strengths": result.get("key_strengths", []),
                    "entry_strategy": result.get("entry_strategy", ""),
                    "target_price_rationale": result.get("target_price_rationale", ""),
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
        beta = prices.get("beta") or 1.0

        # ── P/E ──────────────────────────────────────────────────────────────
        trailing_eps = fins.get("trailing_eps")
        pe_ratio = (calculate_pe_ratio(current_price, trailing_eps)
                    if current_price and trailing_eps else fins.get("pe_ratio"))

        # ── EV/EBITDA ─────────────────────────────────────────────────────────
        ebitda = fins.get("ebitda")
        total_debt = fins.get("total_debt")
        total_cash = fins.get("total_cash")
        ev_ebitda = None
        if market_cap and total_debt is not None and total_cash is not None and ebitda:
            ev_ebitda = calculate_ev_ebitda(
                market_cap / 1e6, total_debt / 1e6, total_cash / 1e6, ebitda / 1e6)

        # ── FCF history & projections ─────────────────────────────────────────
        fcf_history = self._extract_fcf_history(fins.get("cash_flow", []))
        projected_fcfs: list[float] = []
        if fcf_history and shares_outstanding and shares_outstanding > 0:
            projected_fcfs = self._project_fcf(fcf_history)

        # ── DCF intrinsic value (base case, fixed WACC) ───────────────────────
        dcf_intrinsic_value = None
        dcf_margin_of_safety = None
        if projected_fcfs and shares_outstanding and shares_outstanding > 0:
            try:
                dcf_intrinsic_value = calculate_dcf(
                    free_cash_flows=projected_fcfs,
                    terminal_growth_rate=_DEFAULT_TERMINAL_GROWTH,
                    discount_rate=_DEFAULT_WACC,
                    shares_outstanding=shares_outstanding / 1e6,
                )
                if dcf_intrinsic_value and current_price:
                    dcf_margin_of_safety = round(
                        (dcf_intrinsic_value - current_price) / dcf_intrinsic_value, 4)
            except Exception:
                pass

        # ── Target price range (bull / base / bear) ───────────────────────────
        target_prices: dict[str, Any] = {
            "target_price_base": None,
            "target_price_bull": None,
            "target_price_bear": None,
            "buy_below_price": None,
            "wacc_used": None,
        }
        if projected_fcfs and shares_outstanding and shares_outstanding > 0:
            target_prices = calculate_target_price(
                free_cash_flows=projected_fcfs,
                shares_outstanding=shares_outstanding / 1e6,
                beta=float(beta),
                risk_free_rate=_DEFAULT_RISK_FREE_RATE,
                equity_risk_premium=_DEFAULT_ERP,
                terminal_growth_rate=_DEFAULT_TERMINAL_GROWTH,
            )

        # ── P/FCF ─────────────────────────────────────────────────────────────
        pfcf_ratio = None
        fcf_total = fins.get("free_cash_flow")
        if fcf_total and shares_outstanding and shares_outstanding > 0 and current_price:
            fcf_per_share = fcf_total / shares_outstanding
            pfcf_ratio = calculate_pfcf_ratio(current_price, fcf_per_share)

        # ── PEG ratio ─────────────────────────────────────────────────────────
        peg_ratio = None
        forward_eps = fins.get("forward_eps")
        if pe_ratio and trailing_eps and forward_eps and trailing_eps > 0:
            eps_growth_pct = ((forward_eps - trailing_eps) / abs(trailing_eps)) * 100
            if eps_growth_pct > 0:
                peg_ratio = calculate_peg_ratio(pe_ratio, eps_growth_pct)

        # ── Cash flow quality ─────────────────────────────────────────────────
        cash_flow_quality: dict[str, Any] = {"ratio": None, "quality": "unknown", "note": ""}
        net_income = self._extract_net_income(fins.get("income_statement", []))
        operating_cf = self._extract_operating_cf(fins.get("cash_flow", []))
        if net_income is not None and operating_cf is not None:
            cash_flow_quality = calculate_cash_flow_quality(net_income / 1e6, operating_cf / 1e6)

        # ── Ratio scorecard ───────────────────────────────────────────────────
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
            "beta": round(float(beta), 2),
            "pe_ratio": pe_ratio,
            "forward_pe": fins.get("forward_pe"),
            "peg_ratio": peg_ratio,
            "ev_ebitda": ev_ebitda,
            "pfcf_ratio": pfcf_ratio,
            "dcf_intrinsic_value": dcf_intrinsic_value,
            "dcf_margin_of_safety": dcf_margin_of_safety,
            "target_price_base": target_prices.get("target_price_base"),
            "target_price_bull": target_prices.get("target_price_bull"),
            "target_price_bear": target_prices.get("target_price_bear"),
            "buy_below_price": target_prices.get("buy_below_price"),
            "wacc_used_pct": target_prices.get("wacc_used"),
            "cash_flow_quality": cash_flow_quality,
            "ratio_scorecard": ratio_scorecard,
            "revenue_growth_pct": round(fins.get("revenue_growth", 0) * 100, 2) if fins.get("revenue_growth") else None,
            "gross_margin_pct": round(fins.get("gross_margins", 0) * 100, 2) if fins.get("gross_margins") else None,
            "operating_margin_pct": round(fins.get("operating_margins", 0) * 100, 2) if fins.get("operating_margins") else None,
            "free_cash_flow_b": round(fins.get("free_cash_flow", 0) / 1e9, 2) if fins.get("free_cash_flow") else None,
            "return_on_equity_pct": round(roe * 100, 2) if roe else None,
            "return_on_assets_pct": round(fins.get("return_on_assets", 0) * 100, 2) if fins.get("return_on_assets") else None,
        }

    def _extract_fcf_history(self, records: list[dict[str, Any]]) -> list[float]:
        values = []
        for r in records[:4]:
            v = r.get("Free Cash Flow") or r.get("FreeCashFlow")
            if v is not None and v == v:
                values.append(float(v) / 1e6)
        return values

    def _extract_net_income(self, records: list[dict[str, Any]]) -> float | None:
        if not records:
            return None
        latest = records[0]
        v = latest.get("Net Income") or latest.get("NetIncome")
        return float(v) if v is not None and v == v else None

    def _extract_operating_cf(self, records: list[dict[str, Any]]) -> float | None:
        if not records:
            return None
        latest = records[0]
        v = (latest.get("Operating Cash Flow")
             or latest.get("OperatingCashFlow")
             or latest.get("Cash Flow From Continuing Operating Activities"))
        return float(v) if v is not None and v == v else None

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

        prompt = f"""Evaluate {ticker} based on these computed metrics and return ONLY valid JSON (no markdown fences).

## Computed Metrics
{json.dumps(metrics, indent=2)}

## Business Context (10-K excerpt)
{overview or "Not available"}

## Task
1. Determine valuation verdict (undervalued / fairly_valued / overvalued)
2. Compute or refine the target price range using the provided DCF sensitivity data
3. State the buy-below price (the price at which this stock becomes a compelling buy)
4. Assess cash flow quality and PEG ratio
5. Identify 3 key risks and 3 key strengths

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return _parse_json(raw, ticker, fallback={
            "valuation_verdict": "unknown",
            "confidence": "low",
            "target_price_base": metrics.get("target_price_base"),
            "target_price_bull": metrics.get("target_price_bull"),
            "target_price_bear": metrics.get("target_price_bear"),
            "buy_below_price": metrics.get("buy_below_price"),
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
