"""Stock screener — fast quantitative pre-screen across a large universe.

No Claude API calls are made here. All scoring uses yfinance data only so
the screen can run cheaply across hundreds of tickers in seconds.

Scoring model (0–100 points per ticker):
    P/E discount vs sector      0–25 pts  (lower P/E → more points)
    EV/EBITDA discount          0–20 pts
    P/B discount                0–15 pts
    FCF yield                   0–15 pts  (FCF / market cap)
    Revenue growth              0–10 pts
    Gross margin quality        0–10 pts
    Balance sheet health        0–5 pts   (current ratio ≥ 1.0)

Stocks with negative earnings, no revenue, or missing critical data
are filtered out before scoring.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# Sector median P/E benchmarks (rough industry consensus)
SECTOR_PE_MEDIANS: dict[str, float] = {
    "Technology": 28.0,
    "Healthcare": 20.0,
    "Financials": 12.0,
    "Consumer Cyclical": 18.0,
    "Consumer Defensive": 22.0,
    "Energy": 12.0,
    "Utilities": 18.0,
    "Real Estate": 20.0,
    "Industrials": 20.0,
    "Basic Materials": 15.0,
    "Communication Services": 20.0,
    "Unknown": 20.0,
}

SECTOR_EVEB_MEDIANS: dict[str, float] = {
    "Technology": 20.0,
    "Healthcare": 14.0,
    "Financials": 10.0,
    "Consumer Cyclical": 12.0,
    "Consumer Defensive": 14.0,
    "Energy": 8.0,
    "Utilities": 12.0,
    "Real Estate": 18.0,
    "Industrials": 14.0,
    "Basic Materials": 10.0,
    "Communication Services": 12.0,
    "Unknown": 14.0,
}


# ── Universe fetchers ─────────────────────────────────────────────────────────

def get_sp500_tickers() -> list[str]:
    """Fetch current S&P 500 constituent tickers from Wikipedia."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers={"User-Agent": "FinancialAnalystBot/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        # Parse the first table — Symbol is column 0
        import re
        rows = re.findall(r"<tr>\s*<td[^>]*>([A-Z]{1,5}(?:\.[A-Z])?)</td>", resp.text)
        tickers = [t.replace(".", "-") for t in rows if t]  # yfinance uses BRK-B not BRK.B
        if tickers:
            logger.info("Fetched %d S&P 500 tickers from Wikipedia", len(tickers))
            return tickers
    except Exception as exc:
        logger.warning("Wikipedia S&P 500 fetch failed (%s) — using fallback list", exc)

    return _sp500_fallback()


def get_nasdaq100_tickers() -> list[str]:
    """Fetch Nasdaq-100 tickers from Wikipedia."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/Nasdaq-100",
            headers={"User-Agent": "FinancialAnalystBot/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        import re
        rows = re.findall(r"<td[^>]*>([A-Z]{2,5})</td>", resp.text)
        # Deduplicate while preserving order
        seen: set[str] = set()
        tickers = [t for t in rows if t not in seen and not seen.add(t)]  # type: ignore[func-returns-value]
        if len(tickers) >= 80:
            logger.info("Fetched %d Nasdaq-100 tickers", len(tickers))
            return tickers[:100]
    except Exception as exc:
        logger.warning("Nasdaq-100 fetch failed (%s) — using fallback", exc)

    return _nasdaq100_fallback()


def get_taiwan_tickers() -> list[str]:
    """Return a broad list of Taiwan Stock Exchange (TWSE) and OTC tickers.

    Tickers use the yfinance convention: numeric code + '.TW' for TWSE main board
    and '.TWO' for OTC/emerging board.  We fetch the TWSE constituent list from
    the official TWSE open-data API and supplement with a curated fallback of the
    largest-cap names so the screener always has something to work with even when
    the API is unreachable.
    """
    tickers: list[str] = []
    try:
        # TWSE open-data: listed companies
        resp = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            headers={"User-Agent": "FinancialAnalystBot/1.0"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            codes = [item.get("Code", "") for item in data if item.get("Code", "").isdigit()]
            tickers = [f"{c}.TW" for c in codes if c]
            logger.info("Fetched %d TWSE tickers from open-data API", len(tickers))
    except Exception as exc:
        logger.warning("TWSE open-data fetch failed (%s)", exc)

    if not tickers:
        tickers = _taiwan_fallback()

    # Also add major OTC names from fallback if not already present
    for t in _taiwan_otc_supplement():
        if t not in tickers:
            tickers.append(t)

    return tickers


def _taiwan_fallback() -> list[str]:
    """Top ~80 TWSE stocks by market cap (yfinance .TW suffix)."""
    return [
        # Semiconductors / tech
        "2330.TW",  # TSMC
        "2303.TW",  # UMC
        "2308.TW",  # Delta Electronics
        "2317.TW",  # Foxconn (Hon Hai)
        "2382.TW",  # Quanta Computer
        "2357.TW",  # Asustek
        "2354.TW",  # Foxconn Tech
        "2395.TW",  # Advantech
        "2379.TW",  # Realtek
        "2408.TW",  # Nanya Tech
        "2412.TW",  # Chunghwa Telecom
        "2454.TW",  # MediaTek
        "2474.TW",  # Catcher Technology
        "2481.TW",  # Rdc Semiconductor
        "2498.TW",  # HTC
        "3008.TW",  # Largan Precision
        "3034.TW",  # Novatek Microelectronics
        "3045.TW",  # Taiwan Mobile
        "3481.TW",  # Innolux
        "3711.TW",  # ASE Technology
        "4904.TW",  # Far EasTone
        "5880.TW",  # Taiwan Cooperative Financial
        "6505.TW",  # Formosa Petrochemical
        "6669.TW",  # Wiwynn
        "8046.TW",  # Nan Ya PCB
        # Financials
        "2882.TW",  # Cathay Financial
        "2881.TW",  # Fubon Financial
        "2886.TW",  # Mega Financial
        "2884.TW",  # E.Sun Financial
        "2885.TW",  # Yuanta Financial
        "2887.TW",  # Taishin Financial
        "2888.TW",  # Shin Kong Financial
        "2890.TW",  # SinoPac Financial
        "2891.TW",  # CTBC Financial
        "2892.TW",  # First Financial
        "2801.TW",  # Chang Hwa Bank
        "2823.TW",  # China Life Insurance
        # Petrochemicals / materials
        "1301.TW",  # Formosa Plastics
        "1303.TW",  # Nan Ya Plastics
        "1326.TW",  # Formosa Chemicals
        "6415.TW",  # Silergy
        # Electronics / display
        "2002.TW",  # China Steel
        "2207.TW",  # Hotai Motor
        "2301.TW",  # Lite-On Technology
        "2324.TW",  # Compal Electronics
        "2325.TW",  # Siliconware Precision
        "2344.TW",  # Winbond Electronics
        "2347.TW",  # Synnex Technology
        "2353.TW",  # Acer
        "2356.TW",  # Inventec
        "2376.TW",  # Gigabyte Technology
        "2377.TW",  # Micro-Star International (MSI)
        "2385.TW",  # Chilisin Electronics
        "2388.TW",  # VIA Technologies
        "2392.TW",  # Cheng Uei Precision
        "2409.TW",  # AU Optronics
        "2449.TW",  # King Yuan Electronics
        "2451.TW",  # Transcend Information
        "2458.TW",  # Yi Chin Industrial
        "2492.TW",  # Huawei Technologies TW (Walsin Lihwa)
        "2610.TW",  # China Airlines
        "2618.TW",  # EVA Airways
        "2633.TW",  # Taiwan High Speed Rail
        "2801.TW",  # Chang Hwa Bank
        "3006.TW",  # Silitech Technology
        "3017.TW",  # Advantest TW
        "3037.TW",  # Unimicron Technology
        "3044.TW",  # Health & Happiness
        "3231.TW",  # Wistron
        "3532.TW",  # Taiwan Semiconductor Packaging
        "4938.TW",  # Pegatron
        "5871.TW",  # Chailease Financial
        "6176.TW",  # Radiant Opto-Electronics
        "6239.TW",  # Powertech Technology
        "6770.TW",  # Ennoconn
        "9910.TW",  # Feng Tay Enterprises
    ]


def _taiwan_otc_supplement() -> list[str]:
    """Key Taiwan OTC (TWO) stocks to supplement the TWSE list."""
    return [
        "3673.TWO",  # TPK Holding
        "6488.TWO",  # Global Unichip
        "6533.TWO",  # Aspeed Technology
        "6547.TWO",  # Makalot Industrial
        "3529.TWO",  # Micro Base Technology
        "5274.TWO",  # Asia Pacific Telecom
    ]


# ── Screener ──────────────────────────────────────────────────────────────────

# Country → exchange suffixes yfinance uses
COUNTRY_SUFFIX_MAP: dict[str, list[str]] = {
    "United States": [""],           # no suffix
    "United Kingdom": [".L"],
    "Canada": [".TO", ".V"],
    "Australia": [".AX"],
    "Germany": [".DE", ".F"],
    "France": [".PA"],
    "Japan": [".T"],
    "Hong Kong": [".HK"],
    "China": [".SS", ".SZ"],
    "India": [".NS", ".BO"],
    "Switzerland": [".SW"],
    "Netherlands": [".AS"],
    "Sweden": [".ST"],
    "South Korea": [".KS"],
    "Taiwan": [".TW", ".TWO"],
    "Brazil": [".SA"],
}

# Region → country groupings
REGION_COUNTRY_MAP: dict[str, list[str]] = {
    "North America": ["United States", "Canada"],
    "Europe": ["United Kingdom", "Germany", "France", "Switzerland", "Netherlands", "Sweden"],
    "Asia Pacific": ["Japan", "Hong Kong", "China", "India", "South Korea", "Taiwan", "Australia"],
    "Latin America": ["Brazil"],
    "Global": list(COUNTRY_SUFFIX_MAP.keys()),
}

ALL_SECTORS = [
    "Technology", "Healthcare", "Financials", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Utilities", "Real Estate",
    "Industrials", "Basic Materials", "Communication Services",
]


def screen_universe(
    tickers: list[str],
    top_n: int = 10,
    min_market_cap_b: float = 2.0,
    sectors: list[str] | None = None,
    countries: list[str] | None = None,
    max_workers: int = 20,
    emit=None,
) -> list[dict[str, Any]]:
    """Score every ticker and return the top_n most undervalued.

    Args:
        tickers: Full list of tickers to screen.
        top_n: How many to return after filtering and scoring.
        min_market_cap_b: Minimum market cap in billions.
        sectors: If set, only include stocks in these sectors.
        countries: If set, only include stocks in these countries.
        max_workers: Parallel fetch threads.
        emit: Optional event callback.

    Returns:
        List of scored ticker dicts sorted by score descending.
    """
    total = len(tickers)
    logger.info("Screening %d tickers (top_n=%d, sectors=%s, countries=%s)",
                total, top_n, sectors, countries)

    if emit:
        emit("screener_start", {"total": total, "top_n": top_n},
             message=f"Screening {total} tickers…")

    results: list[dict[str, Any]] = []
    completed = 0

    def fetch_one(ticker: str) -> dict[str, Any] | None:
        try:
            info = yf.Ticker(ticker).info
            return {"ticker": ticker, "info": info}
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0 and emit:
                pct = round(completed / total * 100)
                emit("screener_progress", {
                    "completed": completed, "total": total, "pct": pct,
                }, message=f"Screened {completed}/{total} tickers ({pct}%)…")
            data = future.result()
            if data:
                scored = _score_ticker(
                    data["ticker"], data["info"], min_market_cap_b,
                    sectors=sectors, countries=countries,
                )
                if scored:
                    results.append(scored)

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:top_n]

    if emit:
        emit("screener_complete", {
            "screened": len(results),
            "top_n": top_n,
            "top_tickers": [r["ticker"] for r in top],
        }, message=f"Screen complete — top {top_n}: {', '.join(r['ticker'] for r in top)}")

    logger.info("Screen complete. Top %d: %s", top_n, [r["ticker"] for r in top])
    return top


def _score_ticker(
    ticker: str,
    info: dict[str, Any],
    min_market_cap_b: float,
    sectors: list[str] | None = None,
    countries: list[str] | None = None,
) -> dict[str, Any] | None:
    """Score a single ticker. Returns None if filtered out."""
    # ── Hard filters ─────────────────────────────────────────────────────
    market_cap = info.get("marketCap") or 0
    if market_cap < min_market_cap_b * 1e9:
        return None

    trailing_eps = info.get("trailingEps") or 0
    if trailing_eps <= 0:
        return None

    revenue = info.get("totalRevenue") or 0
    if revenue <= 0:
        return None

    pe = info.get("trailingPE") or 0
    if pe <= 0 or pe > 150:
        return None

    # ── Sector filter ─────────────────────────────────────────────────────
    ticker_sector = info.get("sector") or "Unknown"
    if sectors and ticker_sector not in sectors:
        return None

    # ── Country filter ────────────────────────────────────────────────────
    ticker_country = info.get("country") or ""
    if countries and ticker_country not in countries:
        return None

    # ── Sector benchmarks ─────────────────────────────────────────────────
    sector = ticker_sector
    pe_median = SECTOR_PE_MEDIANS.get(sector, 20.0)
    eveb_median = SECTOR_EVEB_MEDIANS.get(sector, 14.0)

    score = 0.0

    # P/E discount (0–25 pts)
    pe_discount = (pe_median - pe) / pe_median  # positive = cheaper than median
    score += max(0.0, min(25.0, pe_discount * 50))

    # EV/EBITDA (0–20 pts)
    ebitda = info.get("ebitda") or 0
    total_debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    if ebitda > 0:
        ev = market_cap + total_debt - cash
        eveb = ev / ebitda
        eveb_discount = (eveb_median - eveb) / eveb_median
        score += max(0.0, min(20.0, eveb_discount * 40))

    # P/B ratio (0–15 pts)
    pb = info.get("priceToBook") or 0
    if 0 < pb < 10:
        score += max(0.0, min(15.0, (5 - pb) / 5 * 15))

    # FCF yield (0–15 pts)
    fcf = info.get("freeCashflow") or 0
    if fcf > 0 and market_cap > 0:
        fcf_yield = fcf / market_cap
        score += min(15.0, fcf_yield * 150)

    # Revenue growth (0–10 pts)
    rev_growth = info.get("revenueGrowth") or 0
    if rev_growth > 0:
        score += min(10.0, rev_growth * 40)

    # Gross margin quality (0–10 pts)
    gross_margin = info.get("grossMargins") or 0
    score += min(10.0, gross_margin * 20)

    # Balance sheet health (0–5 pts)
    current_ratio = info.get("currentRatio") or 0
    if current_ratio >= 1.0:
        score += min(5.0, (current_ratio - 1) * 5)

    return {
        "ticker": ticker,
        "score": round(score, 2),
        "company_name": info.get("longName") or info.get("shortName") or ticker,
        "sector": sector,
        "country": ticker_country,
        "exchange": info.get("exchange") or "",
        "currency": info.get("currency") or "USD",
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap_b": round(market_cap / 1e9, 2),
        "pe_ratio": round(pe, 2),
        "pb_ratio": round(info.get("priceToBook") or 0, 2),
        "ev_ebitda": round((market_cap + total_debt - cash) / ebitda, 2) if ebitda > 0 else None,
        "fcf_yield_pct": round(fcf / market_cap * 100, 2) if fcf > 0 and market_cap > 0 else None,
        "revenue_growth_pct": round(rev_growth * 100, 2) if rev_growth else None,
        "sector_pe_median": pe_median,
        "pe_discount_pct": round((pe_median - pe) / pe_median * 100, 1),
    }


# ── Fallback lists ─────────────────────────────────────────────────────────────
# Used if Wikipedia is unreachable. Representative cross-sector sample.

def _sp500_fallback() -> list[str]:
    return [
        "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","JPM","UNH",
        "XOM","JNJ","V","PG","MA","HD","CVX","MRK","ABBV","PEP","KO","AVGO",
        "LLY","COST","TMO","MCD","ACN","BAC","CSCO","PFE","DIS","WMT","ADBE",
        "CRM","NFLX","CMCSA","AMD","INTC","VZ","PM","T","RTX","NEE","HON","UPS",
        "LOW","QCOM","IBM","GE","CAT","BA","MMM","GS","MS","BLK","SPGI","AXP",
        "AMGN","GILD","BMY","C","WFC","USB","PNC","TFC","COF","AIG","MET","PRU",
        "CI","HUM","CVS","MCK","ABC","CAH","EMR","ETN","PH","DOV","ROK","AME",
        "XOM","OXY","MPC","PSX","VLO","HAL","SLB","BKR","EOG","PXD","COP","DVN",
        "DUK","SO","AEP","EXC","SRE","PCG","ED","FE","ETR","ES","NI","WEC",
        "AMT","PLD","SPG","EQIX","PSA","DLR","O","WELL","AVB","EQR","ESS","UDR",
        "NEM","FCX","DOW","LIN","APD","ECL","PPG","SHW","VMC","MLM","NUE","STLD",
    ]


def _nasdaq100_fallback() -> list[str]:
    return [
        "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","AVGO","COST","ASML",
        "NFLX","AMD","PEP","ADBE","CSCO","INTC","QCOM","TXN","AMAT","INTU",
        "AMGN","ISRG","HON","VRTX","BKNG","REGN","ADP","GILD","MDLZ","ADI",
        "LRCX","MU","KLAC","PANW","SNPS","CDNS","MELI","NXPI","FTNT","CRWD",
        "IDXX","WDAY","KDP","MAR","ABNB","CEG","EXC","AEP","XEL","DXCM",
    ]
