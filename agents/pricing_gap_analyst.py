"""PricingGapAnalystAgent — the core AI-era mispricing signal.

Compares what the market currently prices into the stock against what the AI
value chain framework suggests is actually coming. The output (`gap_score`,
`gap_direction`, `suggested_action`) is the headline signal that surfaces on
the user's report and drives the top-N re-ranking in screener mode.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents._ai_utils import format_financial_summary, parse_json
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PricingGapInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]
    growth_analysis: dict[str, Any]
    peer_comparison: dict[str, Any]
    layer_classification: dict[str, Any]
    value_creation: dict[str, Any]
    value_capture: dict[str, Any]


class PricingGapOutput(TypedDict):
    pricing_gap: dict[str, Any]


class PricingGapAnalystAgent(BaseAgent):
    """Compute the AI-aware pricing gap and a concrete suggested action per ticker."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        growth: dict[str, Any] = context.get("growth_analysis", {})
        peers: dict[str, Any] = context.get("peer_comparison", {})
        layer_cls: dict[str, Any] = context.get("layer_classification", {})
        creation: dict[str, Any] = context.get("value_creation", {})
        capture: dict[str, Any] = context.get("value_capture", {})
        t0 = self._log_run_start()

        gaps: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Computing pricing gap for {ticker}")
            logger.info("[%s] Pricing gap for %s", self.name, ticker)
            try:
                lc = layer_cls.get(ticker, {})
                if not lc.get("activate_ai_agents", True) or lc.get("ai_exposure_type") == "MINIMAL":
                    gaps[ticker] = _neutral_placeholder(lc, fundamental.get(ticker, {}))
                    self._emit("agent_ticker_complete", gaps[ticker], ticker=ticker,
                               message=f"{ticker}: AI-aware gap skipped (NEUTRAL / MINIMAL exposure)")
                    continue

                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                ga = growth.get(ticker, {})
                pa = peers.get(ticker, {})
                vcr = creation.get(ticker, {})
                vcp = capture.get(ticker, {})
                result = self._score(ticker, td, fa, ga, pa, lc, vcr, vcp)
                gaps[ticker] = result
                self._emit("agent_ticker_complete", {
                    "gap_direction": result.get("gap_direction"),
                    "gap_magnitude": result.get("gap_magnitude"),
                    "gap_score": result.get("gap_score"),
                    "market_implied_growth_rate_pct": result.get("market_implied_growth_rate_pct"),
                    "ai_scenario_growth_rate_pct": result.get("ai_scenario_growth_rate_pct"),
                    "consensus_vs_ai_scenario": result.get("consensus_vs_ai_scenario"),
                    "pricing_narrative": result.get("pricing_narrative", ""),
                    "key_rerating_catalyst": result.get("key_rerating_catalyst", ""),
                    "uncertainty_driver": result.get("uncertainty_driver"),
                    "time_horizon": result.get("time_horizon"),
                    "suggested_action": result.get("suggested_action"),
                }, ticker=ticker, message=f"{ticker}: {result.get('gap_direction')} {result.get('gap_score')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                gaps[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["pricing_gap"] = gaps
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
        vcr: dict[str, Any],
        vcp: dict[str, Any],
    ) -> dict[str, Any]:
        summary = format_financial_summary(ticker, td, fa, pa)

        prompt = f"""Compute the AI value chain pricing gap for {ticker} and return ONLY valid JSON (no markdown fences).

## Current valuation
{summary}
DCF intrinsic value (base): {fa.get('dcf_intrinsic_value')}  |  MoS: {fa.get('dcf_margin_of_safety')}
Target range bear / base / bull: {fa.get('target_price_bear')} / {fa.get('target_price_base')} / {fa.get('target_price_bull')}
Buy-below (bear DCF): {fa.get('buy_below_price')}
Sector median P/E: {pa.get('sector_median_pe')}  |  Sector median EV/EBITDA: {pa.get('sector_median_ev_ebitda')}
Existing fundamental verdict: {fa.get('valuation_verdict')} (confidence {fa.get('confidence')})

## Consensus growth signals
3Y revenue CAGR realised: {ga.get('revenue_cagr_3y_pct')}%  |  EPS CAGR: {ga.get('eps_cagr_3y_pct')}%
Forward growth estimate: {ga.get('forward_growth_estimate_pct')}%

## Upstream AI value chain
Layer: {lc.get('primary_layer')} — {lc.get('primary_layer_label')} (confidence {lc.get('layer_confidence')})
AI exposure: {lc.get('ai_exposure_type')} ({lc.get('ai_exposure_score')}/100)
Layer focus: {lc.get('layer_specific_focus')}

Value creation: current {vcr.get('current_creation_score')} / future {vcr.get('future_creation_score')}
  label: {vcr.get('current_creation_label')} → ceiling: {vcr.get('future_creation_ceiling')}
  ai_role: {vcr.get('ai_role')} | tam: {vcr.get('tam_expansion_potential')}
  moat: {vcr.get('key_moat')}

Value capture: current {vcp.get('current_capture_score')} / future {vcp.get('future_capture_score')}
  rate: {vcp.get('current_capture_rate')} → trajectory: {vcp.get('future_capture_trajectory')}
  pricing power: {vcp.get('pricing_power_rating')}  |  commoditization: {vcp.get('commoditization_risk')}
  leakage: {vcp.get('value_leakage_source')}

## Task
Follow the 6-step method in your system prompt exactly.
1. Back-solve the growth rate currently priced into the multiple. State it clearly.
2. Build the AI-scenario growth rate and defensible multiple from the upstream
   creation/capture scores. Do NOT re-do DCF — the Fundamental agent already did.
3. Quantify the gap and populate `gap_score` in [-10, +10].
4. Name a single concrete re-rating catalyst.
5. Tag the uncertainty driver (STRUCTURAL / EXECUTION / MACRO / SPECULATIVE).
6. Pick a `suggested_action` using the mapping in your system prompt.

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return parse_json(raw, ticker, fallback={
            "market_implied_growth_rate_pct": None,
            "ai_scenario_growth_rate_pct": None,
            "gap_direction": "FAIRLY_PRICED",
            "gap_magnitude": "MARGINAL",
            "gap_score": 0,
            "consensus_vs_ai_scenario": "ALIGNED",
            "pricing_narrative": "Fallback — could not parse model output.",
            "key_rerating_catalyst": "Not identified",
            "uncertainty_driver": "EXECUTION",
            "time_horizon": "MEDIUM",
            "suggested_action": "HOLD",
        })


def _neutral_placeholder(lc: dict[str, Any], fa: dict[str, Any]) -> dict[str, Any]:
    """For NEUTRAL/MINIMAL names, emit a skip marker but still echo the fundamental verdict
    so downstream synthesis and re-ranking have something sensible to work with."""
    fund_verdict = fa.get("valuation_verdict")
    action_map = {
        "undervalued": "ACCUMULATE",
        "fairly_valued": "HOLD",
        "overvalued": "TRIM",
    }
    return {
        "market_implied_growth_rate_pct": None,
        "ai_scenario_growth_rate_pct": None,
        "gap_direction": "FAIRLY_PRICED",
        "gap_magnitude": "MARGINAL",
        "gap_score": 0,
        "consensus_vs_ai_scenario": "ALIGNED",
        "pricing_narrative": (
            "AI value chain lens not applied — ticker is NEUTRAL / MINIMAL AI exposure. "
            "Use the classic Fundamental verdict as the primary signal."
        ),
        "key_rerating_catalyst": "No AI-specific catalyst identified",
        "uncertainty_driver": "MACRO",
        "time_horizon": "MEDIUM",
        "suggested_action": action_map.get(fund_verdict or "", "HOLD"),
        "skipped": True,
        "skipped_reason": f"ai_exposure_type={lc.get('ai_exposure_type')} primary_layer={lc.get('primary_layer')}",
    }


__all__ = ["PricingGapAnalystAgent", "PricingGapInput", "PricingGapOutput"]
