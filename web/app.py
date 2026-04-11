"""FastAPI web interface for the Financial Analyst pipeline."""

from __future__ import annotations

import asyncio
import re
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Financial Analyst AI")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/reports")
async def list_reports() -> JSONResponse:
    from config.settings import get_settings
    out = get_settings().report_output_dir
    import re as _re
    reports = sorted(
        [
            {
                "filename": f.name,
                # stem is like "2026-04-05_14-32-01_analyst_report"
                # extract just date + time for display
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


@app.get("/api/reports/{filename}")
async def get_report(filename: str) -> JSONResponse:
    if not re.match(r"^[\w\-\.]+\.md$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    from config.settings import get_settings
    path = get_settings().report_output_dir / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"filename": filename, "content": path.read_text(encoding="utf-8")})


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

    def run_sync() -> None:
        result: dict = {}
        try:
            from agents.orchestrator import OrchestratorAgent, _load_agents_config
            from config.settings import get_settings
            settings = get_settings()
            cfg = _load_agents_config()
            orch = OrchestratorAgent(cfg["orchestrator"], settings, event_callback=emit)
            result = orch.run({"tickers": tickers, "run_date": run_date})
        except Exception as exc:
            emit({"type": "pipeline_error", "agent": "orchestrator",
                  "data": {"error": str(exc)}, "timestamp": _now()})
        finally:
            emit({
                "type": "pipeline_complete",
                "agent": "orchestrator",
                "data": {
                    "report_path": result.get("report_path", ""),
                    "report_filename": Path(result.get("report_path", "x")).name,
                    "tickers_succeeded": result.get("tickers_succeeded", []),
                    "tickers_failed": result.get("tickers_failed", []),
                    "summary": result.get("summary", ""),
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

            def agent_emit(event: dict) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, event)

            cfg = _load_agents_config()
            orch = OrchestratorAgent(cfg["orchestrator"], settings, event_callback=agent_emit)
            result = orch.run({"tickers": top_tickers, "run_date": run_date})

            loop.call_soon_threadsafe(queue.put_nowait, {
                "type": "pipeline_complete",
                "agent": "orchestrator",
                "data": {
                    "report_path": result.get("report_path", ""),
                    "report_filename": Path(result.get("report_path", "x")).name,
                    "tickers_succeeded": result.get("tickers_succeeded", []),
                    "tickers_failed": result.get("tickers_failed", []),
                    "summary": result.get("summary", ""),
                    "screen_results": top_stocks,
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
