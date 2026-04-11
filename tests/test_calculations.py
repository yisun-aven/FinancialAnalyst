"""Tests for tools/calculations.py — pure financial math, no I/O or API calls."""

import pytest

from tools.calculations import (
    calculate_dcf,
    calculate_ev_ebitda,
    calculate_pe_ratio,
    calculate_ratios,
)


class TestCalculatePERatio:
    def test_basic(self) -> None:
        assert calculate_pe_ratio(150.0, 10.0) == 15.0

    def test_zero_eps_returns_none(self) -> None:
        assert calculate_pe_ratio(150.0, 0.0) is None

    def test_negative_eps_returns_none(self) -> None:
        assert calculate_pe_ratio(150.0, -5.0) is None

    def test_rounds_to_two_decimals(self) -> None:
        result = calculate_pe_ratio(100.0, 3.0)
        assert result == 33.33


class TestCalculateEVEBITDA:
    def test_basic(self) -> None:
        # EV = 1000 + 200 - 100 = 1100; EV/EBITDA = 1100/100 = 11.0
        assert calculate_ev_ebitda(1000.0, 200.0, 100.0, 100.0) == 11.0

    def test_zero_ebitda_returns_none(self) -> None:
        assert calculate_ev_ebitda(1000.0, 200.0, 100.0, 0.0) is None

    def test_negative_ebitda_returns_none(self) -> None:
        assert calculate_ev_ebitda(1000.0, 200.0, 100.0, -50.0) is None


class TestCalculateDCF:
    def test_basic_intrinsic_value(self) -> None:
        fcfs = [100.0, 110.0, 121.0]
        result = calculate_dcf(
            free_cash_flows=fcfs,
            terminal_growth_rate=0.03,
            discount_rate=0.10,
            shares_outstanding=10.0,
        )
        assert result > 0

    def test_discount_rate_must_exceed_growth_rate(self) -> None:
        with pytest.raises(ValueError, match="discount_rate must be greater than"):
            calculate_dcf([100.0], terminal_growth_rate=0.10, discount_rate=0.05, shares_outstanding=10.0)


class TestCalculateRatios:
    def test_all_ratios_computed(self) -> None:
        result = calculate_ratios(
            net_income=50.0,
            shareholders_equity=250.0,
            total_debt=100.0,
            current_assets=200.0,
            current_liabilities=100.0,
            invested_capital=350.0,
            nopat=60.0,
        )
        assert result["roe"] == pytest.approx(0.2, rel=1e-3)
        assert result["debt_to_equity"] == pytest.approx(0.4, rel=1e-3)
        assert result["current_ratio"] == pytest.approx(2.0, rel=1e-3)
        assert result["roic"] == pytest.approx(60 / 350, rel=1e-3)

    def test_zero_equity_returns_none_for_equity_ratios(self) -> None:
        result = calculate_ratios(
            net_income=50.0,
            shareholders_equity=0.0,
            total_debt=100.0,
            current_assets=200.0,
            current_liabilities=100.0,
            invested_capital=350.0,
            nopat=60.0,
        )
        assert result["roe"] is None
        assert result["debt_to_equity"] is None
