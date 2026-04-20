"""OrchestratorAgent — coordinates the full analysis pipeline."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import yaml

from agents.base_agent import BaseAgent
from config.settings import get_settings

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
    """Coordinates all specialist agents and assembles the final report.

    Pipeline stages:
        1.  DataCollector           — prices, financials, SEC filings, macro
        2.  FundamentalAnalyst      — DCF, P/E, EV/EBITDA, target price, buy-below
        3.  GrowthAnalyst           — revenue/EPS/FCF CAGR, PEG, growth quality
        4.  PeerComparison          — sector median multiples, peer discount/premium
        5.  TechnicalAnalyst        — RSI, MA50/200, 52-week position, volume trend
        6.  SentimentAnalyst        — news sentiment, analyst ratings, insider activity
        7.  LayerClassifier         — assigns ticker to AI value chain (L1–L7 / NEUTRAL)
        8.  ValueCreationAnalyst    — real economic value created (now + 3–5y)
        9.  ValueCaptureAnalyst     — how much flows to the P&L (pricing power, leakage)
        10. PricingGapAnalyst       — market-implied vs AI-scenario — core mispricing signal
        11. AIRiskAnalyst           — AI-specific structural risks (commoditization, …)
        12. Synthesis (in-process)  — composite conviction_score + re-rank
        13. ReportWriter            — markdown report with all agent outputs
    """

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        t0 = self._log_run_start()
        settings = get_settings()
        cfg = _load_agents_config()
        cb = self._event_callback  # propagate to all sub-agents

        from agents.ai_risk_analyst import AIRiskAnalystAgent
        from agents.data_collector import DataCollectorAgent
        from agents.fundamental_analyst import FundamentalAnalystAgent
        from agents.growth_analyst import GrowthAnalystAgent
        from agents.layer_classifier import LayerClassifierAgent
        from agents.peer_comparison import PeerComparisonAgent
        from agents.pricing_gap_analyst import PricingGapAnalystAgent
        from agents.report_writer import ReportWriterAgent
        from agents.sentiment_analyst import SentimentAnalystAgent
        from agents.synthesis import synthesize_all
        from agents.technical_analyst import TechnicalAnalystAgent
        from agents.value_capture_analyst import ValueCaptureAnalystAgent
        from agents.value_creation_analyst import ValueCreationAnalystAgent

        data_collector         = DataCollectorAgent(cfg["data_collector"], settings, event_callback=cb)
        fundamental_analyst    = FundamentalAnalystAgent(cfg["fundamental_analyst"], settings, event_callback=cb)
        growth_analyst         = GrowthAnalystAgent(cfg["growth_analyst"], settings, event_callback=cb)
        peer_comparison        = PeerComparisonAgent(cfg["peer_comparison"], settings, event_callback=cb)
        technical_analyst      = TechnicalAnalystAgent(cfg["technical_analyst"], settings, event_callback=cb)
        sentiment_analyst      = SentimentAnalystAgent(cfg["sentiment_analyst"], settings, event_callback=cb)
        layer_classifier       = LayerClassifierAgent(cfg["layer_classifier"], settings, event_callback=cb)
        value_creation_analyst = ValueCreationAnalystAgent(cfg["value_creation_analyst"], settings, event_callback=cb)
        value_capture_analyst  = ValueCaptureAnalystAgent(cfg["value_capture_analyst"], settings, event_callback=cb)
        pricing_gap_analyst    = PricingGapAnalystAgent(cfg["pricing_gap_analyst"], settings, event_callback=cb)
        ai_risk_analyst        = AIRiskAnalystAgent(cfg["ai_risk_analyst"], settings, event_callback=cb)
        report_writer          = ReportWriterAgent(cfg["report_writer"], settings, event_callback=cb)

        tickers: list[str] = context["tickers"]
        tickers_failed: list[str] = []

        _TOTAL_STAGES = 13

        def _stage(n: int, name: str) -> None:
            self._emit("pipeline_stage", {"stage": n, "name": name, "total_stages": _TOTAL_STAGES})
            logger.info("[Orchestrator] Stage %d — %s", n, name)

        # ── Stage 1: Data Collection ──────────────────────────────────────────
        _stage(1, "Data Collection")
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

        # ── Stages 2–6: Classic pipeline ──────────────────────────────────────
        _classic_stages = [
            (2, "Fundamental Analysis", fundamental_analyst, "fundamental_analysis"),
            (3, "Growth Analysis",      growth_analyst,      "growth_analysis"),
            (4, "Peer Comparison",      peer_comparison,     "peer_comparison"),
            (5, "Technical Analysis",   technical_analyst,   "technical_analysis"),
            (6, "Sentiment Analysis",   sentiment_analyst,   "sentiment_analysis"),
        ]
        for stage_n, stage_name, agent, ctx_key in _classic_stages:
            _stage(stage_n, stage_name)
            try:
                context = agent.run(context)
            except Exception as exc:
                logger.error("%s failed: %s", stage_name, exc)
                context.setdefault(ctx_key, {})

        # ── Stages 7–11: AI value chain ───────────────────────────────────────
        # Stage 7 (Layer Classifier) runs first. Stages 8–11 each short-circuit
        # internally for tickers with NEUTRAL / MINIMAL AI exposure — no API cost
        # is paid on non-AI names.
        _ai_stages = [
            (7,  "AI Layer Classification",  layer_classifier,       "layer_classification"),
            (8,  "Value Creation Analysis",  value_creation_analyst, "value_creation"),
            (9,  "Value Capture Analysis",   value_capture_analyst,  "value_capture"),
            (10, "AI Pricing Gap Analysis",  pricing_gap_analyst,    "pricing_gap"),
            (11, "AI Risk Analysis",         ai_risk_analyst,        "ai_risk"),
        ]
        for stage_n, stage_name, agent, ctx_key in _ai_stages:
            _stage(stage_n, stage_name)
            try:
                context = agent.run(context)
            except Exception as exc:
                logger.error("%s failed: %s", stage_name, exc)
                context.setdefault(ctx_key, {})

        # ── Stage 12: Deterministic synthesis + re-rank ───────────────────────
        _stage(12, "Conviction Synthesis")
        try:
            synthesis = synthesize_all(context)
            context["synthesis"] = synthesis
            # Emit per-ticker conviction events so the frontend can surface them live
            for ticker, block in synthesis["per_ticker"].items():
                score = block.get("conviction_score")
                score_fmt = f"{score:+.1f}" if isinstance(score, (int, float)) else "?"
                self._emit(
                    "agent_ticker_complete",
                    {
                        "conviction_score": score,
                        "recommendation": block.get("recommendation"),
                        "thesis": block.get("thesis"),
                        "components": block.get("components"),
                        "adjustments": block.get("adjustments"),
                    },
                    ticker=ticker,
                    message=f"{ticker}: {block.get('recommendation')} ({score_fmt})",
                )
            first_block = synthesis["per_ticker"].get(tickers_ok[0], {}) if tickers_ok else {}
            self._emit(
                "ranking_ready",
                {
                    "ranking": synthesis["ranking"],
                    "weights": first_block.get("weights"),
                },
                message=f"Ranked {len(synthesis['ranking'])} tickers by AI-aware conviction",
            )
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            context.setdefault("synthesis", {"per_ticker": {}, "ranking": []})

        # ── Stage 13: Report Writing ──────────────────────────────────────────
        _stage(13, "Report Writing")
        try:
            context = report_writer.run(context)
        except Exception as exc:
            logger.error("Report writing failed: %s", exc)
            context.setdefault("report_path", "")
            context.setdefault("summary", f"Report generation failed: {exc}")

        # Propagate re-ranked order if Mode 2 wants it
        ranking = context.get("synthesis", {}).get("ranking", [])
        if ranking:
            context["tickers_ranked"] = [r["ticker"] for r in ranking]

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
