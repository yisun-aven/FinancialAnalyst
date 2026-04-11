"""Entry point: runs the full analyst pipeline for today.

Usage:
    python scripts/run_daily.py
    python scripts/run_daily.py --date 2026-04-01   # backfill a specific date
    python scripts/run_daily.py --tickers AAPL MSFT  # override watchlist
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.logging import RichHandler

from config.settings import get_settings

console = Console()


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def _load_watchlist(watchlist_path: Path) -> list[str]:
    import yaml
    with watchlist_path.open() as f:
        data = yaml.safe_load(f)
    return [entry["ticker"] for entry in data.get("watchlist", [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the daily financial analysis pipeline.")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument("--tickers", nargs="+", help="Override watchlist with specific tickers")
    args = parser.parse_args()

    settings = get_settings()
    _configure_logging(settings.log_level)
    log = logging.getLogger(__name__)

    tickers = args.tickers if args.tickers else _load_watchlist(settings.watchlist_path)
    log.info("Tickers: %s | Date: %s", tickers, args.date)

    # Load orchestrator config and run
    import yaml
    from agents.orchestrator import OrchestratorAgent, _load_agents_config

    agents_config = _load_agents_config()
    orchestrator = OrchestratorAgent(agents_config["orchestrator"], settings)

    context: dict = {"tickers": tickers, "run_date": args.date}

    console.print(f"\n[bold cyan]Financial Analyst[/] starting — {len(tickers)} tickers, date {args.date}\n")

    result = orchestrator.run(context)

    # ── Print results ──────────────────────────────────────────────────────
    report_path = result.get("report_path", "")
    succeeded = result.get("tickers_succeeded", [])
    failed = result.get("tickers_failed", [])
    summary = result.get("summary", "")

    console.print(f"\n[bold green]Pipeline complete![/]")
    console.print(f"  Succeeded : {succeeded}")
    if failed:
        console.print(f"  [yellow]Failed    : {failed}[/]")
    if report_path:
        console.print(f"  Report    : [link={report_path}]{report_path}[/link]")
    if summary:
        console.print(f"\n[bold]Summary[/]\n{summary}")


if __name__ == "__main__":
    main()
