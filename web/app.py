"""FastAPI web interface for the Financial Analyst pipeline."""

from __future__ import annotations

import asyncio
import json
import re
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Financial Analyst AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"

# ── Output directory helpers ───────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
print(f"[app] PROJECT_ROOT = {_PROJECT_ROOT}", flush=True)

def _reports_dir() -> Path:
    from config.settings import get_settings
    d = get_settings().report_output_dir   # outputs/reports
    if not d.is_absolute():
        d = _PROJECT_ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d

def _results_dir() -> Path:
    from config.settings import get_settings
    d = get_settings().results_output_dir  # outputs/results
    if not d.is_absolute():
        d = _PROJECT_ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_results(
    run_ts: str,
    tickers_succeeded: list[str],
    tickers_failed: list[str],
    all_results: dict,
    report_filename: str,
    summary: str,
    screen_results: list | None = None,
    ranking: list | None = None,
) -> str:
    """Persist agent outputs to a JSON file alongside the markdown report.

    Returns the filename of the saved results file.
    Filename format: 2026-04-11_17-34-22_TSM-AAPL-MSFT_results.json
    """
    ticker_slug = "-".join(t.replace(".", "") for t in tickers_succeeded[:4])
    if len(tickers_succeeded) > 4:
        ticker_slug += f"+{len(tickers_succeeded) - 4}more"
    filename = f"{run_ts}_{ticker_slug}_results.json" if ticker_slug else f"{run_ts}_results.json"
    payload = {
        "run_ts": run_ts,
        "tickers_succeeded": tickers_succeeded,
        "tickers_failed": tickers_failed,
        "all_results": all_results,
        "report_filename": report_filename,
        "summary": summary,
        "screen_results": screen_results or [],
        "ranking": ranking or [],
    }
    path = _results_dir() / filename
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return filename


# ── REST endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/runs")
async def list_runs() -> JSONResponse:
    """List all saved result runs, newest first.

    Each entry has: filename, run_ts, tickers, report_filename, size_kb.
    """
    out = _results_dir()
    runs = []
    for f in out.glob("*_results.json"):
        if not f.is_file():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # run_ts is stored inside the JSON; fall back to parsing the filename
            run_ts = data.get("run_ts") or f.stem[:16]  # "2026-04-11_17-34"
            runs.append({
                "filename": f.name,
                "run_ts": run_ts,
                "tickers": data.get("tickers_succeeded", []),
                "report_filename": data.get("report_filename", ""),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
        except Exception:
            continue
    runs.sort(key=lambda r: r["run_ts"], reverse=True)
    return JSONResponse(runs)


@app.get("/api/runs/{filename:path}")
async def get_run(filename: str) -> JSONResponse:
    """Return the full results JSON for a saved run."""
    if not re.match(r"^[\w\-\.]+\.json$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    path = _results_dir() / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/reports")
async def list_reports() -> JSONResponse:
    out = _reports_dir()
    import re as _re
    reports = sorted(
        [
            {
                "filename": f.name,
                "date": _re.sub(r"_analyst_report$", "", f.stem).replace("_", " ", 1),
                "size_kb": round(f.stat().st_size / 1024, 1),
            }
            for f in out.glob("*_analyst_report.md")
            if f.is_file()
        ],
        key=lambda r: r["date"],
        reverse=True,
    )
    return JSONResponse(reports)


# NOTE: the `/pdf` route MUST be declared before the generic `{filename:path}`
# route, otherwise FastAPI would match the `:path` converter greedily and the
# PDF route would never be reached.
@app.get("/api/reports/{filename}/pdf")
async def download_report_pdf(filename: str):
    """Render the given markdown report as a PDF and stream it back."""
    if not re.match(r"^[\w\-\.]+$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    path = _reports_dir() / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)

    try:
        from tools.pdf_export import render_markdown_file_to_pdf
    except ImportError as exc:
        return JSONResponse(
            {"error": f"PDF export not available: {exc}. Run `pip install fpdf2 markdown`."},
            status_code=501,
        )

    # Use the markdown stem (without trailing _analyst_report) as the human title
    pretty_title = re.sub(r"_analyst_report$", "", path.stem).replace("_", " ")
    try:
        pdf_bytes = render_markdown_file_to_pdf(path, title=pretty_title)
    except Exception as exc:
        return JSONResponse({"error": f"PDF rendering failed: {exc}"}, status_code=500)

    pdf_filename = path.stem + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
    )


@app.get("/api/reports/{filename:path}")
async def get_report(filename: str) -> JSONResponse:
    if not re.match(r"^[\w\-\.]+$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    reports_dir = _reports_dir()
    path = reports_dir / filename
    import logging as _logging
    _logging.getLogger("uvicorn").info("get_report: dir=%s  file=%s  exists=%s", reports_dir, path, path.exists())
    if not path.exists():
        return JSONResponse({"error": "Not found", "path": str(path)}, status_code=404)
    return JSONResponse({"filename": filename, "content": path.read_text(encoding="utf-8")})



# ── User profile endpoints ─────────────────────────────────────────────────

_USER_FILE = _PROJECT_ROOT / "database" / "user_profile.json"


def _load_user() -> dict:
    if _USER_FILE.exists():
        return json.loads(_USER_FILE.read_text(encoding="utf-8"))
    return {}


def _save_user(data: dict) -> None:
    _USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USER_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


@app.get("/api/user")
async def get_user() -> JSONResponse:
    if not _USER_FILE.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(_load_user())


@app.put("/api/user")
async def put_user(request: Request) -> JSONResponse:
    body = await request.json()
    _save_user(body)
    return JSONResponse({"ok": True})


# ── Ticker search endpoint ─────────────────────────────────────────────────

# Maps region key → yfinance exchange suffix (empty string = US, no suffix needed)
_REGION_SUFFIX: dict[str, str] = {
    "US": "",
    "TW": ".TW",
    "TWO": ".TWO",   # Taiwan OTC
    "HK": ".HK",
    "JP": ".T",
    "KR": ".KS",
    "CN": ".SS",     # Shanghai
    "CNS": ".SZ",    # Shenzhen
    "UK": ".L",
    "DE": ".DE",
    "FR": ".PA",
    "AU": ".AX",
    "CA": ".TO",
    "IN": ".NS",     # NSE India
    "SG": ".SI",
}


@app.get("/api/search")
async def search_tickers(q: str = "", region: str = "US") -> JSONResponse:
    """Search for tickers by name/symbol within a region using yfinance."""
    q = q.strip()
    if not q or len(q) < 1:
        return JSONResponse([])

    import yfinance as yf

    region_up = region.upper()
    # "TW" covers both TWSE main board (.TW) and Taipei Exchange OTC (.TWO) so
    # users don't have to guess which market a Taiwan name trades on.
    if region_up == "TW":
        accepted_suffixes = (".TW", ".TWO")
    else:
        accepted_suffixes = (_REGION_SUFFIX.get(region_up, ""),)

    try:
        results = yf.Search(q, max_results=20).quotes
    except Exception:
        results = []

    out = []
    for r in results:
        sym: str = r.get("symbol", "")
        name: str = r.get("longname") or r.get("shortname") or ""
        exchange: str = r.get("exchange", "")
        q_type: str = r.get("quoteType", "")

        if region_up == "US":
            if "." in sym:
                continue
            if q_type in ("CRYPTOCURRENCY", "FUTURE", "INDEX"):
                continue
        else:
            # Non-US: require one of the region's accepted suffixes.
            if not any(sym.endswith(s) for s in accepted_suffixes if s):
                continue

        out.append({
            "symbol": sym,
            "name": name,
            "exchange": exchange,
            "type": q_type,
        })

    return JSONResponse(out[:15])


# ── FX rates endpoint ─────────────────────────────────────────────────────

@app.get("/api/fx")
async def get_fx_rates(currencies: str = "") -> JSONResponse:
    """Return USD conversion rates for a comma-separated list of ISO currency codes.

    Uses yfinance forex pairs (e.g. TWDUSD=X) to get the latest rate.
    Always returns rates as: 1 unit of <currency> = N USD.
    USD itself is always 1.0.
    """
    import yfinance as yf

    currency_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]
    # Always include USD
    if "USD" not in currency_list:
        currency_list.append("USD")

    rates: dict[str, float | None] = {"USD": 1.0}

    for ccy in currency_list:
        if ccy == "USD":
            continue
        # GBp (pence) is a special case — 100 pence = 1 GBP, and GBPUSD=X gives GBP/USD
        if ccy == "GBp":
            try:
                pair = "GBPUSD=X"
                info = yf.Ticker(pair).fast_info
                gbp_usd = getattr(info, "last_price", None)
                rates["GBp"] = round(float(gbp_usd) / 100, 8) if gbp_usd else None
            except Exception:
                rates["GBp"] = None
            continue
        try:
            pair = f"{ccy}USD=X"
            info = yf.Ticker(pair).fast_info
            rate = getattr(info, "last_price", None)
            rates[ccy] = round(float(rate), 8) if rate is not None else None
        except Exception:
            rates[ccy] = None

    return JSONResponse(rates)


# ── Live price endpoint ────────────────────────────────────────────────────

def _fetch_twse_quote(ticker: str) -> dict | None:
    """Fetch a near-live quote from TWSE MIS for a .TW / .TWO ticker.

    Returns a normalized dict (same shape as the yfinance branch) or None on
    any failure so the caller can fall back to yfinance.
    TWSE MIS is delayed by roughly 20 seconds and requires no API key.
    """
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        return None

    import requests

    symbol = ticker.split(".")[0]
    prefix = "tse" if ticker.endswith(".TW") else "otc"
    ex_ch = f"{prefix}_{symbol}.tw"
    url = (
        "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        f"?ex_ch={ex_ch}&json=1&delay=0"
    )
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    arr = data.get("msgArray") or []
    if not arr:
        return None
    q = arr[0]

    def _f(key: str) -> float | None:
        v = q.get(key)
        if v in (None, "", "-"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    price = _f("z")  # latest match price ("-" pre-open / halted)
    if price is None:
        # Pre-open: use mid of best bid/ask if available
        bid_str = (q.get("b") or "").split("_")[0]
        ask_str = (q.get("a") or "").split("_")[0]
        try:
            bid = float(bid_str) if bid_str not in ("", "-") else None
            ask = float(ask_str) if ask_str not in ("", "-") else None
        except ValueError:
            bid = ask = None
        if bid and ask:
            price = (bid + ask) / 2

    prev_close = _f("y")
    if price is None or prev_close is None or prev_close == 0:
        return None

    change = round(price - prev_close, 4)
    change_pct = round((change / prev_close) * 100, 2)
    return {
        "ticker": ticker,
        "price": round(price, 4),
        "change": change,
        "changePct": change_pct,
        "currency": "TWD",
        "source": "twse",
    }


@app.get("/api/prices")
async def get_prices(tickers: str = "") -> JSONResponse:
    """Fetch current price + day change for a comma-separated list of tickers.

    Routing:
      * `.TW` / `.TWO`  → TWSE MIS (near-live, ~20s delay), falls back to yfinance
      * everything else → yfinance (~15 min delay)
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return JSONResponse([], headers={"Cache-Control": "no-store"})

    import yfinance as yf

    results = []
    for ticker in ticker_list:
        # 1) Try TWSE MIS for Taiwan-listed tickers
        if ticker.endswith(".TW") or ticker.endswith(".TWO"):
            twse_quote = await asyncio.to_thread(_fetch_twse_quote, ticker)
            if twse_quote is not None:
                results.append(twse_quote)
                continue

        # 2) Fallback: yfinance (also the default path for non-TW tickers)
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)
            currency = getattr(info, "currency", None) or (t.info or {}).get("currency", "USD")
            if price is not None and prev_close is not None and prev_close != 0:
                change = round(price - prev_close, 4)
                change_pct = round((change / prev_close) * 100, 2)
            else:
                change = None
                change_pct = None
            results.append({
                "ticker": ticker,
                "price": round(price, 4) if price is not None else None,
                "change": change,
                "changePct": change_pct,
                "currency": currency,
                "source": "yfinance",
            })
        except Exception as exc:
            results.append({
                "ticker": ticker,
                "price": None,
                "change": None,
                "changePct": None,
                "currency": "USD",
                "source": "error",
                "error": str(exc),
            })

    return JSONResponse(results, headers={"Cache-Control": "no-store"})


@app.websocket("/ws/run")
async def run_pipeline_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        params = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
    except Exception:
        await websocket.close(code=1008)
        return

    tickers: list[str] = [t.strip().upper() for t in params.get("tickers", []) if t.strip()]
    run_date: str = params.get("run_date", date.today().isoformat())

    if not tickers:
        await websocket.send_json({"type": "pipeline_error", "data": {"error": "No tickers provided"}})
        return

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    def emit(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # Collect per-ticker agent outputs server-side for persistence
    _agent_outputs: dict[str, dict] = {}
    _orig_emit = emit

    def emit_and_collect(event: dict) -> None:
        _orig_emit(event)
        if event.get("type") == "agent_ticker_complete" and event.get("ticker"):
            ticker = event["ticker"]
            agent  = event.get("agent", "")
            data   = event.get("data", {})
            if ticker not in _agent_outputs:
                _agent_outputs[ticker] = {}
            KEY_MAP = {
                "fundamental_analyst":    "fundamental",
                "growth_analyst":         "growth",
                "peer_comparison":        "peers",
                "technical_analyst":      "technical",
                "sentiment_analyst":      "sentiment",
                "data_collector":         "raw",
                "layer_classifier":       "layer",
                "value_creation_analyst": "value_creation",
                "value_capture_analyst":  "value_capture",
                "pricing_gap_analyst":    "pricing_gap",
                "ai_risk_analyst":        "ai_risk",
                "orchestrator":           "synthesis",
            }
            if agent in KEY_MAP:
                _agent_outputs[ticker][KEY_MAP[agent]] = data

    def run_sync() -> None:
        result: dict = {}
        run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        try:
            from agents.orchestrator import OrchestratorAgent, _load_agents_config
            from config.settings import get_settings
            settings = get_settings()
            cfg = _load_agents_config()
            orch = OrchestratorAgent(cfg["orchestrator"], settings, event_callback=emit_and_collect)
            result = orch.run({"tickers": tickers, "run_date": run_date})
        except Exception as exc:
            emit({"type": "pipeline_error", "agent": "orchestrator",
                  "data": {"error": str(exc)}, "timestamp": _now()})
        finally:
            report_filename = Path(result.get("report_path", "x")).name
            results_filename = ""
            try:
                results_filename = _save_results(
                    run_ts=run_ts,
                    tickers_succeeded=result.get("tickers_succeeded", []),
                    tickers_failed=result.get("tickers_failed", []),
                    all_results=_agent_outputs,
                    report_filename=report_filename,
                    summary=result.get("summary", ""),
                    ranking=(result.get("synthesis") or {}).get("ranking"),
                )
            except Exception:
                pass
            synthesis = result.get("synthesis", {}) or {}
            emit({
                "type": "pipeline_complete",
                "agent": "orchestrator",
                "data": {
                    "report_path": result.get("report_path", ""),
                    "report_filename": report_filename,
                    "results_filename": results_filename,
                    "tickers_succeeded": result.get("tickers_succeeded", []),
                    "tickers_failed": result.get("tickers_failed", []),
                    "tickers_ranked": result.get("tickers_ranked", []),
                    "summary": result.get("summary", ""),
                    "ranking": synthesis.get("ranking", []),
                    "all_results": _agent_outputs,
                },
                "timestamp": _now(),
            })

    threading.Thread(target=run_sync, daemon=True).start()

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=600.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            try:
                await websocket.send_json(event)
            except Exception:
                break

            if event["type"] in ("pipeline_complete", "pipeline_error"):
                break
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/screen")
async def screen_and_run_ws(websocket: WebSocket) -> None:
    """Screen a universe for undervalued stocks, then run the full pipeline on top N."""
    await websocket.accept()

    try:
        params = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
    except Exception:
        await websocket.close(code=1008)
        return

    universe: str = params.get("universe", "sp500")
    top_n: int = min(int(params.get("top_n", 5)), 20)
    min_cap: float = float(params.get("min_market_cap_b", 2.0))
    run_date: str = params.get("run_date", date.today().isoformat())
    sectors: list[str] | None = params.get("sectors") or None       # None = all
    region: str = params.get("region", "")
    countries_raw: list[str] = params.get("countries") or []

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def emit(event_type: str, data: dict | None = None, ticker: str | None = None, message: str = "") -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {
            "type": event_type,
            "agent": "screener",
            "ticker": ticker,
            "message": message,
            "data": data or {},
            "timestamp": _now(),
        })

    # Collect per-ticker agent outputs server-side for persistence
    _agent_outputs_s: dict[str, dict] = {}

    def agent_emit_and_collect(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)
        if event.get("type") == "agent_ticker_complete" and event.get("ticker"):
            ticker = event["ticker"]
            agent  = event.get("agent", "")
            data   = event.get("data", {})
            if ticker not in _agent_outputs_s:
                _agent_outputs_s[ticker] = {}
            KEY_MAP = {
                "fundamental_analyst":    "fundamental",
                "growth_analyst":         "growth",
                "peer_comparison":        "peers",
                "technical_analyst":      "technical",
                "sentiment_analyst":      "sentiment",
                "data_collector":         "raw",
                "layer_classifier":       "layer",
                "value_creation_analyst": "value_creation",
                "value_capture_analyst":  "value_capture",
                "pricing_gap_analyst":    "pricing_gap",
                "ai_risk_analyst":        "ai_risk",
                "orchestrator":           "synthesis",
            }
            if agent in KEY_MAP:
                _agent_outputs_s[ticker][KEY_MAP[agent]] = data

    def run_sync() -> None:
        try:
            from tools.screener import (
                REGION_COUNTRY_MAP,
                get_nasdaq100_tickers,
                get_sp500_tickers,
                get_taiwan_tickers,
                screen_universe,
            )
            from config.settings import get_settings
            settings = get_settings()

            # Resolve country/region filter first so we can pick the right universe
            countries_filter: list[str] | None = None
            if countries_raw:
                countries_filter = countries_raw
            elif region and region != "Global":
                countries_filter = REGION_COUNTRY_MAP.get(region)

            # Step 1: get universe
            # When the user explicitly filters for Taiwan, automatically use the
            # full Taiwan stock universe instead of a US-only index so that actual
            # Taiwanese stocks are screened rather than just the handful that happen
            # to be cross-listed on US exchanges.
            is_taiwan_only = countries_filter == ["Taiwan"]

            if is_taiwan_only or universe == "taiwan":
                tickers_all = get_taiwan_tickers()
                universe_label = "Taiwan (TWSE + OTC)"
            elif universe == "sp500":
                tickers_all = get_sp500_tickers()
                universe_label = "S&P 500"
            elif universe == "nasdaq100":
                tickers_all = get_nasdaq100_tickers()
                universe_label = "Nasdaq 100"
            else:  # watchlist
                import yaml
                with open(settings.watchlist_path) as f:
                    tickers_all = [e["ticker"] for e in yaml.safe_load(f).get("watchlist", [])]
                universe_label = "watchlist"

            emit("universe_loaded", {"universe": universe, "count": len(tickers_all)},
                 message=f"Loaded {len(tickers_all)} tickers from {universe_label}")

            # Step 2: quantitative pre-screen
            top_stocks = screen_universe(
                tickers_all, top_n=top_n, min_market_cap_b=min_cap,
                sectors=sectors, countries=countries_filter, emit=emit,
            )

            if not top_stocks:
                hint = ""
                if countries_filter:
                    hint = (f" No stocks from {countries_filter} passed the screen. "
                            f"Try lowering the minimum market cap or removing sector filters.")
                elif sectors:
                    hint = f" No stocks in {sectors} passed the screen with current filters."
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "pipeline_error",
                    "agent": "screener",
                    "data": {"error": f"Screen returned 0 results.{hint}"},
                    "timestamp": _now(),
                })
                return
            top_tickers = [s["ticker"] for s in top_stocks]

            # Emit screen results table
            emit("screen_results", {"stocks": top_stocks, "top_tickers": top_tickers},
                 message=f"Top {len(top_tickers)}: {', '.join(top_tickers)}")

            # Step 3: full pipeline on top N
            from agents.orchestrator import OrchestratorAgent, _load_agents_config

            run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
            cfg = _load_agents_config()
            orch = OrchestratorAgent(cfg["orchestrator"], settings, event_callback=agent_emit_and_collect)
            result = orch.run({"tickers": top_tickers, "run_date": run_date})

            # ── Re-rank the screener table by the AI-aware conviction score ───────
            synthesis = result.get("synthesis", {}) or {}
            ranking = synthesis.get("ranking", []) or []
            if ranking:
                rank_map = {r["ticker"]: i for i, r in enumerate(ranking)}
                top_stocks_ranked = sorted(
                    top_stocks,
                    key=lambda s: rank_map.get(s.get("ticker"), 10**6),
                )
                # Enrich each screener row with the conviction fields
                per_ticker = synthesis.get("per_ticker", {}) or {}
                for row in top_stocks_ranked:
                    block = per_ticker.get(row.get("ticker"), {})
                    row["conviction_score"] = block.get("conviction_score")
                    row["recommendation"] = block.get("recommendation")
                    row["ai_gap_score"] = (block.get("components") or {}).get("gap_score")
                    row["primary_layer"] = (block.get("components") or {}).get("primary_layer")
                top_stocks_final = top_stocks_ranked
            else:
                top_stocks_final = top_stocks

            report_filename = Path(result.get("report_path", "x")).name
            results_filename = ""
            try:
                results_filename = _save_results(
                    run_ts=run_ts,
                    tickers_succeeded=result.get("tickers_succeeded", []),
                    tickers_failed=result.get("tickers_failed", []),
                    all_results=_agent_outputs_s,
                    report_filename=report_filename,
                    summary=result.get("summary", ""),
                    screen_results=top_stocks_final,
                    ranking=ranking,
                )
            except Exception:
                pass

            loop.call_soon_threadsafe(queue.put_nowait, {
                "type": "pipeline_complete",
                "agent": "orchestrator",
                "data": {
                    "report_path": result.get("report_path", ""),
                    "report_filename": report_filename,
                    "results_filename": results_filename,
                    "tickers_succeeded": result.get("tickers_succeeded", []),
                    "tickers_failed": result.get("tickers_failed", []),
                    "tickers_ranked": result.get("tickers_ranked", []),
                    "summary": result.get("summary", ""),
                    "screen_results": top_stocks_final,
                    "ranking": ranking,
                    "all_results": _agent_outputs_s,
                },
                "timestamp": _now(),
            })

        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {
                "type": "pipeline_error",
                "agent": "screener",
                "data": {"error": str(exc)},
                "timestamp": _now(),
            })

    threading.Thread(target=run_sync, daemon=True).start()

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=600.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue
            try:
                await websocket.send_json(event)
            except Exception:
                break
            if event["type"] in ("pipeline_complete", "pipeline_error"):
                break
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
