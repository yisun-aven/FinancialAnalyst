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

        prompt = self._build_prompt(tickers, run_date, fundamental, growth, peers, sentiment, macro)
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
    ) -> str:
        blocks = []
        for t in tickers:
            fa = fundamental.get(t, {})
            ga = growth.get(t, {})
            pa = peers.get(t, {})
            sa = sentiment.get(t, {})

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

            blocks.append(f"""### {t} (currency: {currency})
{price_note}
{fundamental_block}
{growth_block}
{peer_block}
{sentiment_block}""")

        if not blocks:
            ticker_section = "⚠️ No ticker data was passed to the report writer. This is a pipeline error — do not generate a blank report. List the error prominently."
        else:
            ticker_section = "\n\n".join(blocks)

        macro_lines = []
        for k, v in macro.items():
            if isinstance(v, dict) and "value" in v:
                macro_lines.append(f"- {k.replace('_',' ').title()}: {v['value']}% ({v.get('date','')})")
        macro_text = "\n".join(macro_lines) or "Macro data unavailable."

        return f"""Generate a professional daily equity analyst report for {run_date}.

## Macro Environment
{macro_text}

## Ticker Data
{ticker_section}

Follow your system prompt format exactly. Date the report {run_date}.
Include the full valuation table, growth profile, peer comparison, and entry strategy for each ticker.
Use only the data provided — do not invent numbers."""

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
        m = re.search(r"##\s+.*?Executive Summary.*?\n+(.*?)(?=\n##|\Z)", markdown, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()[:800]
        try:
            return self.call_claude(
                [{"role": "user", "content": f"Write a 3-sentence executive summary of this report:\n\n{markdown[:3000]}"}],
                system="You are a financial editor. Be concise.",
                max_tokens=250, temperature=0.2,
            )
        except Exception:
            return markdown[:400]


def _pct(v: Any) -> str:
    return f"{round(float(v)*100,1)}%" if v is not None else "N/A"


def _cf_quality(v: Any) -> str:
    if not v or not isinstance(v, dict):
        return "N/A"
    return f"{v.get('quality','?')} (ratio={v.get('ratio','?')})"
