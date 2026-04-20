"""AIRiskAnalystAgent — AI-specific structural risks (commoditization, capex trap, geopolitics, …)."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents._ai_utils import format_financial_summary, parse_json
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AIRiskInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]
    peer_comparison: dict[str, Any]
    layer_classification: dict[str, Any]
    value_creation: dict[str, Any]
    value_capture: dict[str, Any]


class AIRiskOutput(TypedDict):
    ai_risk: dict[str, Any]


class AIRiskAnalystAgent(BaseAgent):
    """Identify AI-era structural risks that the base risk agents do not capture."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        peers: dict[str, Any] = context.get("peer_comparison", {})
        layer_cls: dict[str, Any] = context.get("layer_classification", {})
        creation: dict[str, Any] = context.get("value_creation", {})
        capture: dict[str, Any] = context.get("value_capture", {})
        t0 = self._log_run_start()

        risks: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Screening AI risks for {ticker}")
            logger.info("[%s] AI risk for %s", self.name, ticker)
            try:
                lc = layer_cls.get(ticker, {})
                if not lc.get("activate_ai_agents", True) or lc.get("ai_exposure_type") == "MINIMAL":
                    risks[ticker] = _neutral_placeholder(lc)
                    self._emit("agent_ticker_complete", risks[ticker], ticker=ticker,
                               message=f"{ticker}: no AI-specific risks (NEUTRAL / MINIMAL exposure)")
                    continue

                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                pa = peers.get(ticker, {})
                vcr = creation.get(ticker, {})
                vcp = capture.get(ticker, {})
                result = self._score(ticker, td, fa, pa, lc, vcr, vcp)
                risks[ticker] = result
                self._emit("agent_ticker_complete", {
                    "overall_risk_level": result.get("overall_risk_level"),
                    "risk_score": result.get("risk_score"),
                    "primary_risk": result.get("primary_risk", ""),
                    "risks": result.get("risks", []),
                    "bear_case_scenario": result.get("bear_case_scenario", ""),
                    "thesis_breaker": result.get("thesis_breaker", ""),
                }, ticker=ticker, message=f"{ticker}: risk {result.get('overall_risk_level')} ({result.get('risk_score')}/100)")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                risks[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["ai_risk"] = risks
        self._log_run_end(t0)
        return context

    def _score(
        self,
        ticker: str,
        td: dict[str, Any],
        fa: dict[str, Any],
        pa: dict[str, Any],
        lc: dict[str, Any],
        vcr: dict[str, Any],
        vcp: dict[str, Any],
    ) -> dict[str, Any]:
        summary = format_financial_summary(ticker, td, fa, pa)

        prompt = f"""Screen AI-specific structural risks for {ticker} and return ONLY valid JSON (no markdown fences).

## Company snapshot
{summary}

## Layer classification
Primary: {lc.get('primary_layer')} — {lc.get('primary_layer_label')}
Secondary: {lc.get('secondary_layer')}
AI exposure: {lc.get('ai_exposure_type')} ({lc.get('ai_exposure_score')}/100)
Focus: {lc.get('layer_specific_focus')}

## Value chain context
Creation: current {vcr.get('current_creation_score')} → future {vcr.get('future_creation_score')}
  ai_role: {vcr.get('ai_role')} | ceiling: {vcr.get('future_creation_ceiling')} | moat: {vcr.get('key_moat')}
Capture: current {vcp.get('current_capture_score')} → future {vcp.get('future_capture_score')}
  trajectory: {vcp.get('future_capture_trajectory')} | commoditization: {vcp.get('commoditization_risk')}
  leakage source: {vcp.get('value_leakage_source')}

## Capital intensity signals
ROE: {fa.get('return_on_equity_pct')}% | ROA: {fa.get('return_on_assets_pct')}%
FCF: {fa.get('free_cash_flow_b')}B | Revenue growth: {fa.get('revenue_growth_pct')}%

## Task
Follow the 4-step method in your system prompt.
Focus on risks that the BASE platform agents do NOT already cover:
- Skip generic macro / rate / FX / recession risk (covered elsewhere)
- Skip standard valuation multiple compression risk (covered by Fundamental)
- DO focus on: commoditization, displacement, capex trap, customer concentration on
  hyperscalers, geopolitical supply chain fragility, AI regulation, moat erosion,
  AI cycle exposure.

Return the JSON structure defined in your system prompt exactly. Include the full
8-type screen even if some are dismissed in one line — the caller wants to see that
you checked all of them."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.15,
        )
        return parse_json(raw, ticker, fallback={
            "overall_risk_level": "MODERATE",
            "risk_score": 40,
            "primary_risk": "Unspecified — model parse fallback",
            "risks": [],
            "bear_case_scenario": "Fallback — could not parse model output.",
            "thesis_breaker": "Not identified",
        })


def _neutral_placeholder(lc: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_risk_level": "LOW",
        "risk_score": 15,
        "primary_risk": "No material AI-specific risk for this business model.",
        "risks": [],
        "bear_case_scenario": "AI is not a material driver for this company over 3-5y. Bear case is covered by standard fundamental / sentiment risks.",
        "thesis_breaker": "N/A — ticker has NEUTRAL / MINIMAL AI exposure.",
        "skipped": True,
        "skipped_reason": f"ai_exposure_type={lc.get('ai_exposure_type')} primary_layer={lc.get('primary_layer')}",
    }


__all__ = ["AIRiskAnalystAgent", "AIRiskInput", "AIRiskOutput"]
