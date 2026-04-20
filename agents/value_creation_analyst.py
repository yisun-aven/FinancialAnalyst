"""ValueCreationAnalystAgent — scores real-world economic value creation (now + 3–5y).

Runs after the LayerClassifier. For tickers with `activate_ai_agents == False`,
returns a short NEUTRAL placeholder so the pipeline still produces uniform output
without paying the API cost.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents._ai_utils import company_overview, format_financial_summary, parse_json
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ValueCreationInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]
    growth_analysis: dict[str, Any]
    layer_classification: dict[str, Any]


class ValueCreationOutput(TypedDict):
    value_creation: dict[str, Any]


class ValueCreationAnalystAgent(BaseAgent):
    """Score how much real economic value the company creates today and in a 3–5y AI scenario."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        growth: dict[str, Any] = context.get("growth_analysis", {})
        peers: dict[str, Any] = context.get("peer_comparison", {})
        layer_cls: dict[str, Any] = context.get("layer_classification", {})
        t0 = self._log_run_start()

        creation: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Scoring value creation for {ticker}")
            logger.info("[%s] Scoring %s", self.name, ticker)
            try:
                lc = layer_cls.get(ticker, {})
                if not lc.get("activate_ai_agents", True) or lc.get("ai_exposure_type") == "MINIMAL":
                    creation[ticker] = _neutral_placeholder(lc)
                    self._emit("agent_ticker_complete", creation[ticker], ticker=ticker,
                               message=f"{ticker}: skipped (NEUTRAL / MINIMAL exposure)")
                    continue

                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                ga = growth.get(ticker, {})
                pa = peers.get(ticker, {})
                result = self._score(ticker, td, fa, ga, pa, lc)
                creation[ticker] = result
                self._emit("agent_ticker_complete", {
                    "current_creation_score": result.get("current_creation_score"),
                    "current_creation_label": result.get("current_creation_label"),
                    "future_creation_score": result.get("future_creation_score"),
                    "future_creation_ceiling": result.get("future_creation_ceiling"),
                    "ai_role": result.get("ai_role"),
                    "tam_expansion_potential": result.get("tam_expansion_potential"),
                    "creation_thesis": result.get("creation_thesis", ""),
                    "key_moat": result.get("key_moat", ""),
                }, ticker=ticker, message=f"{ticker}: {result.get('current_creation_label')} / future {result.get('future_creation_ceiling')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                creation[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["value_creation"] = creation
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
    ) -> dict[str, Any]:
        summary = format_financial_summary(ticker, td, fa, pa)
        overview = company_overview(td, max_chars=1800)

        prompt = f"""Score the value creation profile of {ticker} and return ONLY valid JSON (no markdown fences).

## Company snapshot
{summary}

## Layer classification (from upstream agent)
Primary layer: {lc.get('primary_layer')} — {lc.get('primary_layer_label')}
Secondary layer: {lc.get('secondary_layer')}
AI exposure: {lc.get('ai_exposure_type')} (score {lc.get('ai_exposure_score')}/100)
Focus: {lc.get('layer_specific_focus')}
Rationale: {lc.get('layer_rationale')}

## Growth signals (from upstream agent)
Revenue CAGR 3Y: {ga.get('revenue_cagr_3y_pct')}% | EPS CAGR 3Y: {ga.get('eps_cagr_3y_pct')}%
FCF CAGR 3Y: {ga.get('fcf_cagr_3y_pct')}% | Growth verdict: {ga.get('growth_verdict')}
Revenue trend: {ga.get('revenue_trend')}

## 10-K / 10-Q business overview (excerpt)
{overview or "Not available"}

## Task
Follow the 5-step method in your system prompt. Ground your scoring in:
1. The specific problem this company solves (be concrete)
2. Their AI role (BUILDING / ACCELERATED / DISRUPTED / NEUTRAL)
3. Defensible TAM expansion under the AI scenario (3–5y)
4. The single most important moat (physical > informational, all else equal)

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.15,
        )
        return parse_json(raw, ticker, fallback={
            "current_creation_score": 50,
            "current_creation_label": "INCREMENTAL",
            "future_creation_ceiling": "MODERATE",
            "future_creation_score": 50,
            "ai_role": "NEUTRAL",
            "tam_expansion_potential": "LINEAR",
            "creation_thesis": "Fallback — could not parse model output.",
            "key_moat": "Unknown",
        })


def _neutral_placeholder(lc: dict[str, Any]) -> dict[str, Any]:
    """Return a low-cost NEUTRAL placeholder for tickers the classifier skipped."""
    return {
        "current_creation_score": 50,
        "current_creation_label": "INCREMENTAL",
        "future_creation_ceiling": "MODERATE",
        "future_creation_score": 50,
        "ai_role": "NEUTRAL",
        "tam_expansion_potential": "LINEAR",
        "creation_thesis": (
            "Skipped AI-specific value creation scoring because the layer classifier "
            "flagged this company as NEUTRAL / MINIMAL AI exposure. Standard fundamental "
            "and growth agents remain authoritative for this ticker."
        ),
        "key_moat": "See fundamental analysis",
        "skipped": True,
        "skipped_reason": f"ai_exposure_type={lc.get('ai_exposure_type')} primary_layer={lc.get('primary_layer')}",
    }


__all__ = ["ValueCreationAnalystAgent", "ValueCreationInput", "ValueCreationOutput"]
