"""ReportWriterAgent — generates the formatted daily analyst report."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReportWriterInput(TypedDict):
    tickers: list[str]
    run_date: str
    macro_data: dict[str, Any]
    fundamental_analysis: dict[str, Any]
    growth_analysis: dict[str, Any]
    peer_comparison: dict[str, Any]
    sentiment_analysis: dict[str, Any]
    layer_classification: dict[str, Any]
    value_creation: dict[str, Any]
    value_capture: dict[str, Any]
    pricing_gap: dict[str, Any]
    ai_risk: dict[str, Any]
    synthesis: dict[str, Any]


class ReportWriterOutput(TypedDict):
    report_markdown: str
    report_path: str
    summary: str


class ReportWriterAgent(BaseAgent):
    """Assembles all agent outputs into a formatted daily analyst report."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        t0 = self._log_run_start()
        tickers: list[str] = context["tickers"]
        run_date: str = context.get("run_date", datetime.today().strftime("%Y-%m-%d"))
        fundamental = context.get("fundamental_analysis", {})
        growth = context.get("growth_analysis", {})
        peers = context.get("peer_comparison", {})
        sentiment = context.get("sentiment_analysis", {})
        macro = context.get("macro_data", {})
        layer = context.get("layer_classification", {})
        creation = context.get("value_creation", {})
        capture = context.get("value_capture", {})
        pricing_gap = context.get("pricing_gap", {})
        ai_risk = context.get("ai_risk", {})
        synthesis = context.get("synthesis", {})

        prompt = self._build_prompt(
            tickers, run_date, fundamental, growth, peers, sentiment, macro,
            layer, creation, capture, pricing_gap, ai_risk, synthesis,
        )
        logger.info("[%s] Generating report for %d tickers", self.name, len(tickers))

        report_markdown = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        report_path = self._save_report(report_markdown, run_date, tickers)
        summary = self._extract_summary(report_markdown)

        self._emit("report_ready", {
            "report_path": str(report_path),
            "report_filename": report_path.name,
            "summary": summary,
        }, message=f"Report saved → {report_path.name}")

        context["report_markdown"] = report_markdown
        context["report_path"] = str(report_path)
        context["summary"] = summary
        self._log_run_end(t0)
        return context

    def _build_prompt(
        self,
        tickers: list[str],
        run_date: str,
        fundamental: dict[str, Any],
        growth: dict[str, Any],
        peers: dict[str, Any],
        sentiment: dict[str, Any],
        macro: dict[str, Any],
        layer: dict[str, Any],
        creation: dict[str, Any],
        capture: dict[str, Any],
        pricing_gap: dict[str, Any],
        ai_risk: dict[str, Any],
        synthesis: dict[str, Any],
    ) -> str:
        blocks = []
        synthesis_per_ticker = (synthesis or {}).get("per_ticker", {})
        for t in tickers:
            fa = fundamental.get(t, {})
            ga = growth.get(t, {})
            pa = peers.get(t, {})
            sa = sentiment.get(t, {})
            lc = layer.get(t, {})
            vcr = creation.get(t, {})
            vcp = capture.get(t, {})
            pg = pricing_gap.get(t, {})
            ar = ai_risk.get(t, {})
            syn = synthesis_per_ticker.get(t, {})

            # Detect currency from ticker suffix
            if t.endswith(".TW") or t.endswith(".TWO"):
                currency = "TWD"
                price_note = "Prices are in TWD (New Taiwan Dollar). Convert to USD context where helpful."
            else:
                currency = "USD"
                price_note = ""

            # ── Fundamental block ─────────────────────────────────────────────
            fundamental_block = f"""Fundamental: verdict={fa.get('valuation_verdict')} confidence={fa.get('confidence')}
  price={fa.get('current_price')} {currency} | mktcap={fa.get('market_cap_b')}B {currency} | beta={fa.get('beta')}
  PE={fa.get('pe_ratio')} | ForwardPE={fa.get('forward_pe')} | PEG={fa.get('peg_ratio')} | EV/EBITDA={fa.get('ev_ebitda')} | P/FCF={fa.get('pfcf_ratio')}
  DCF_base={fa.get('dcf_intrinsic_value')} {currency} | MoS={_pct(fa.get('dcf_margin_of_safety'))}
  TargetBear={fa.get('target_price_bear')} | TargetBase={fa.get('target_price_base')} | TargetBull={fa.get('target_price_bull')} {currency}
  BuyBelow={fa.get('buy_below_price')} {currency} | WACC={fa.get('wacc_used_pct')}%
  RevGrowth={fa.get('revenue_growth_pct')}% | GrossMargin={fa.get('gross_margin_pct')}% | OpMargin={fa.get('operating_margin_pct')}%
  FCF={fa.get('free_cash_flow_b')}B {currency} | ROE={fa.get('return_on_equity_pct')}% | ROA={fa.get('return_on_assets_pct')}%
  CashFlowQuality={_cf_quality(fa.get('cash_flow_quality'))}
  Reasoning: {fa.get('reasoning','')}
  Strengths: {', '.join(fa.get('key_strengths',[]))}
  Risks: {', '.join(fa.get('key_risks',[]))}
  TargetRationale: {fa.get('target_price_rationale','')}
  EntryStrategy: {fa.get('entry_strategy','')}"""

            # ── Growth block ──────────────────────────────────────────────────
            growth_block = f"""Growth: verdict={ga.get('growth_verdict')} score={ga.get('growth_quality_score')}/10
  RevCAGR3Y={ga.get('revenue_cagr_3y_pct')}% | EPS_CAGR3Y={ga.get('eps_cagr_3y_pct')}% | FCF_CAGR3Y={ga.get('fcf_cagr_3y_pct')}%
  RevTrend={ga.get('revenue_trend')} | EPSTrend={ga.get('eps_trend')} | FCFTrend={ga.get('fcf_trend')}
  PEG={ga.get('peg_ratio')} | ForwardGrowthEst={ga.get('forward_growth_estimate_pct')}%
  Catalysts: {', '.join(ga.get('growth_catalysts',[]))}
  GrowthRisks: {', '.join(ga.get('growth_risks',[]))}
  Reasoning: {ga.get('reasoning','')}"""

            # ── Peer comparison block ─────────────────────────────────────────
            peer_block = f"""Peers: verdict={pa.get('peer_verdict')} sector={pa.get('sector')}
  SectorMedianPE={pa.get('sector_median_pe')} | SectorMedianEV/EBITDA={pa.get('sector_median_ev_ebitda')}
  CompanyPE={pa.get('company_pe')} | PE_Discount={pa.get('company_pe_discount_pct')}%
  CompanyEV/EBITDA={pa.get('company_ev_ebitda')} | EVEB_Discount={pa.get('company_ev_ebitda_discount_pct')}%
  CompositePeerDiscount={pa.get('composite_peer_discount_pct')}%
  PeersUsed: {', '.join(pa.get('peers_used',[])[:5])}
  Reasoning: {pa.get('reasoning','')}"""

            # ── Sentiment block ───────────────────────────────────────────────
            sentiment_block = f"""Sentiment: score={sa.get('sentiment_score')} label={sa.get('sentiment_label')}
  consensus={sa.get('analyst_consensus')}
  insider={sa.get('insider_activity')}
  headlines={json.dumps(sa.get('top_headlines',[])[:3])}
  reasoning={sa.get('reasoning','')}"""

            # ── AI Value Chain block ──────────────────────────────────────────
            ai_skipped = bool(pg.get("skipped") or vcr.get("skipped") or vcp.get("skipped"))
            if ai_skipped:
                ai_block = (
                    f"AIValueChain: layer={lc.get('primary_layer')} ({lc.get('primary_layer_label')})\n"
                    f"  ai_exposure={lc.get('ai_exposure_type')} "
                    f"score={lc.get('ai_exposure_score')} — agents short-circuited (NEUTRAL / MINIMAL)."
                )
            else:
                risks_summary = "; ".join(
                    f"{r.get('risk_type')}({r.get('severity')}/{r.get('likelihood')})"
                    for r in (ar.get("risks") or [])[:4]
                )
                ai_block = f"""AIValueChain:
  Layer: {lc.get('primary_layer')} — {lc.get('primary_layer_label')} (conf {lc.get('layer_confidence')})
  AI exposure: {lc.get('ai_exposure_type')} ({lc.get('ai_exposure_score')}/100)
  Layer focus: {lc.get('layer_specific_focus','')}
  Value creation: current {vcr.get('current_creation_score')} ({vcr.get('current_creation_label')}) / future {vcr.get('future_creation_score')} (ceiling {vcr.get('future_creation_ceiling')})
    ai_role={vcr.get('ai_role')} tam={vcr.get('tam_expansion_potential')} moat={vcr.get('key_moat','')}
  Value capture: current {vcp.get('current_capture_score')} ({vcp.get('current_capture_rate')}) / future {vcp.get('future_capture_score')} ({vcp.get('future_capture_trajectory')})
    pricing_power={vcp.get('pricing_power_rating')} commoditization={vcp.get('commoditization_risk')} leakage={vcp.get('value_leakage_source','')}
  Pricing Gap: {pg.get('gap_direction')} {pg.get('gap_magnitude')} score={pg.get('gap_score')}
    market_implied={pg.get('market_implied_growth_rate_pct')}% ai_scenario={pg.get('ai_scenario_growth_rate_pct')}%
    consensus_vs_ai_scenario={pg.get('consensus_vs_ai_scenario')} uncertainty={pg.get('uncertainty_driver')} horizon={pg.get('time_horizon')}
    catalyst: {pg.get('key_rerating_catalyst','')}
    narrative: {pg.get('pricing_narrative','')}
    suggested_action: {pg.get('suggested_action')}
  AI Risk: {ar.get('overall_risk_level')} (score {ar.get('risk_score')}/100)
    primary_risk: {ar.get('primary_risk','')}
    top_risks: {risks_summary or '—'}
    thesis_breaker: {ar.get('thesis_breaker','')}
    bear_case: {ar.get('bear_case_scenario','')}
Synthesis: conviction={syn.get('conviction_score')} recommendation={syn.get('recommendation')}
  thesis: {syn.get('thesis','')}"""

            blocks.append(f"""### {t} (currency: {currency})
{price_note}
{fundamental_block}
{growth_block}
{peer_block}
{sentiment_block}
{ai_block}""")

        if not blocks:
            ticker_section = "⚠️ No ticker data was passed to the report writer. This is a pipeline error — do not generate a blank report. List the error prominently."
        else:
            ticker_section = "\n\n".join(blocks)

        macro_lines = []
        for k, v in macro.items():
            if isinstance(v, dict) and "value" in v:
                macro_lines.append(f"- {k.replace('_',' ').title()}: {v['value']}% ({v.get('date','')})")
        macro_text = "\n".join(macro_lines) or "Macro data unavailable."

        # ── AI-aware ranked summary (from the deterministic synthesis step) ────
        ranking = (synthesis or {}).get("ranking", [])
        if ranking:
            rank_lines = ["Rank | Ticker | Conviction | Recommendation | Layer | AI Gap | Thesis"]
            for i, r in enumerate(ranking, start=1):
                score = r.get("conviction_score")
                score_fmt = f"{score:+.1f}" if isinstance(score, (int, float)) else "?"
                gap = r.get("gap_score")
                gap_fmt = f"{gap:+d}" if isinstance(gap, int) else (f"{gap:+.0f}" if isinstance(gap, float) else "—")
                rank_lines.append(
                    f"{i} | {r.get('ticker')} | {score_fmt} | {r.get('recommendation')} | "
                    f"{r.get('primary_layer') or '—'} | {gap_fmt} | {r.get('thesis','')[:120]}"
                )
            ranking_text = "\n".join(rank_lines)
        else:
            ranking_text = "No synthesis ranking available."

        return f"""Generate a professional daily equity analyst report for {run_date}.

## Macro Environment
{macro_text}

## AI-Aware Conviction Ranking (deterministic synthesis)
This ranking is computed in-process from the agent outputs using the weighting
  final = 0.4·gap_score + 0.3·future_creation/10 + 0.2·future_capture/10 − 0.1·risk/10
with adjustments for SPECULATIVE uncertainty, CRITICAL AI risk, and strong
disagreement between the classic fundamental verdict and the AI lens.
Use this as the primary ordering for the Executive Summary and the Top Picks table.

{ranking_text}

## Ticker Data
{ticker_section}

Follow your system prompt format exactly. Date the report {run_date}.
Include the full valuation table, growth profile, peer comparison, AI value chain
analysis, and entry strategy for each ticker. Use only the data provided —
do not invent numbers. Where the `AIValueChain:` block says the agents
short-circuited, honestly state that AI-specific analysis was skipped for that
ticker rather than fabricating it."""

    def _save_report(self, markdown: str, run_date: str, tickers: list[str]) -> Path:
        out = self.settings.report_output_dir
        out.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H-%M-%S")
        # Embed up to 4 tickers in the filename so files are self-describing.
        # e.g. 2026-04-11_17-34-22_TSM-AAPL-MSFT_analyst_report.md
        ticker_slug = "-".join(t.replace(".", "") for t in tickers[:4])
        if len(tickers) > 4:
            ticker_slug += f"+{len(tickers) - 4}more"
        path = out / f"{run_date}_{timestamp}_{ticker_slug}_analyst_report.md"
        path.write_text(markdown, encoding="utf-8")
        logger.info("[%s] Saved → %s", self.name, path)
        return path

    def _extract_summary(self, markdown: str) -> str:
        """Pull the Executive Summary section out of the report.

        The summary is rendered as markdown in the UI, so we keep the original
        formatting (bold, bullet lists) and leave a generous character budget
        instead of clipping mid-sentence.
        """
        m = re.search(r"##\s+.*?Executive Summary.*?\n+(.*?)(?=\n##|\Z)", markdown, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        try:
            return self.call_claude(
                [{"role": "user", "content": f"Write a 3-sentence executive summary of this report:\n\n{markdown[:3000]}"}],
                system="You are a financial editor. Be concise.",
                max_tokens=250, temperature=0.2,
            )
        except Exception:
            return markdown[:600]


def _pct(v: Any) -> str:
    return f"{round(float(v)*100,1)}%" if v is not None else "N/A"


def _cf_quality(v: Any) -> str:
    if not v or not isinstance(v, dict):
        return "N/A"
    return f"{v.get('quality','?')} (ratio={v.get('ratio','?')})"
