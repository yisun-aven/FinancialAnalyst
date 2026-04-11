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
        sentiment = context.get("sentiment_analysis", {})
        macro = context.get("macro_data", {})

        prompt = self._build_prompt(tickers, run_date, fundamental, sentiment, macro)
        logger.info("[%s] Generating report for %d tickers", self.name, len(tickers))

        report_markdown = self.call_claude(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        report_path = self._save_report(report_markdown, run_date)

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

    def _build_prompt(self, tickers, run_date, fundamental, sentiment, macro) -> str:
        blocks = []
        for t in tickers:
            fa = fundamental.get(t, {})
            sa = sentiment.get(t, {})
            # Detect currency from ticker suffix so Claude labels prices correctly
            if t.endswith(".TW") or t.endswith(".TWO"):
                currency = "TWD"
                price_note = "Prices are in TWD (New Taiwan Dollar). Convert to USD context where helpful."
            else:
                currency = "USD"
                price_note = ""
            blocks.append(f"""### {t} (currency: {currency})
{price_note}
Fundamental: verdict={fa.get('valuation_verdict')} confidence={fa.get('confidence')}
  price={fa.get('current_price')} {currency} mktcap={fa.get('market_cap_b')}B {currency}
  PE={fa.get('pe_ratio')} ForwardPE={fa.get('forward_pe')} EV/EBITDA={fa.get('ev_ebitda')}
  DCF={fa.get('dcf_intrinsic_value')} {currency} MoS={_pct(fa.get('dcf_margin_of_safety'))}
  RevGrowth={fa.get('revenue_growth_pct')}% GrossMargin={fa.get('gross_margin_pct')}% FCF={fa.get('free_cash_flow_b')}B {currency}
  Reasoning: {fa.get('reasoning','')}
  Strengths: {', '.join(fa.get('key_strengths',[]))}
  Risks: {', '.join(fa.get('key_risks',[]))}
Sentiment: score={sa.get('sentiment_score')} label={sa.get('sentiment_label')}
  consensus={sa.get('analyst_consensus')}
  insider={sa.get('insider_activity')}
  headlines={json.dumps(sa.get('top_headlines',[])[:3])}
  reasoning={sa.get('reasoning','')}""")

        if not blocks:
            ticker_section = "⚠️ No ticker data was passed to the report writer. This is a pipeline error — do not generate a blank report. List the error prominently."
        else:
            ticker_section = "".join(blocks)

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

Follow your system prompt format exactly. Date the report {run_date}. Use only the data provided."""

    def _save_report(self, markdown: str, run_date: str) -> Path:
        out = self.settings.report_output_dir
        out.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H-%M-%S")
        path = out / f"{run_date}_{timestamp}_analyst_report.md"
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
