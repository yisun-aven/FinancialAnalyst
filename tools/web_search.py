"""Web search tool — wraps Anthropic's built-in web_search_20250305 tool.

Usage pattern A (standalone):
    results = web_search("AAPL earnings call Q1 2026")

Usage pattern B (give Claude the tool directly in a call_claude() call):
    agent.call_claude(messages, tools=[WEB_SEARCH_TOOL])
    Claude will then search autonomously as part of its response.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Tool definition — pass this list to call_claude(tools=...) to give any agent
# the ability to search the web during its Claude call.
WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
}


def web_search(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Search the web via Claude's built-in web_search_20250305 tool.

    Sends the query to Claude (Haiku for cost efficiency) with the web search
    tool enabled and asks it to return structured JSON results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to request.

    Returns:
        List of dicts with keys: title, url, snippet, published_date.
        Returns an empty list on failure (never raises).
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = (
        f"Search the web for: {query}\n\n"
        f"Return ONLY a JSON array of the top {max_results} results. "
        "Each element must have exactly these keys: "
        '"title", "url", "snippet", "published_date". '
        "No markdown fences, no explanation — just the JSON array."
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    try:
        for _turn in range(6):
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                tools=[WEB_SEARCH_TOOL],
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = [
                    {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                    for b in response.content
                    if b.type == "tool_use"
                ]
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # Extract text from the final response
        raw_text = "\n".join(
            b.text for b in response.content if hasattr(b, "text") and b.text
        )

        return _parse_results(raw_text, max_results)

    except Exception as exc:
        logger.error("web_search failed for query '%s': %s", query, exc)
        return []


def _parse_results(text: str, max_results: int) -> list[dict[str, Any]]:
    """Extract a JSON array from Claude's text response."""
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)

    try:
        data = json.loads(text.strip())
        if isinstance(data, list):
            return data[:max_results]
    except json.JSONDecodeError:
        pass

    # Fallback: try to find a JSON array anywhere in the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data[:max_results]
        except json.JSONDecodeError:
            pass

    # Last resort: return the raw text as a single result
    if text.strip():
        return [{"title": "Search summary", "url": "", "snippet": text[:500], "published_date": ""}]

    return []
