"""Financial calculation functions.

Pure functions — no side effects, no I/O. These are called by agents
to compute valuation metrics from raw financial data.

All dollar amounts are assumed to be in millions unless noted.
"""

from __future__ import annotations

import logging

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
