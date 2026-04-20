"""LayerClassifierAgent — assigns each ticker to the AI value chain (L1–L7 or NEUTRAL).

Runs first among the AI value chain agents. Its output gates whether the four
downstream AI agents (value_creation, value_capture, pricing_gap, ai_risk) execute
on each ticker — companies with MINIMAL AI exposure short-circuit to save cost.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents._ai_utils import (
    company_overview,
    format_financial_summary,
    parse_json,
    sector_and_industry,
)
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class LayerClassifierInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]


class LayerClassifierOutput(TypedDict):
    layer_classification: dict[str, Any]


class LayerClassifierAgent(BaseAgent):
    """Classify each ticker into one of the 7 AI value chain layers, or NEUTRAL."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        peers: dict[str, Any] = context.get("peer_comparison", {})
        t0 = self._log_run_start()

        classification: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Classifying {ticker} in AI value chain")
            logger.info("[%s] Classifying %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                pa = peers.get(ticker, {})
                result = self._classify(ticker, td, fa, pa)
                classification[ticker] = result
                self._emit("agent_ticker_complete", {
                    "primary_layer": result.get("primary_layer"),
                    "primary_layer_label": result.get("primary_layer_label"),
                    "secondary_layer": result.get("secondary_layer"),
                    "layer_confidence": result.get("layer_confidence"),
                    "ai_exposure_type": result.get("ai_exposure_type"),
                    "ai_exposure_score": result.get("ai_exposure_score"),
                    "activate_ai_agents": result.get("activate_ai_agents"),
                    "layer_specific_focus": result.get("layer_specific_focus"),
                    "layer_rationale": result.get("layer_rationale", ""),
                }, ticker=ticker, message=f"{ticker}: {result.get('primary_layer')} / {result.get('ai_exposure_type')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                classification[ticker] = {"error": str(exc), "activate_ai_agents": False}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["layer_classification"] = classification
        self._log_run_end(t0)
        return context

    def _classify(
        self, ticker: str, td: dict[str, Any], fa: dict[str, Any], pa: dict[str, Any]
    ) -> dict[str, Any]:
        sector, industry = sector_and_industry(ticker, td, pa)
        overview = company_overview(td, max_chars=2000)
        summary = format_financial_summary(ticker, td, fa, pa)

        prompt = f"""Classify {ticker} within the AI value chain and return ONLY valid JSON (no markdown fences).

## Company snapshot
{summary}

## 10-K / 10-Q business overview (excerpt)
{overview or "Not available — use the sector/industry + financials only."}

## Task
Follow the 5-step method in your system prompt. Be decisive.
Pay special attention to:
- Is the company building infrastructure the AI wave requires, or are they just a user of AI?
- Would a 10x scaling of AI compute demand meaningfully change this company's TAM?
- Is "AI" already a meaningful line in their disclosed revenue mix?

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        default_activate = (sector == "Technology") or (industry in ("Semiconductors", "Software—Infrastructure"))
        return parse_json(raw, ticker, fallback={
            "primary_layer": "NEUTRAL",
            "primary_layer_label": "Not classified",
            "secondary_layer": None,
            "layer_confidence": 30,
            "ai_exposure_type": "MINIMAL",
            "ai_exposure_score": 0,
            "layer_rationale": "Classification fell back to NEUTRAL due to parse error.",
            "activate_ai_agents": default_activate,
            "layer_specific_focus": "Standard fundamental lens; no AI-specific focus.",
        })


# Re-exported for convenience (so test imports don't require _ai_utils path)
__all__ = ["LayerClassifierAgent", "LayerClassifierInput", "LayerClassifierOutput"]
