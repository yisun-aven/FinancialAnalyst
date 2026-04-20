"""ValueCaptureAnalystAgent — scores how much created value flows to the P&L (now + 3–5y)."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents._ai_utils import format_financial_summary, parse_json
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ValueCaptureInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]
    growth_analysis: dict[str, Any]
    peer_comparison: dict[str, Any]
    layer_classification: dict[str, Any]
    value_creation: dict[str, Any]


class ValueCaptureOutput(TypedDict):
    value_capture: dict[str, Any]


class ValueCaptureAnalystAgent(BaseAgent):
    """Score how much of the created value flows to the company's own P&L, now and 3–5y."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        growth: dict[str, Any] = context.get("growth_analysis", {})
        peers: dict[str, Any] = context.get("peer_comparison", {})
        layer_cls: dict[str, Any] = context.get("layer_classification", {})
        creation: dict[str, Any] = context.get("value_creation", {})
        t0 = self._log_run_start()

        capture: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Scoring value capture for {ticker}")
            logger.info("[%s] Scoring %s", self.name, ticker)
            try:
                lc = layer_cls.get(ticker, {})
                if not lc.get("activate_ai_agents", True) or lc.get("ai_exposure_type") == "MINIMAL":
                    capture[ticker] = _neutral_placeholder(lc)
                    self._emit("agent_ticker_complete", capture[ticker], ticker=ticker,
                               message=f"{ticker}: skipped (NEUTRAL / MINIMAL exposure)")
                    continue

                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                ga = growth.get(ticker, {})
                pa = peers.get(ticker, {})
                vc = creation.get(ticker, {})
                result = self._score(ticker, td, fa, ga, pa, lc, vc)
                capture[ticker] = result
                self._emit("agent_ticker_complete", {
                    "current_capture_rate": result.get("current_capture_rate"),
                    "current_capture_score": result.get("current_capture_score"),
                    "future_capture_trajectory": result.get("future_capture_trajectory"),
                    "future_capture_score": result.get("future_capture_score"),
                    "pricing_power_rating": result.get("pricing_power_rating"),
                    "commoditization_risk": result.get("commoditization_risk"),
                    "value_leakage_source": result.get("value_leakage_source"),
                    "capture_thesis": result.get("capture_thesis", ""),
                }, ticker=ticker, message=f"{ticker}: capture {result.get('current_capture_rate')} / {result.get('future_capture_trajectory')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                capture[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["value_capture"] = capture
        self._log_run_end(t0)
        return context

    def _score(
        self,
        ticker: str,
        td: dict[str, Any],
        fa: dict[str, Any],
        ga: dict[str, Any],
        pa: dict[str, Any],
        lc: dict[str, Any],
        vc: dict[str, Any],
    ) -> dict[str, Any]:
        summary = format_financial_summary(ticker, td, fa, pa)

        prompt = f"""Score the value capture profile of {ticker} and return ONLY valid JSON (no markdown fences).

## Company snapshot
{summary}

## Margin & capital signals
Gross margin: {fa.get('gross_margin_pct')}%  |  Operating margin: {fa.get('operating_margin_pct')}%
ROE: {fa.get('return_on_equity_pct')}%  |  ROA: {fa.get('return_on_assets_pct')}%
FCF: {fa.get('free_cash_flow_b')}B  |  FCF CAGR 3Y: {ga.get('fcf_cagr_3y_pct')}%
Sector median P/E: {pa.get('sector_median_pe')}  |  Company P/E: {pa.get('company_pe')}  |  Peer discount: {pa.get('company_pe_discount_pct')}%
Cash flow quality: {_cf_quality(fa.get('cash_flow_quality'))}

## Layer classification
Primary layer: {lc.get('primary_layer')} — {lc.get('primary_layer_label')}
AI exposure: {lc.get('ai_exposure_type')}
Focus: {lc.get('layer_specific_focus')}

## Value creation (from upstream agent)
Current creation: {vc.get('current_creation_label')} ({vc.get('current_creation_score')}/100)
Future ceiling: {vc.get('future_creation_ceiling')} ({vc.get('future_creation_score')}/100)
AI role: {vc.get('ai_role')} | TAM expansion: {vc.get('tam_expansion_potential')}
Key moat: {vc.get('key_moat')}

## Task
Follow the 6-step method in your system prompt. Be explicit about:
1. Is margin structure durable or being eaten (by suppliers, hyperscalers, or AI)?
2. Will the moat help the company keep more of the incremental value AI creates,
   or does AI commoditize their product faster than they can move?
3. Where is the primary leakage today?

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.15,
        )
        return parse_json(raw, ticker, fallback={
            "current_capture_rate": "MED",
            "current_capture_score": 50,
            "future_capture_trajectory": "STABLE",
            "future_capture_score": 50,
            "pricing_power_rating": "MODERATE",
            "commoditization_risk": "MED",
            "value_leakage_source": "Unknown",
            "capture_thesis": "Fallback — could not parse model output.",
        })


def _cf_quality(v: Any) -> str:
    if not v or not isinstance(v, dict):
        return "N/A"
    return f"{v.get('quality', '?')} (OCF/NI={v.get('ratio', '?')})"


def _neutral_placeholder(lc: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_capture_rate": "MED",
        "current_capture_score": 50,
        "future_capture_trajectory": "STABLE",
        "future_capture_score": 50,
        "pricing_power_rating": "MODERATE",
        "commoditization_risk": "MED",
        "value_leakage_source": "See fundamental analysis",
        "capture_thesis": (
            "Skipped AI-specific value capture scoring because the layer classifier "
            "flagged this company as NEUTRAL / MINIMAL AI exposure."
        ),
        "skipped": True,
        "skipped_reason": f"ai_exposure_type={lc.get('ai_exposure_type')} primary_layer={lc.get('primary_layer')}",
    }


__all__ = ["ValueCaptureAnalystAgent", "ValueCaptureInput", "ValueCaptureOutput"]
