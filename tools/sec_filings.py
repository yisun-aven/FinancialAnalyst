"""SEC EDGAR filing fetcher.

Retrieves 10-K and 10-Q filings via the SEC EDGAR REST API.
No authentication or API key required — SEC EDGAR is a public API.

Rate limit: SEC requests a max of 10 requests/second with a User-Agent header.
We stay well under that with a single sequential fetch per ticker.

Flow:
    1. Resolve ticker → CIK via EDGAR company search API
    2. Fetch the filing index for the most recent matching form type
    3. Locate the primary HTML/HTM document in the index
    4. Fetch and strip it to plain text
    5. Extract key sections: MD&A, Risk Factors, Business Overview, Guidance
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Literal

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FilingType = Literal["10-K", "10-Q"]

_EDGAR_BASE = "https://data.sec.gov"
_EDGAR_ARCHIVE_BASE = "https://www.sec.gov"
_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_USER_AGENT = "FinancialAnalystBot contact@example.com"  # SEC requires a User-Agent
_HEADERS = {"User-Agent": _USER_AGENT, "Accept-Encoding": "gzip, deflate"}
_REQUEST_DELAY = 0.15  # seconds between requests — stay well under 10 req/s

# Max characters to extract per section (keeps context manageable for LLMs)
_SECTION_MAX_CHARS = 8_000


def fetch_sec_filing(ticker: str, form_type: FilingType = "10-K") -> dict[str, Any]:
    """Fetch the most recent SEC filing and extract key narrative sections.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        form_type: "10-K" (annual) or "10-Q" (quarterly).

    Returns:
        Dict with keys:
            ticker, form_type, cik, company_name,
            filing_date, accession_number, filing_url,
            key_sections: {
                business_overview,  # Item 1
                risk_factors,       # Item 1A
                mda,                # Item 7 / Item 2 (10-Q)
                guidance,           # Forward-looking statements extracted from MDA
            }
            Each section is a plain-text string (up to _SECTION_MAX_CHARS chars)
            or None if the section was not found.
    """
    logger.info("Fetching %s filing for %s", form_type, ticker)

    cik, company_name = _resolve_cik(ticker)
    filing_meta = _get_latest_filing_meta(cik, form_type)

    accession_clean = filing_meta["accession_number"].replace("-", "")
    cik_int = str(int(cik))  # strip leading zeros for archive URLs
    index_url = (
        f"{_EDGAR_ARCHIVE_BASE}/Archives/edgar/data/{cik_int}/{accession_clean}/"
        f"{filing_meta['accession_number']}-index.htm"
    )

    primary_doc_url = (
        f"{_EDGAR_ARCHIVE_BASE}/Archives/edgar/data/{cik_int}/{accession_clean}/"
        f"{filing_meta['primary_document']}"
    )
    full_text = _fetch_and_strip_html(primary_doc_url)
    key_sections = _extract_sections(full_text, form_type)

    return {
        "ticker": ticker,
        "form_type": form_type,
        "cik": cik,
        "company_name": company_name,
        "filing_date": filing_meta["filing_date"],
        "accession_number": filing_meta["accession_number"],
        "filing_url": index_url,
        "primary_doc_url": primary_doc_url,
        "key_sections": key_sections,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_cik(ticker: str) -> tuple[str, str]:
    """Resolve a ticker symbol to a zero-padded CIK and company name.

    Uses the EDGAR company search endpoint which maps tickers to CIKs.

    Returns:
        (cik_padded, company_name) — CIK is zero-padded to 10 digits.

    Raises:
        ValueError: If the ticker cannot be resolved.
    """
    url = f"{_EDGAR_BASE}/submissions/CIK.json"  # placeholder — use ticker search below
    search_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"

    # Use the company tickers JSON — updated daily by SEC
    resp = _get("https://www.sec.gov/files/company_tickers.json")
    tickers_map: dict[str, dict[str, Any]] = resp.json()

    ticker_upper = ticker.upper()
    for entry in tickers_map.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            return cik, entry.get("title", ticker_upper)

    raise ValueError(
        f"Could not resolve CIK for ticker '{ticker}'. "
        "SEC EDGAR only covers US-listed companies; non-US tickers (e.g. .TW, .HK) "
        "will not have SEC filings — this is expected."
    )


def _get_latest_filing_meta(cik: str, form_type: str) -> dict[str, str]:
    """Return accession_number and filing_date for the most recent matching filing.

    Args:
        cik: Zero-padded 10-digit CIK string.
        form_type: "10-K" or "10-Q".

    Returns:
        Dict with keys: accession_number (formatted with dashes), filing_date.

    Raises:
        ValueError: If no matching filing is found.
    """
    submissions_url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = _get(submissions_url)
    data = resp.json()

    def _search_block(block: dict[str, Any]) -> dict[str, str] | None:
        forms = block.get("form", [])
        dates = block.get("filingDate", [])
        accessions = block.get("accessionNumber", [])
        primary_docs = block.get("primaryDocument", [])
        for form, date, accession, primary_doc in zip(forms, dates, accessions, primary_docs):
            if form == form_type:
                return {
                    "accession_number": accession,
                    "filing_date": date,
                    "primary_document": primary_doc,
                }
        return None

    recent = data.get("filings", {}).get("recent", {})
    result = _search_block(recent)
    if result:
        return result

    # Check older filings pages if not found in recent
    for extra_file in data.get("filings", {}).get("files", []):
        extra_url = f"{_EDGAR_BASE}/submissions/{extra_file['name']}"
        extra_resp = _get(extra_url)
        result = _search_block(extra_resp.json())
        if result:
            return result

    raise ValueError(f"No {form_type} filing found for CIK {cik}.")



def _fetch_and_strip_html(url: str) -> str:
    """Download an HTML filing document and return clean plain text.

    Strips all HTML tags, normalises whitespace, and removes XBRL boilerplate.
    """
    logger.debug("Fetching filing document: %s", url)
    resp = _get(url)

    soup = BeautifulSoup(resp.content, "html.parser")

    # Remove script, style, and XBRL hidden elements
    for tag in soup(["script", "style", "ix:hidden", "ix:nonnumeric"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse runs of blank lines and leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if not line:
            blank_run += 1
            if blank_run <= 2:
                cleaned_lines.append("")
        else:
            blank_run = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _extract_sections(text: str, form_type: str) -> dict[str, str | None]:
    """Extract key narrative sections from the full filing plain text.

    Uses regex to find standard SEC section headers (Item 1, 1A, 7, etc.).
    Extracts up to _SECTION_MAX_CHARS of content per section.

    Returns:
        Dict with keys: business_overview, risk_factors, mda, guidance.
    """
    # Item numbers differ slightly between 10-K and 10-Q
    if form_type == "10-K":
        section_patterns = {
            "business_overview": r"item\s+1[\.\s]+business",
            "risk_factors": r"item\s+1a[\.\s]+risk\s+factors",
            "mda": r"item\s+7[\.\s]+management.{0,30}discussion",
        }
    else:  # 10-Q
        section_patterns = {
            "business_overview": r"item\s+1[\.\s]+financial\s+statements",
            "risk_factors": r"item\s+1a[\.\s]+risk\s+factors",
            "mda": r"item\s+2[\.\s]+management.{0,30}discussion",
        }

    sections: dict[str, str | None] = {}
    text_lower = text.lower()

    # Find the best match for each section pattern.
    # Strategy: the Table of Contents is always in the first ~5% of the document.
    # We collect all occurrences of each pattern and prefer the LAST one that
    # appears before 90% of the document length, which is the actual section body.
    doc_len = len(text_lower)
    cutoff = int(doc_len * 0.90)

    all_matches: list[tuple[int, str]] = []
    for section_name, pattern in section_patterns.items():
        candidates = [m.start() for m in re.finditer(pattern, text_lower) if m.start() < cutoff]
        if not candidates:
            continue
        # If multiple occurrences, skip the first (TOC) when there are 2+
        chosen = candidates[-1] if len(candidates) >= 2 else candidates[0]
        all_matches.append((chosen, section_name))

    all_matches.sort()

    for i, (start_pos, section_name) in enumerate(all_matches):
        # Section ends where the next section begins (or _SECTION_MAX_CHARS)
        if i + 1 < len(all_matches):
            end_pos = min(start_pos + _SECTION_MAX_CHARS, all_matches[i + 1][0])
        else:
            end_pos = start_pos + _SECTION_MAX_CHARS

        content = text[start_pos:end_pos].strip()
        sections[section_name] = content if content else None

    # Fill in any sections not found
    for key in ("business_overview", "risk_factors", "mda"):
        sections.setdefault(key, None)

    # Extract forward-looking / guidance language from MDA
    sections["guidance"] = _extract_guidance(sections.get("mda") or "")

    return sections


def _extract_guidance(mda_text: str) -> str | None:
    """Pull forward-looking statements and guidance language from the MDA section."""
    if not mda_text:
        return None

    guidance_keywords = [
        r"we expect", r"we anticipate", r"we believe", r"we intend",
        r"outlook", r"guidance", r"fiscal \d{4}", r"going forward",
        r"next quarter", r"next fiscal", r"full.year",
    ]
    pattern = "|".join(guidance_keywords)
    lines = mda_text.splitlines()
    guidance_lines: list[str] = []

    for line in lines:
        if re.search(pattern, line.lower()):
            guidance_lines.append(line.strip())
            if len("\n".join(guidance_lines)) >= 3_000:
                break

    return "\n".join(guidance_lines) if guidance_lines else None


def _get(url: str) -> requests.Response:
    """HTTP GET with required SEC User-Agent header and a small delay."""
    time.sleep(_REQUEST_DELAY)
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp
