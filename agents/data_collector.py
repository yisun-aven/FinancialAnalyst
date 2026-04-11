"""DataCollectorAgent — fetches all raw data needed for analysis."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agents.base_agent import BaseAgent
from tools.market_data import fetch_analyst_ratings, fetch_financials, fetch_macro_data, fetch_price_data
from tools.sec_filings import fetch_sec_filing

logger = logging.getLogger(__name__)


class DataCollectorInput(TypedDict):
    tickers: list[str]
    run_date: str


class DataCollectorOutput(TypedDict):
    raw_data: dict[str, Any]
    macro_data: dict[str, Any]


class DataCollectorAgent(BaseAgent):
    """Fetches prices, financials, SEC filings, and macro data for each ticker."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        tickers: list[str] = context["tickers"]
        t0 = self._log_run_start()

        try:
            macro_data = fetch_macro_data()
        except Exception as exc:
            logger.warning("[%s] Macro fetch failed: %s", self.name, exc)
            macro_data = {"error": str(exc)}

        raw_data: dict[str, Any] = {}

        for ticker in tickers:
            self._emit("agent_ticker_start", ticker=ticker, message=f"Collecting {ticker}")
            logger.info("[%s] Collecting %s", self.name, ticker)
            td: dict[str, Any] = {}

            try:
                td["prices"] = fetch_price_data(ticker, period="2y")
            except Exception as exc:
                td["prices"] = {"error": str(exc)}

            try:
                td["financials"] = fetch_financials(ticker)
            except Exception as exc:
                td["financials"] = {"error": str(exc)}

            try:
                td["analyst_ratings"] = fetch_analyst_ratings(ticker)
            except Exception as exc:
                td["analyst_ratings"] = {"error": str(exc)}

            try:
                td["sec_filing"] = fetch_sec_filing(ticker, "10-K")
            except Exception as exc:
                try:
                    td["sec_filing"] = fetch_sec_filing(ticker, "10-Q")
                except Exception as exc2:
                    td["sec_filing"] = {"error": str(exc2)}

            raw_data[ticker] = td

            # Emit a summary of what was collected for this ticker
            prices = td.get("prices", {})
            fins = td.get("financials", {})
            filing = td.get("sec_filing", {})
            self._emit("agent_ticker_complete", {
                "company_name": filing.get("company_name") or ticker,
                "current_price": prices.get("current_price"),
                "market_cap_b": round(prices.get("market_cap", 0) / 1e9, 2) if prices.get("market_cap") else None,
                "pe_ratio": fins.get("pe_ratio"),
                "free_cash_flow_b": round(fins.get("free_cash_flow", 0) / 1e9, 2) if fins.get("free_cash_flow") else None,
                "sec_filing_date": filing.get("filing_date"),
                "sec_filing_type": filing.get("form_type"),
                "data_errors": [k for k in ("prices", "financials", "sec_filing") if "error" in td.get(k, {})],
            }, ticker=ticker, message=f"Collected {ticker}")

        context["raw_data"] = raw_data
        context["macro_data"] = macro_data
        self._log_run_end(t0)
        return context
