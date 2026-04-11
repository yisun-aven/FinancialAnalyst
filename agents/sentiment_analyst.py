"""SentimentAnalystAgent — assesses market sentiment for each ticker."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.web_search import WEB_SEARCH_TOOL

logger = logging.getLogger(__name__)


class SentimentAnalystInput(TypedDict):
    tickers: list[str]
    raw_data: dict[str, Any]


class SentimentAnalystOutput(TypedDict):
    sentiment_analysis: dict[str, Any]


class SentimentAnalystAgent(BaseAgent):
    """Analyses news, analyst ratings, and insider activity per ticker."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        raw_data: dict[str, Any] = context.get("raw_data", {})
        t0 = self._log_run_start()

        sentiment_analysis: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Analysing sentiment for {ticker}")
            logger.info("[%s] Sentiment for %s", self.name, ticker)
            try:
                td = raw_data.get(ticker, {})
                result = self._analyse(ticker, td)
                sentiment_analysis[ticker] = result
                self._emit("agent_ticker_complete", {
                    "sentiment_score": result.get("sentiment_score"),
                    "sentiment_label": result.get("sentiment_label"),
                    "analyst_consensus": result.get("analyst_consensus"),
                    "insider_activity": result.get("insider_activity"),
                    "top_headlines": result.get("top_headlines", [])[:3],
                    "reasoning": result.get("reasoning", ""),
                }, ticker=ticker, message=f"{ticker}: {result.get('sentiment_label', 'unknown')}")
            except Exception as exc:
                logger.error("[%s] Error on %s: %s", self.name, ticker, exc)
                sentiment_analysis[ticker] = {"error": str(exc)}
                self._emit("agent_ticker_complete", {"error": str(exc)}, ticker=ticker)

        context["sentiment_analysis"] = sentiment_analysis
        self._log_run_end(t0)
        return context

    def _analyse(self, ticker: str, td: dict[str, Any]) -> dict[str, Any]:
        ratings = td.get("analyst_ratings", {})
        prices = td.get("prices", {})

        prompt = f"""You are a market sentiment analyst. Analyse sentiment for {ticker}.

## Analyst Ratings
{_fmt_ratings(ratings)}

## Price Context
{_fmt_price(prices)}

Search the web for:
1. Recent news about {ticker} (last 30 days)
2. Any insider buying/selling at {ticker}

Return ONLY valid JSON:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "very_bearish"|"bearish"|"neutral"|"bullish"|"very_bullish",
  "top_headlines": [{{"headline": "...", "date": "YYYY-MM-DD", "sentiment": "positive|neutral|negative"}}],
  "analyst_consensus": "<one sentence>",
  "insider_activity": "<one sentence or 'No significant activity'>",
  "reasoning": "<2-3 sentences>"
}}"""

        raw = self.call_claude(
            [{"role": "user", "content": prompt}],
            tools=[WEB_SEARCH_TOOL],
            temperature=0.1,
        )

        result = _parse_json(raw, ticker)
        if not result:
            score = _score_from_ratings(ratings)
            result = {
                "sentiment_score": score,
                "sentiment_label": "neutral",
                "top_headlines": [],
                "analyst_consensus": ratings.get("recommendation_key", "unknown"),
                "insider_activity": "Could not retrieve",
                "reasoning": "Fallback from analyst ratings only.",
            }
        return result


def _fmt_ratings(r: dict[str, Any]) -> str:
    if "error" in r:
        return f"Unavailable: {r['error']}"
    lines = [
        f"Consensus: {r.get('recommendation_key','N/A').upper()}",
        f"Mean: {r.get('recommendation_mean','N/A')} (1=Strong Buy, 5=Sell)",
        f"Analysts: {r.get('number_of_analysts','N/A')}",
        f"Targets: Low ${r.get('target_low_price','N/A')} / Mean ${r.get('target_mean_price','N/A')} / High ${r.get('target_high_price','N/A')}",
    ]
    for ch in (r.get("recent_upgrades_downgrades") or [])[:5]:
        if ch.get("action") in ("up", "down", "init"):
            lines.append(f"  {ch.get('date')} {ch.get('firm')}: {ch.get('from_grade','?')}→{ch.get('to_grade','?')} ({ch.get('action')})")
    return "\n".join(lines)


def _fmt_price(p: dict[str, Any]) -> str:
    if "error" in p:
        return "Unavailable"
    cur, hi, lo = p.get("current_price"), p.get("week_52_high"), p.get("week_52_low")
    if cur and hi and lo:
        return (f"${cur} | 52w High ${hi} ({round((hi-cur)/hi*100,1)}% above) | "
                f"52w Low ${lo} ({round((cur-lo)/lo*100,1)}% above low)")
    return f"Current: ${cur}"


def _score_from_ratings(r: dict[str, Any]) -> float:
    rec = r.get("recommendation_mean")
    return round((3 - float(rec)) / 2, 2) if rec else 0.0


def _parse_json(raw: str, ticker: str) -> dict[str, Any] | None:
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
    return None
