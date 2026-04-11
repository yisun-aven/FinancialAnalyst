"""Dev tool: run a single agent in isolation for testing/debugging.

Usage:
    python scripts/run_agent.py --agent data_collector --ticker AAPL
    python scripts/run_agent.py --agent fundamental_analyst --ticker MSFT
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.logging import RichHandler

from config.settings import get_settings

console = Console()

AGENT_MAP = {
    "data_collector": "agents.data_collector.DataCollectorAgent",
    "fundamental_analyst": "agents.fundamental_analyst.FundamentalAnalystAgent",
    "sentiment_analyst": "agents.sentiment_analyst.SentimentAnalystAgent",
    "report_writer": "agents.report_writer.ReportWriterAgent",
    "orchestrator": "agents.orchestrator.OrchestratorAgent",
}


def _import_agent_class(dotted_path: str):  # type: ignore[return]
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single agent for dev/testing.")
    parser.add_argument("--agent", required=True, choices=list(AGENT_MAP.keys()))
    parser.add_argument("--ticker", required=True, help="Ticker symbol to analyse")
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    with open("config/agents.yaml") as f:
        agents_yaml = yaml.safe_load(f)
    agent_config = agents_yaml["agents"][args.agent]

    AgentClass = _import_agent_class(AGENT_MAP[args.agent])
    agent = AgentClass(config=agent_config, settings=settings)

    context: dict = {
        "tickers": [args.ticker],
        "run_date": "2026-04-04",
    }

    console.print(f"[bold]Running[/] [cyan]{args.agent}[/] for [yellow]{args.ticker}[/]…")
    result = agent.run(context)
    console.print_json(data=result)


if __name__ == "__main__":
    main()
