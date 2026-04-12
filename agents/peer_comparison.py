"""PeerComparisonAgent — compares each ticker's valuation multiples to sector peers."""

from __future__ import annotations

import json
import logging
import re
import statistics
from typing import Any, TypedDict

import yfinance as yf

from agents.base_agent import BaseAgent
from tools.screener import SECTOR_EVEB_MEDIANS, SECTOR_PE_MEDIANS

logger = logging.getLogger(__name__)

# Number of peer tickers to sample per sector for live median computation
_MAX_PEERS = 8

# Sector → representative peer tickers (used when live screener data is unavailable)
_SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["MSFT", "GOOGL", "META", "NVDA", "ORCL", "CRM", "ADBE", "INTC"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "BMY", "AMGN"],
    "Financials": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "AXP"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "TGT", "LOW"],
    "Consumer Defensive": ["KO", "PEP", "WMT", "PG", "COST", "CL", "KMB", "GIS"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO"],
    "Industrials": ["CAT", "HON", "UPS", "BA", "GE", "MMM", "LMT", "RTX"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL"],
    "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "O", "WELL"],
    "Basic Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "NUE", "CF", "MOS"],
}


class PeerComparisonInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]


class PeerComparisonOutput(TypedDict):
    peer_comparison: dict[str, Any]


class PeerComparisonAgent(BaseAgent):
    """Computes sector-relative valuation discounts/premiums for each ticker.

    Expected context keys (PeerComparisonInput):
        tickers: list of ticker symbols
        raw_data: dict keyed by ticker with prices, financials sub-dicts
        fundamental_analysis: dict keyed by ticker (for pe_ratio, ev_ebitda)

    Adds to context (PeerComparisonOutput):
        peer_comparison: dict keyed by ticker with peer metrics + Claude verdict
    """

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        fundamental: dict[str, Any] = context.get("fundamental_analysis", {})
        t0 = self._log_run_start()

        peer_comparison: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Peer comparison for {ticker}")
            logger.info("[%s] Peer comparison for %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                fa = fundamental.get(ticker, {})
                metrics = self._compute_peer_metrics(ticker, td, fa)
                verdict = self._get_claude_verdict(ticker, metrics, fa)
                result = {**metrics, **verdict}
                peer_comparison[ticker] = result
                self._emit("agent_ticker_complete", {
                    "peer_verdict": result.get("peer_verdict"),
                    "composite_peer_discount_pct": result.get("composite_peer_discount_pct"),
                    "company_pe_discount_pct": result.get("company_pe_discount_pct"),
                    "sector_median_pe": result.get("sector_median_pe"),
                    "sector": result.get("sector"),
                    "peers_used": result.get("peers_used", []),
                    "reasoning": result.get("reasoning", ""),
                }, ticker=ticker, message=f"{ticker}: {result.get('peer_verdict', 'unknown')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                peer_comparison[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["peer_comparison"] = peer_comparison
        self._log_run_end(t0)
        return context

    def _compute_peer_metrics(
        self, ticker: str, td: dict[str, Any], fa: dict[str, Any]
    ) -> dict[str, Any]:
        # ── Determine sector ──────────────────────────────────────────────────
        sector = self._get_sector(ticker, td)

        # ── Company multiples (from fundamental analysis) ─────────────────────
        company_pe = fa.get("pe_ratio")
        company_ev_ebitda = fa.get("ev_ebitda")
        company_pfcf = fa.get("pfcf_ratio")

        # ── Fetch live peer data ──────────────────────────────────────────────
        peer_tickers = [p for p in _SECTOR_PEERS.get(sector, []) if p != ticker][:_MAX_PEERS]
        peer_pe_values: list[float] = []
        peer_eveb_values: list[float] = []
        peers_used: list[str] = []

        for peer in peer_tickers:
            try:
                info = yf.Ticker(peer).info
                pe = info.get("trailingPE") or info.get("forwardPE")
                if pe and 0 < pe < 200:
                    peer_pe_values.append(float(pe))
                ev = info.get("enterpriseToEbitda")
                if ev and 0 < ev < 100:
                    peer_eveb_values.append(float(ev))
                if pe or ev:
                    peers_used.append(peer)
            except Exception:
                pass

        # ── Compute sector medians ────────────────────────────────────────────
        if len(peer_pe_values) >= 3:
            sector_median_pe = round(statistics.median(peer_pe_values), 2)
        else:
            # Fall back to built-in sector benchmarks
            sector_median_pe = SECTOR_PE_MEDIANS.get(sector, SECTOR_PE_MEDIANS["Unknown"])

        if len(peer_eveb_values) >= 3:
            sector_median_ev_ebitda = round(statistics.median(peer_eveb_values), 2)
        else:
            sector_median_ev_ebitda = SECTOR_EVEB_MEDIANS.get(sector, SECTOR_EVEB_MEDIANS["Unknown"])

        # ── Discount calculations ─────────────────────────────────────────────
        pe_discount = None
        if company_pe and sector_median_pe and sector_median_pe > 0:
            pe_discount = round((sector_median_pe - company_pe) / sector_median_pe * 100, 2)

        eveb_discount = None
        if company_ev_ebitda and sector_median_ev_ebitda and sector_median_ev_ebitda > 0:
            eveb_discount = round(
                (sector_median_ev_ebitda - company_ev_ebitda) / sector_median_ev_ebitda * 100, 2
            )

        # ── Composite discount (weighted average) ─────────────────────────────
        composite = None
        discounts = [d for d in [pe_discount, eveb_discount] if d is not None]
        if discounts:
            composite = round(sum(discounts) / len(discounts), 2)

        return {
            "sector": sector,
            "peers_used": peers_used,
            "sector_median_pe": sector_median_pe,
            "sector_median_ev_ebitda": sector_median_ev_ebitda,
            "sector_median_pfcf": None,  # not yet computed from live peers
            "company_pe": company_pe,
            "company_ev_ebitda": company_ev_ebitda,
            "company_pfcf": company_pfcf,
            "company_pe_discount_pct": pe_discount,
            "company_ev_ebitda_discount_pct": eveb_discount,
            "composite_peer_discount_pct": composite,
            "live_peer_data_available": len(peers_used) >= 3,
        }

    def _get_sector(self, ticker: str, td: dict[str, Any]) -> str:
        """Resolve sector from yfinance info or fall back to 'Unknown'."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("sector") or "Unknown"
        except Exception:
            return "Unknown"

    def _get_claude_verdict(
        self, ticker: str, metrics: dict[str, Any], fa: dict[str, Any]
    ) -> dict[str, Any]:
        prompt = f"""Evaluate the relative valuation of {ticker} vs its sector peers and return ONLY valid JSON (no markdown fences).

## Peer Comparison Metrics
{json.dumps(metrics, indent=2)}

## Company Fundamentals Summary
PE={fa.get('pe_ratio')} | ForwardPE={fa.get('forward_pe')} | EV/EBITDA={fa.get('ev_ebitda')}
ROE={fa.get('return_on_equity_pct')}% | RevGrowth={fa.get('revenue_growth_pct')}%
Verdict from fundamental analysis: {fa.get('valuation_verdict', 'unknown')}

## Task
1. Classify the peer_verdict (significant_discount / slight_discount / at_par / premium / justified_premium)
2. Compute or confirm composite_peer_discount_pct
3. Write 3-4 sentences of reasoning on relative valuation
4. Note any caveats about data quality or sector comparability

Return the JSON structure defined in your system prompt exactly."""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return _parse_json(raw, ticker, fallback={
            "peer_verdict": "at_par",
            "composite_peer_discount_pct": metrics.get("composite_peer_discount_pct"),
            "reasoning": "Peer comparison data insufficient for full assessment.",
            "peer_comparison_note": "",
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
