"""Shared helpers for the AI value chain agents."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_json(raw: str, ticker: str, fallback: dict[str, Any]) -> dict[str, Any]:
    """Tolerant JSON parser — strips markdown fences and falls back to brace-search.

    If parsing fails, return `fallback` enriched with a short `reasoning` slice
    so the downstream pipeline can still show something useful.
    """
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse JSON for %s", ticker)
    return {**fallback, "reasoning": raw[:300]}


def company_overview(td: dict[str, Any], max_chars: int = 1500) -> str:
    """Return a short business overview excerpt from the collected SEC filing."""
    sec = td.get("sec_filing", {}) or {}
    sections = sec.get("key_sections") or {}
    overview = sections.get("business_overview") or sections.get("mda") or ""
    return (overview or "")[:max_chars]


def sector_and_industry(ticker: str, td: dict[str, Any], pa: dict[str, Any] | None = None) -> tuple[str, str]:
    """Best-effort sector/industry resolution.

    Prefer the sector already resolved by the PeerComparison agent (no extra API
    call). Fall back to a live yfinance lookup only if neither is available.
    """
    if pa and pa.get("sector"):
        return (pa.get("sector") or "Unknown", pa.get("industry") or "Unknown")

    sec = td.get("sec_filing", {}) or {}
    meta_sector = (sec.get("company_meta") or {}).get("sector")
    meta_industry = (sec.get("company_meta") or {}).get("industry")
    if meta_sector:
        return (meta_sector, meta_industry or "Unknown")

    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return (info.get("sector") or "Unknown", info.get("industry") or "Unknown")
    except Exception:
        return ("Unknown", "Unknown")


def format_financial_summary(
    ticker: str,
    td: dict[str, Any],
    fa: dict[str, Any],
    pa: dict[str, Any] | None = None,
) -> str:
    """Compact, agent-facing financial summary used in prompts."""
    sector, industry = sector_and_industry(ticker, td, pa)
    return (
        f"Ticker: {ticker}\n"
        f"Sector: {sector} | Industry: {industry}\n"
        f"Market cap: {fa.get('market_cap_b')}B | Price: {fa.get('current_price')} | Beta: {fa.get('beta')}\n"
        f"P/E: {fa.get('pe_ratio')} | Fwd P/E: {fa.get('forward_pe')} | PEG: {fa.get('peg_ratio')} | "
        f"EV/EBITDA: {fa.get('ev_ebitda')} | P/FCF: {fa.get('pfcf_ratio')}\n"
        f"Revenue growth: {fa.get('revenue_growth_pct')}% | Gross margin: {fa.get('gross_margin_pct')}% | "
        f"Operating margin: {fa.get('operating_margin_pct')}%\n"
        f"FCF: {fa.get('free_cash_flow_b')}B | ROE: {fa.get('return_on_equity_pct')}% | ROA: {fa.get('return_on_assets_pct')}%\n"
    )
