"""Conviction synthesis — deterministic, in-process composite scoring.

Not a Claude-calling agent. Combines outputs from fundamental, growth, peer,
pricing_gap, ai_risk, and sentiment into a single `conviction_score` per ticker
and a final `recommendation` (BUY / ACCUMULATE / HOLD / TRIM / AVOID).

The score follows the weighting proposed in the AI value chain reference doc:
    final_score = (gap_score × 0.4)
                + (future_creation_score/10 × 0.3)
                + (future_capture_score/10 × 0.2)
                - (risk_score/10 × 0.1)

Normalised to -10..+10 where it is directly comparable to `gap_score`.

In Mode 2 (screener), this is also used to re-rank the top N so the final
ranking reflects the full AI value chain lens, not just the quantitative
pre-screen.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default weighting — can be surfaced as a user setting in the future
_WEIGHTS = {
    "gap": 0.40,
    "future_creation": 0.30,
    "future_capture": 0.20,
    "risk": 0.10,
}

_ACTION_BANDS: list[tuple[float, str]] = [
    (6.0, "BUY"),
    (3.0, "ACCUMULATE"),
    (-2.0, "HOLD"),
    (-5.0, "TRIM"),
    (-10.1, "AVOID"),
]


def synthesize_ticker(
    ticker: str,
    fundamental: dict[str, Any],
    pricing_gap: dict[str, Any],
    value_creation: dict[str, Any],
    value_capture: dict[str, Any],
    ai_risk: dict[str, Any],
    sentiment: dict[str, Any],
    layer_cls: dict[str, Any],
) -> dict[str, Any]:
    """Return a conviction block for a single ticker.

    Keys:
        conviction_score: float in [-10, +10]
        recommendation:   BUY | ACCUMULATE | HOLD | TRIM | AVOID
        thesis:           one-sentence plain-English summary
        components:       dict of the inputs that fed the score
        adjustments:      list of notable adjustments (e.g. 'trimmed due to SPECULATIVE uncertainty')
    """
    gap_score = _safe_num(pricing_gap.get("gap_score"))
    future_creation = _safe_num(value_creation.get("future_creation_score"))
    future_capture = _safe_num(value_capture.get("future_capture_score"))
    risk_score = _safe_num(ai_risk.get("risk_score"))

    # Normalise 0-100 scores to -10..+10 by centering on 50
    creation_norm = (future_creation - 50) / 5.0 if future_creation is not None else 0.0
    capture_norm = (future_capture - 50) / 5.0 if future_capture is not None else 0.0
    risk_norm = (risk_score - 30) / 7.0 if risk_score is not None else 0.0  # centered at 30 (benign)
    gap_norm = gap_score if gap_score is not None else 0.0

    raw_score = (
        _WEIGHTS["gap"] * gap_norm
        + _WEIGHTS["future_creation"] * creation_norm
        + _WEIGHTS["future_capture"] * capture_norm
        - _WEIGHTS["risk"] * risk_norm
    )

    adjustments: list[str] = []

    uncertainty = (pricing_gap.get("uncertainty_driver") or "").upper()
    if uncertainty == "SPECULATIVE" and raw_score > 0:
        penalty = raw_score * 0.35
        raw_score -= penalty
        adjustments.append(f"-{penalty:.2f} for SPECULATIVE uncertainty driver")
    elif uncertainty == "STRUCTURAL" and raw_score > 0:
        bonus = min(0.5, raw_score * 0.08)
        raw_score += bonus
        adjustments.append(f"+{bonus:.2f} for STRUCTURAL fundamentals")

    if ai_risk.get("overall_risk_level") == "CRITICAL":
        raw_score -= 1.5
        adjustments.append("-1.5 for CRITICAL AI risk level")

    fund_verdict = (fundamental.get("valuation_verdict") or "").lower()
    if fund_verdict == "overvalued" and raw_score > 0:
        raw_score *= 0.75
        adjustments.append("×0.75 because classic fundamentals still flag 'overvalued'")
    elif fund_verdict == "undervalued" and raw_score < 0:
        raw_score *= 0.75
        adjustments.append("×0.75 because classic fundamentals still flag 'undervalued'")

    sentiment_label = (sentiment.get("sentiment_label") or "").lower()
    if sentiment_label == "very_bearish":
        raw_score -= 0.25
        adjustments.append("-0.25 for very_bearish sentiment")
    elif sentiment_label == "very_bullish" and raw_score < 0:
        raw_score += 0.25
        adjustments.append("+0.25 for very_bullish sentiment (crowding)")

    conviction_score = max(-10.0, min(10.0, round(raw_score, 2)))
    recommendation = _action_from_score(conviction_score)

    suggested_action = (pricing_gap.get("suggested_action") or "").upper()
    if (
        suggested_action in ("BUY", "ACCUMULATE", "HOLD", "TRIM", "AVOID")
        and _distance(suggested_action, recommendation) >= 2
    ):
        recommendation = suggested_action
        adjustments.append(f"overrode deterministic → {suggested_action} from pricing_gap analyst")

    thesis = _build_thesis(
        ticker=ticker,
        conviction_score=conviction_score,
        recommendation=recommendation,
        pricing_gap=pricing_gap,
        value_creation=value_creation,
        value_capture=value_capture,
        layer_cls=layer_cls,
    )

    return {
        "conviction_score": conviction_score,
        "recommendation": recommendation,
        "thesis": thesis,
        "components": {
            "gap_score": gap_score,
            "future_creation_score": future_creation,
            "future_capture_score": future_capture,
            "risk_score": risk_score,
            "fundamental_verdict": fund_verdict or None,
            "sentiment_label": sentiment_label or None,
            "uncertainty_driver": uncertainty or None,
            "primary_layer": layer_cls.get("primary_layer"),
            "ai_exposure_type": layer_cls.get("ai_exposure_type"),
        },
        "weights": _WEIGHTS,
        "adjustments": adjustments,
    }


def synthesize_all(context: dict[str, Any]) -> dict[str, Any]:
    """Apply `synthesize_ticker` to every ticker in the pipeline context.

    Returns the same dict keyed by ticker, and also sorts a ranked list of
    `{ticker, conviction_score, recommendation, thesis}` used by Mode 2 to
    re-order the screened top N.
    """
    tickers: list[str] = context.get("tickers", [])
    fund = context.get("fundamental_analysis", {}) or {}
    gap = context.get("pricing_gap", {}) or {}
    creation = context.get("value_creation", {}) or {}
    capture = context.get("value_capture", {}) or {}
    risk = context.get("ai_risk", {}) or {}
    sent = context.get("sentiment_analysis", {}) or {}
    layer = context.get("layer_classification", {}) or {}

    per_ticker: dict[str, Any] = {}
    for t in tickers:
        per_ticker[t] = synthesize_ticker(
            ticker=t,
            fundamental=fund.get(t, {}) or {},
            pricing_gap=gap.get(t, {}) or {},
            value_creation=creation.get(t, {}) or {},
            value_capture=capture.get(t, {}) or {},
            ai_risk=risk.get(t, {}) or {},
            sentiment=sent.get(t, {}) or {},
            layer_cls=layer.get(t, {}) or {},
        )

    ranking = sorted(
        (
            {
                "ticker": t,
                "conviction_score": per_ticker[t]["conviction_score"],
                "recommendation": per_ticker[t]["recommendation"],
                "thesis": per_ticker[t]["thesis"],
                "gap_score": per_ticker[t]["components"].get("gap_score"),
                "primary_layer": per_ticker[t]["components"].get("primary_layer"),
            }
            for t in tickers
        ),
        key=lambda r: (r["conviction_score"] if r["conviction_score"] is not None else -99),
        reverse=True,
    )

    return {"per_ticker": per_ticker, "ranking": ranking}


def _safe_num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _action_from_score(score: float) -> str:
    for threshold, action in _ACTION_BANDS:
        if score >= threshold:
            return action
    return "AVOID"


_ACTION_ORDER = ["AVOID", "TRIM", "HOLD", "ACCUMULATE", "BUY"]


def _distance(a: str, b: str) -> int:
    try:
        return abs(_ACTION_ORDER.index(a) - _ACTION_ORDER.index(b))
    except ValueError:
        return 0


def _build_thesis(
    ticker: str,
    conviction_score: float,
    recommendation: str,
    pricing_gap: dict[str, Any],
    value_creation: dict[str, Any],
    value_capture: dict[str, Any],
    layer_cls: dict[str, Any],
) -> str:
    layer = layer_cls.get("primary_layer") or "NEUTRAL"
    label = layer_cls.get("primary_layer_label") or "no clear AI value chain position"
    gap_dir = (pricing_gap.get("gap_direction") or "FAIRLY_PRICED").lower().replace("_", " ")
    catalyst = pricing_gap.get("key_rerating_catalyst") or "no specific catalyst identified"
    capture_traj = (value_capture.get("future_capture_trajectory") or "").lower()
    creation_ceiling = (value_creation.get("future_creation_ceiling") or "").lower().replace("_", " ")

    return (
        f"{ticker}: {recommendation} — conviction {conviction_score:+.1f}. "
        f"{layer} ({label}); AI lens says {gap_dir} with "
        f"{creation_ceiling or 'moderate'} creation ceiling and "
        f"{capture_traj or 'stable'} capture. Watch: {catalyst}."
    )
