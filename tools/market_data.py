"""Market data tools — wrappers around yfinance and Alpha Vantage.

All functions return plain dicts so they are easy to serialize and
pass through the agent context without any ORM / model dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
import yfinance as yf

from config.settings import get_settings

logger = logging.getLogger(__name__)

_ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"


# ── Price & market data ───────────────────────────────────────────────────────

def fetch_price_data(ticker: str, period: str = "1y") -> dict[str, Any]:
    """Fetch OHLCV price history and key market stats for a ticker via yfinance.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        period: yfinance period string ("1mo", "6mo", "1y", "2y", etc.).

    Returns:
        Dict with keys:
            ticker, current_price, previous_close, day_high, day_low,
            week_52_high, week_52_low, market_cap, shares_outstanding,
            beta, history (list of OHLCV dicts, newest last).
    """
    logger.info("Fetching price data for %s (period=%s)", ticker, period)
    stock = yf.Ticker(ticker)
    info = stock.info

    hist_df = stock.history(period=period)
    history = [
        {
            "date": str(idx.date()),
            "open": round(row["Open"], 4),
            "high": round(row["High"], 4),
            "low": round(row["Low"], 4),
            "close": round(row["Close"], 4),
            "volume": int(row["Volume"]),
        }
        for idx, row in hist_df.iterrows()
    ]

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None and history:
        current_price = history[-1]["close"]

    return {
        "ticker": ticker,
        "current_price": current_price,
        "previous_close": info.get("previousClose"),
        "day_high": info.get("dayHigh"),
        "day_low": info.get("dayLow"),
        "week_52_high": info.get("fiftyTwoWeekHigh"),
        "week_52_low": info.get("fiftyTwoWeekLow"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "beta": info.get("beta"),
        "history": history,
    }


# ── Financials ────────────────────────────────────────────────────────────────

def fetch_financials(ticker: str) -> dict[str, Any]:
    """Fetch income statement, balance sheet, and cash flow via yfinance.

    All monetary values are in USD (as reported by yfinance — typically millions
    for large caps, but units vary; label each value with its raw amount).

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Dict with keys:
            ticker, currency,
            income_statement  (list of annual period dicts, newest first),
            balance_sheet     (list of annual period dicts, newest first),
            cash_flow         (list of annual period dicts, newest first),
            trailing_eps, forward_eps, pe_ratio, forward_pe,
            ebitda, total_debt, free_cash_flow.
    """
    logger.info("Fetching financials for %s", ticker)
    stock = yf.Ticker(ticker)
    info = stock.info

    def _df_to_records(df) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
        """Convert a yfinance financial DataFrame to a list of period dicts."""
        if df is None or df.empty:
            return []
        records = []
        for col in df.columns:
            period_dict: dict[str, Any] = {"period": str(col.date()) if hasattr(col, "date") else str(col)}
            for idx in df.index:
                val = df.loc[idx, col]
                # Convert numpy types to plain Python for JSON safety
                if hasattr(val, "item"):
                    val = val.item()
                period_dict[str(idx)] = val if val == val else None  # NaN → None
            records.append(period_dict)
        return records

    return {
        "ticker": ticker,
        "currency": info.get("currency", "USD"),
        "income_statement": _df_to_records(stock.income_stmt),
        "balance_sheet": _df_to_records(stock.balance_sheet),
        "cash_flow": _df_to_records(stock.cash_flow),
        # Key summary metrics from info (pre-computed by Yahoo)
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "ebitda": info.get("ebitda"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "free_cash_flow": info.get("freeCashflow"),
        "revenue_growth": info.get("revenueGrowth"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "return_on_assets": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
    }


def fetch_analyst_ratings(ticker: str) -> dict[str, Any]:
    """Fetch analyst recommendations and price targets via yfinance.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Dict with keys:
            ticker, recommendation_mean (1=Strong Buy … 5=Sell),
            recommendation_key (e.g. "buy"), number_of_analysts,
            target_mean_price, target_high_price, target_low_price,
            recent_upgrades_downgrades (list of last 10 changes).
    """
    logger.info("Fetching analyst ratings for %s", ticker)
    stock = yf.Ticker(ticker)
    info = stock.info

    upgrades_df = stock.upgrades_downgrades
    recent_changes: list[dict[str, Any]] = []
    if upgrades_df is not None and not upgrades_df.empty:
        for idx, row in upgrades_df.head(10).iterrows():
            recent_changes.append({
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                "firm": row.get("Firm", ""),
                "to_grade": row.get("ToGrade", ""),
                "from_grade": row.get("FromGrade", ""),
                "action": row.get("Action", ""),
            })

    return {
        "ticker": ticker,
        "recommendation_mean": info.get("recommendationMean"),
        "recommendation_key": info.get("recommendationKey"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "target_mean_price": info.get("targetMeanPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "recent_upgrades_downgrades": recent_changes,
    }


# ── Macro data ────────────────────────────────────────────────────────────────

def fetch_macro_data() -> dict[str, Any]:
    """Fetch macro indicators from Alpha Vantage.

    Requires ALPHA_VANTAGE_API_KEY in .env.

    Returns:
        Dict with keys:
            fed_funds_rate (%, latest monthly value),
            cpi_yoy (%, year-over-year CPI change),
            real_gdp_growth (%, latest quarterly annualised growth),
            unemployment_rate (%, latest monthly value).
        Each key maps to {"value": float, "date": str} or {"error": str}.
    """
    settings = get_settings()
    api_key = settings.alpha_vantage_api_key

    if not api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY not set — skipping macro data fetch")
        return {
            "fed_funds_rate": {"error": "API key not configured"},
            "cpi_yoy": {"error": "API key not configured"},
            "real_gdp_growth": {"error": "API key not configured"},
            "unemployment_rate": {"error": "API key not configured"},
        }

    def _latest(function: str, data_key: str = "data") -> dict[str, Any]:
        """Call one Alpha Vantage macro endpoint and return the latest data point."""
        try:
            resp = requests.get(
                _ALPHA_VANTAGE_BASE,
                params={"function": function, "apikey": api_key},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()

            if "Information" in payload:
                # Hit rate limit
                return {"error": "Alpha Vantage rate limit reached"}

            series = payload.get(data_key, [])
            if not series:
                return {"error": f"No data returned for {function}"}

            latest = series[0]  # most recent entry
            return {"value": float(latest["value"]), "date": latest["date"]}

        except Exception as exc:
            logger.error("Alpha Vantage error (%s): %s", function, exc)
            return {"error": str(exc)}

    def _cpi_yoy() -> dict[str, Any]:
        """Compute year-over-year CPI change from monthly series."""
        try:
            resp = requests.get(
                _ALPHA_VANTAGE_BASE,
                params={"function": "CPI", "interval": "monthly", "apikey": api_key},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()

            if "Information" in payload:
                return {"error": "Alpha Vantage rate limit reached"}

            series = payload.get("data", [])
            if len(series) < 13:
                return {"error": "Not enough CPI data for YoY calculation"}

            latest_val = float(series[0]["value"])
            year_ago_val = float(series[12]["value"])
            yoy = round((latest_val - year_ago_val) / year_ago_val * 100, 2)
            return {"value": yoy, "date": series[0]["date"]}

        except Exception as exc:
            logger.error("Alpha Vantage CPI YoY error: %s", exc)
            return {"error": str(exc)}

    logger.info("Fetching macro data from Alpha Vantage")

    return {
        "fed_funds_rate": _latest("FEDERAL_FUNDS_RATE"),
        "cpi_yoy": _cpi_yoy(),
        "real_gdp_growth": _latest("REAL_GDP", data_key="data"),
        "unemployment_rate": _latest("UNEMPLOYMENT"),
    }
