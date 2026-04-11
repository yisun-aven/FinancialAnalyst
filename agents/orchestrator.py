"""OrchestratorAgent — coordinates the full analysis pipeline."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import yaml

from agents.base_agent import BaseAgent
from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class OrchestratorInput(TypedDict):
    tickers: list[str]
    run_date: str


class OrchestratorOutput(TypedDict):
    report_path: str
    tickers_succeeded: list[str]
    tickers_failed: list[str]
    summary: str


class OrchestratorAgent(BaseAgent):
    """Coordinates all specialist agents and assembles the final report."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        t0 = self._log_run_start()
        settings = get_settings()
        cfg = _load_agents_config()
        cb = self._event_callback  # propagate to all sub-agents

        from agents.data_collector import DataCollectorAgent
        from agents.fundamental_analyst import FundamentalAnalystAgent
        from agents.report_writer import ReportWriterAgent
        from agents.sentiment_analyst import SentimentAnalystAgent

        data_collector      = DataCollectorAgent(cfg["data_collector"], settings, event_callback=cb)
        fundamental_analyst = FundamentalAnalystAgent(cfg["fundamental_analyst"], settings, event_callback=cb)
        sentiment_analyst   = SentimentAnalystAgent(cfg["sentiment_analyst"], settings, event_callback=cb)
        report_writer       = ReportWriterAgent(cfg["report_writer"], settings, event_callback=cb)

        tickers: list[str] = context["tickers"]
        tickers_failed: list[str] = []

        # ── Stage 1 ───────────────────────────────────────────────────────────
        self._emit("pipeline_stage", {"stage": 1, "name": "Data Collection"})
        logger.info("[Orchestrator] Stage 1 — Data collection")
        try:
            context = data_collector.run(context)
        except Exception as exc:
            logger.error("Data collection failed: %s", exc)
            context.setdefault("raw_data", {})
            context.setdefault("macro_data", {})

        raw_data: dict[str, Any] = context.get("raw_data", {})
        for ticker in tickers:
            td = raw_data.get(ticker, {})
            if all("error" in td.get(k, {}) for k in ("prices", "financials")):
                tickers_failed.append(ticker)
        tickers_ok = [t for t in tickers if t not in tickers_failed]
        context["tickers"] = tickers_ok

        # ── Stage 2 ───────────────────────────────────────────────────────────
        self._emit("pipeline_stage", {"stage": 2, "name": "Fundamental Analysis"})
        logger.info("[Orchestrator] Stage 2 — Fundamental analysis (%d tickers)", len(tickers_ok))
        try:
            context = fundamental_analyst.run(context)
        except Exception as exc:
            logger.error("Fundamental analysis failed: %s", exc)
            context.setdefault("fundamental_analysis", {})

        # ── Stage 3 ───────────────────────────────────────────────────────────
        self._emit("pipeline_stage", {"stage": 3, "name": "Sentiment Analysis"})
        logger.info("[Orchestrator] Stage 3 — Sentiment analysis")
        try:
            context = sentiment_analyst.run(context)
        except Exception as exc:
            logger.error("Sentiment analysis failed: %s", exc)
            context.setdefault("sentiment_analysis", {})

        # ── Stage 4 ───────────────────────────────────────────────────────────
        self._emit("pipeline_stage", {"stage": 4, "name": "Report Writing"})
        logger.info("[Orchestrator] Stage 4 — Writing report")
        try:
            context = report_writer.run(context)
        except Exception as exc:
            logger.error("Report writing failed: %s", exc)
            context.setdefault("report_path", "")
            context.setdefault("summary", f"Report generation failed: {exc}")

        context["tickers_succeeded"] = tickers_ok
        context["tickers_failed"] = tickers_failed
        context["tickers"] = tickers
        self._log_run_end(t0)
        return context


def _load_agents_config() -> dict[str, dict[str, Any]]:
    with open("config/agents.yaml") as f:
        data = yaml.safe_load(f)
    agents: dict[str, dict[str, Any]] = data.get("agents", {})
    settings = get_settings()
    for ac in agents.values():
        env_var = ac.get("model_env_var", "MODEL_ANALYST")
        ac["model"] = getattr(settings, env_var.lower(), settings.model_analyst)
    return agents
