"""TechnicalAnalystAgent — price-based technical indicators per ticker."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.calculations import (
    calculate_52w_position,
    calculate_moving_averages,
    calculate_rsi,
    calculate_volume_trend,
)

logger = logging.getLogger(__name__)


class TechnicalAnalystInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]


class TechnicalAnalystOutput(TypedDict):
    technical_analysis: dict[str, Any]


class TechnicalAnalystAgent(BaseAgent):
    """Computes RSI, moving averages, 52-week position, and volume trend.

    Expected context keys (TechnicalAnalystInput):
        tickers: list of ticker symbols
        raw_data: dict keyed by ticker; each value contains a "prices" sub-dict
                  with "history" (list of OHLCV dicts, newest first) and
                  "info" (yfinance stock.info dict).

    Adds to context (TechnicalAnalystOutput):
        technical_analysis: dict keyed by ticker with computed indicators
                            + Claude verdict.
    """

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        t0 = self._log_run_start()

        technical_analysis: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker,
                       message=f"Technical analysis for {ticker}")
            logger.info("[%s] Technical analysis for %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                metrics = self._compute_indicators(ticker, td)
                verdict = self._get_claude_verdict(ticker, metrics)
                result = {**metrics, **verdict}
                technical_analysis[ticker] = result
                self._emit("agent_ticker_complete", {
                    "technical_verdict": result.get("technical_verdict"),
                    "rsi_14": result.get("rsi_14"),
                    "ma_50": result.get("ma_50"),
                    "ma_200": result.get("ma_200"),
                    "cross_signal": result.get("cross_signal"),
                    "position_52w": result.get("position_52w"),
                    "volume_ratio": result.get("volume_ratio"),
                    "entry_signal": result.get("entry_signal"),
                    "reasoning": result.get("reasoning", ""),
                }, ticker=ticker,
                   message=f"{ticker}: {result.get('technical_verdict', 'unknown')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                technical_analysis[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["technical_analysis"] = technical_analysis
        self._log_run_end(t0)
        return context

    # ── Indicator computation ─────────────────────────────────────────────

    def _compute_indicators(self, ticker: str, td: dict[str, Any]) -> dict[str, Any]:
        prices_block = td.get("prices", {})
        history: list[dict[str, Any]] = prices_block.get("history", [])
        info: dict[str, Any] = prices_block.get("info", {})

        # history is newest-first from yfinance; reverse for chronological order
        history_asc = list(reversed(history))

        closes: list[float] = []
        volumes: list[float] = []
        for bar in history_asc:
            c = bar.get("Close") or bar.get("close")
            v = bar.get("Volume") or bar.get("volume")
            if c is not None:
                try:
                    closes.append(float(c))
                except (TypeError, ValueError):
                    pass
            if v is not None:
                try:
                    volumes.append(float(v))
                except (TypeError, ValueError):
                    pass

        # ── RSI ───────────────────────────────────────────────────────────
        rsi = calculate_rsi(closes, period=14)

        # ── Moving averages ───────────────────────────────────────────────
        ma_result = calculate_moving_averages(closes, windows=(50, 200))
        ma_50 = ma_result.get("ma_50")
        ma_200 = ma_result.get("ma_200")
        cross_signal = ma_result.get("cross_signal", "neutral")

        # ── 52-week position ──────────────────────────────────────────────
        current_price: float | None = None
        if closes:
            current_price = closes[-1]

        high_52w = info.get("fiftyTwoWeekHigh") or info.get("52WeekHigh")
        low_52w = info.get("fiftyTwoWeekLow") or info.get("52WeekLow")

        # Fallback: derive from price history if info fields are missing
        if high_52w is None and len(closes) >= 252:
            high_52w = max(closes[-252:])
        if low_52w is None and len(closes) >= 252:
            low_52w = min(closes[-252:])
        if high_52w is None and closes:
            high_52w = max(closes)
        if low_52w is None and closes:
            low_52w = min(closes)

        position_52w = calculate_52w_position(current_price, high_52w, low_52w) if current_price else None

        # ── Volume trend ──────────────────────────────────────────────────
        vol_result = calculate_volume_trend(volumes, recent_days=20, baseline_days=90)
        volume_ratio = vol_result.get("volume_ratio")

        # ── RSI zone classification ───────────────────────────────────────
        rsi_zone: str = "neutral"
        if rsi is not None:
            if rsi >= 70:
                rsi_zone = "overbought"
            elif rsi <= 30:
                rsi_zone = "oversold"
            elif rsi >= 60:
                rsi_zone = "bullish"
            elif rsi <= 40:
                rsi_zone = "bearish"

        return {
            "current_price": round(current_price, 2) if current_price else None,
            "rsi_14": rsi,
            "rsi_zone": rsi_zone,
            "ma_50": round(ma_50, 2) if ma_50 else None,
            "ma_200": round(ma_200, 2) if ma_200 else None,
            "cross_signal": cross_signal,
            "high_52w": round(high_52w, 2) if high_52w else None,
            "low_52w": round(low_52w, 2) if low_52w else None,
            "position_52w": position_52w,
            "volume_ratio": volume_ratio,
            "avg_volume_20d": vol_result.get("avg_volume_recent"),
            "avg_volume_90d": vol_result.get("avg_volume_baseline"),
            "price_bars_available": len(closes),
        }

    # ── Claude verdict ────────────────────────────────────────────────────

    def _get_claude_verdict(self, ticker: str, metrics: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""Evaluate the technical setup of {ticker} and return ONLY valid JSON (no markdown fences).

## Computed Technical Indicators
{json.dumps(metrics, indent=2)}

## Task
1. Classify the technical_verdict:
   - "strong_entry"   — RSI oversold/neutral + golden cross + price near 52w low
   - "neutral"        — mixed signals, no clear edge
   - "avoid_entry"    — death cross or price far above 52w low with no pullback
   - "overbought"     — RSI >= 70 and price near 52w high
2. Set entry_signal: "buy" | "hold" | "avoid"
3. Write 2-3 sentences of reasoning explaining the key technical factors.
4. List up to 2 technical_risks (e.g. "death cross in effect", "RSI overbought").
5. List up to 2 technical_supports (e.g. "price near 52w low", "volume increasing").

Return exactly this JSON structure:
{{
  "technical_verdict": "...",
  "entry_signal": "...",
  "reasoning": "...",
  "technical_risks": ["..."],
  "technical_supports": ["..."]
}}"""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return _parse_json(raw, ticker, fallback={
            "technical_verdict": "neutral",
            "entry_signal": "hold",
            "technical_risks": [],
            "technical_supports": [],
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
