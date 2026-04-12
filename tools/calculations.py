"""Financial calculation functions.

Pure functions — no side effects, no I/O. These are called by agents
to compute valuation metrics from raw financial data.

All dollar amounts are assumed to be in millions unless noted.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_pe_ratio(market_price: float, earnings_per_share: float) -> float | None:
    """Compute trailing Price-to-Earnings ratio.

    Args:
        market_price: Current share price.
        earnings_per_share: Trailing twelve-month EPS.

    Returns:
        P/E ratio, or None if EPS is zero or negative.
    """
    if earnings_per_share <= 0:
        return None
    return round(market_price / earnings_per_share, 2)


def calculate_ev_ebitda(
    market_cap: float,
    total_debt: float,
    cash_and_equivalents: float,
    ebitda: float,
) -> float | None:
    """Compute Enterprise Value / EBITDA.

    EV = Market Cap + Total Debt - Cash

    Args:
        market_cap: Market capitalisation (millions).
        total_debt: Total debt (millions).
        cash_and_equivalents: Cash and short-term investments (millions).
        ebitda: Earnings before interest, taxes, depreciation, amortisation (millions).

    Returns:
        EV/EBITDA multiple, or None if EBITDA is zero or negative.
    """
    if ebitda <= 0:
        return None
    ev = market_cap + total_debt - cash_and_equivalents
    return round(ev / ebitda, 2)


def calculate_dcf(
    free_cash_flows: list[float],
    terminal_growth_rate: float,
    discount_rate: float,
    shares_outstanding: float,
) -> float:
    """Estimate intrinsic value per share via a simple DCF model.

    Args:
        free_cash_flows: Projected annual FCF for each forecast year (millions).
        terminal_growth_rate: Perpetuity growth rate for terminal value (e.g. 0.03).
        discount_rate: WACC / required rate of return (e.g. 0.10).
        shares_outstanding: Total diluted shares outstanding (millions).

    Returns:
        Estimated intrinsic value per share.

    Raises:
        ValueError: If discount_rate <= terminal_growth_rate.
    """
    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount_rate must be greater than terminal_growth_rate")

    # Present value of forecast cash flows
    pv_fcfs = sum(
        fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(free_cash_flows)
    )

    # Terminal value using Gordon Growth Model
    terminal_fcf = free_cash_flows[-1] * (1 + terminal_growth_rate)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
    pv_terminal = terminal_value / (1 + discount_rate) ** len(free_cash_flows)

    intrinsic_value_total = pv_fcfs + pv_terminal
    return round(intrinsic_value_total / shares_outstanding, 2)


def calculate_ratios(
    *,
    net_income: float,
    shareholders_equity: float,
    total_debt: float,
    current_assets: float,
    current_liabilities: float,
    invested_capital: float,
    nopat: float,
) -> dict[str, float | None]:
    """Compute key financial health and return ratios.

    Args:
        net_income: Trailing twelve-month net income (millions).
        shareholders_equity: Total shareholders' equity (millions).
        total_debt: Total debt (millions).
        current_assets: Current assets (millions).
        current_liabilities: Current liabilities (millions).
        invested_capital: Total invested capital (millions).
        nopat: Net operating profit after tax (millions).

    Returns:
        Dict with keys: roe, debt_to_equity, current_ratio, roic.
        Values are rounded floats, or None when denominator is zero.
    """
    roe = round(net_income / shareholders_equity, 4) if shareholders_equity else None
    debt_to_equity = round(total_debt / shareholders_equity, 4) if shareholders_equity else None
    current_ratio = round(current_assets / current_liabilities, 4) if current_liabilities else None
    roic = round(nopat / invested_capital, 4) if invested_capital else None

    return {
        "roe": roe,
        "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "roic": roic,
    }


def calculate_peg_ratio(pe_ratio: float, eps_growth_rate_pct: float) -> float | None:
    """Compute the Price/Earnings-to-Growth (PEG) ratio.

    PEG < 1.0 historically suggests a stock may be undervalued relative to its
    earnings growth rate. PEG > 2.0 suggests expensive relative to growth.

    Args:
        pe_ratio: Trailing or forward P/E ratio.
        eps_growth_rate_pct: Expected annual EPS growth rate as a percentage (e.g. 15.0 for 15%).

    Returns:
        PEG ratio rounded to 2 decimal places, or None if inputs are invalid.
    """
    if pe_ratio is None or eps_growth_rate_pct is None:
        return None
    if pe_ratio <= 0 or eps_growth_rate_pct <= 0:
        return None
    return round(pe_ratio / eps_growth_rate_pct, 2)


def calculate_pfcf_ratio(price: float, fcf_per_share: float) -> float | None:
    """Compute the Price-to-Free-Cash-Flow (P/FCF) ratio.

    P/FCF strips out accounting distortions and shows what investors pay for
    actual cash generation. Below 15x is generally considered attractive.

    Args:
        price: Current share price.
        fcf_per_share: Free cash flow per diluted share (TTM).

    Returns:
        P/FCF ratio rounded to 2 decimal places, or None if FCF is zero/negative.
    """
    if price is None or fcf_per_share is None:
        return None
    if fcf_per_share <= 0:
        return None
    return round(price / fcf_per_share, 2)


def calculate_target_price(
    free_cash_flows: list[float],
    shares_outstanding: float,
    *,
    beta: float = 1.0,
    risk_free_rate: float = 0.045,
    equity_risk_premium: float = 0.055,
    terminal_growth_rate: float = 0.03,
    bull_growth_boost: float = 0.05,
    bear_growth_haircut: float = 0.05,
) -> dict[str, float | None]:
    """Compute bull / base / bear DCF target prices and a recommended buy-below price.

    Uses CAPM to derive a beta-adjusted WACC for each scenario:
        WACC = risk_free_rate + beta * equity_risk_premium

    The three scenarios vary the FCF growth assumption:
        - Base: FCF growth as projected (from historical CAGR, capped at 20%)
        - Bull: Base growth + bull_growth_boost (optimistic case)
        - Bear: Base growth - bear_growth_haircut (pessimistic case)

    The buy-below price is the bear-case intrinsic value, providing a margin of
    safety even under the worst modelled scenario.

    Args:
        free_cash_flows: Projected annual FCF for each forecast year (millions).
        shares_outstanding: Total diluted shares outstanding (millions).
        beta: Stock beta (default 1.0 = market risk).
        risk_free_rate: Risk-free rate, e.g. 10-year Treasury yield (default 4.5%).
        equity_risk_premium: Equity risk premium (default 5.5%).
        terminal_growth_rate: Perpetuity growth rate for terminal value (default 3%).
        bull_growth_boost: Additional annual growth applied in the bull scenario (default +5%).
        bear_growth_haircut: Growth reduction applied in the bear scenario (default -5%).

    Returns:
        Dict with keys:
            target_price_base, target_price_bull, target_price_bear,
            buy_below_price (= bear case), wacc_used.
        All prices are per share in the same currency as FCF inputs.
        Values are None if calculation is not possible.
    """
    if not free_cash_flows or shares_outstanding <= 0:
        return {
            "target_price_base": None,
            "target_price_bull": None,
            "target_price_bear": None,
            "buy_below_price": None,
            "wacc_used": None,
        }

    wacc = round(risk_free_rate + beta * equity_risk_premium, 4)
    # Ensure WACC > terminal growth rate
    if wacc <= terminal_growth_rate:
        wacc = terminal_growth_rate + 0.02

    def _dcf_value(fcfs: list[float], discount_rate: float) -> float | None:
        try:
            pv_fcfs = sum(
                fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(fcfs)
            )
            terminal_fcf = fcfs[-1] * (1 + terminal_growth_rate)
            terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
            pv_terminal = terminal_value / (1 + discount_rate) ** len(fcfs)
            total_ev = pv_fcfs + pv_terminal
            return round(total_ev / shares_outstanding, 2)
        except (ZeroDivisionError, OverflowError):
            return None

    # Derive growth rate from the FCF projection slope
    if len(free_cash_flows) >= 2 and free_cash_flows[0] > 0:
        implied_growth = (free_cash_flows[-1] / free_cash_flows[0]) ** (
            1 / max(len(free_cash_flows) - 1, 1)
        ) - 1
    else:
        implied_growth = 0.05

    def _scale_fcfs(growth_delta: float) -> list[float]:
        """Re-project FCFs at base_growth + growth_delta."""
        base = free_cash_flows[0] / (1 + implied_growth) if implied_growth != -1 else free_cash_flows[0]
        new_growth = max(-0.10, min(implied_growth + growth_delta, 0.30))
        return [base * (1 + new_growth) ** i for i in range(1, len(free_cash_flows) + 1)]

    base_price = _dcf_value(free_cash_flows, wacc)
    bull_price = _dcf_value(_scale_fcfs(bull_growth_boost), wacc * 0.95)  # slightly lower WACC in bull
    bear_price = _dcf_value(_scale_fcfs(-bear_growth_haircut), wacc * 1.05)  # slightly higher WACC in bear

    return {
        "target_price_base": base_price,
        "target_price_bull": bull_price,
        "target_price_bear": bear_price,
        "buy_below_price": bear_price,  # only buy when price ≤ worst-case intrinsic value
        "wacc_used": round(wacc * 100, 2),  # as percentage
    }


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """Compute the Relative Strength Index (RSI) for a price series.

    Args:
        prices: List of closing prices in chronological order (oldest first).
        period: Look-back window (default 14 days).

    Returns:
        RSI value 0–100, or None if insufficient data.
        Above 70 = overbought; below 30 = oversold.
    """
    if len(prices) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    # Wilder's smoothed average over the first `period` changes
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_moving_averages(
    prices: list[float],
    windows: tuple[int, int] = (50, 200),
) -> dict[str, float | None]:
    """Compute simple moving averages and detect golden/death cross.

    Args:
        prices: Closing prices in chronological order (oldest first).
        windows: Tuple of (short_window, long_window) in days (default 50, 200).

    Returns:
        Dict with keys: ma_short, ma_long, cross_signal
        cross_signal: "golden_cross" | "death_cross" | "neutral"
    """
    short_w, long_w = windows
    ma_short: float | None = None
    ma_long: float | None = None

    if len(prices) >= short_w:
        ma_short = round(sum(prices[-short_w:]) / short_w, 4)
    if len(prices) >= long_w:
        ma_long = round(sum(prices[-long_w:]) / long_w, 4)

    cross_signal = "neutral"
    if ma_short is not None and ma_long is not None:
        if ma_short > ma_long:
            cross_signal = "golden_cross"
        elif ma_short < ma_long:
            cross_signal = "death_cross"

    return {
        f"ma_{short_w}": ma_short,
        f"ma_{long_w}": ma_long,
        "cross_signal": cross_signal,
    }


def calculate_52w_position(
    current_price: float,
    high_52w: float,
    low_52w: float,
) -> float | None:
    """Compute where the current price sits within its 52-week range.

    Returns a value from 0.0 (at the 52-week low) to 1.0 (at the 52-week high).
    Values below 0.3 suggest the stock is near its lows (potential entry zone).

    Args:
        current_price: Latest closing price.
        high_52w: 52-week high price.
        low_52w: 52-week low price.

    Returns:
        Position ratio 0.0–1.0, or None if range is zero.
    """
    if high_52w is None or low_52w is None or current_price is None:
        return None
    price_range = high_52w - low_52w
    if price_range <= 0:
        return None
    return round((current_price - low_52w) / price_range, 4)


def calculate_volume_trend(
    volumes: list[float],
    recent_days: int = 20,
    baseline_days: int = 90,
) -> dict[str, float | None]:
    """Compare recent average volume to a longer-term baseline.

    Args:
        volumes: Daily volume figures in chronological order (oldest first).
        recent_days: Window for the recent average (default 20 days).
        baseline_days: Window for the baseline average (default 90 days).

    Returns:
        Dict with keys: avg_volume_recent, avg_volume_baseline, volume_ratio
        volume_ratio > 1.0 means recent volume is above baseline (increased interest).
    """
    if len(volumes) < recent_days:
        return {"avg_volume_recent": None, "avg_volume_baseline": None, "volume_ratio": None}

    avg_recent = sum(volumes[-recent_days:]) / recent_days
    baseline_slice = volumes[-min(baseline_days, len(volumes)):]
    avg_baseline = sum(baseline_slice) / len(baseline_slice)

    ratio: float | None = None
    if avg_baseline > 0:
        ratio = round(avg_recent / avg_baseline, 4)

    return {
        "avg_volume_recent": round(avg_recent),
        "avg_volume_baseline": round(avg_baseline),
        "volume_ratio": ratio,
    }


def calculate_cash_flow_quality(net_income: float, operating_cash_flow: float) -> dict[str, Any]:
    """Assess earnings quality by comparing net income to operating cash flow.

    A high-quality earnings stream has operating cash flow ≥ net income.
    When OCF < net income, the company may be using aggressive accounting.

    Args:
        net_income: Trailing twelve-month net income (millions).
        operating_cash_flow: Trailing twelve-month operating cash flow (millions).

    Returns:
        Dict with keys:
            ratio (OCF / Net Income), quality ("high" | "medium" | "low" | "negative_earnings"),
            note (plain-English interpretation).
    """
    if net_income is None or operating_cash_flow is None:
        return {"ratio": None, "quality": "unknown", "note": "Insufficient data"}

    if net_income <= 0:
        return {
            "ratio": None,
            "quality": "negative_earnings",
            "note": "Net income is negative; OCF quality check not applicable",
        }

    ratio = round(operating_cash_flow / net_income, 2)

    if ratio >= 1.2:
        quality = "high"
        note = f"OCF is {ratio}x net income — strong cash conversion, high earnings quality"
    elif ratio >= 0.8:
        quality = "medium"
        note = f"OCF is {ratio}x net income — reasonable cash conversion"
    elif ratio >= 0.5:
        quality = "low"
        note = f"OCF is only {ratio}x net income — possible aggressive revenue recognition or working capital build"
    else:
        quality = "low"
        note = f"OCF is {ratio}x net income — significant divergence; review accruals and working capital"

    return {"ratio": ratio, "quality": quality, "note": note}
