"""Ratio arithmetic and covenant headroom against hand-worked values for the sample borrower.

FY2024 inputs ($M): revenue 420, COGS 294, EBIT 42, D&A 12, interest 11, lease cost 6,
cash 15, CA 150, CL 100, STB 10, CPLTD 12, LTD 140, equity 130, CFO 38, capex 14, cash taxes 6.
"""

import math

import pytest

from credit_engine.edgar import load_borrowers, load_fixture
from credit_engine.ratios import compute_ratios, headroom, test_covenants as run_covenants
from credit_engine.spreading import spread_companyfacts

M = 1e6


@pytest.fixture(scope="module")
def fy2024():
    return spread_companyfacts(load_fixture("sample_borrower")).year(2024)


def test_hand_worked_ratios(fy2024):
    r = compute_ratios(fy2024)
    assert r["ebitda"] / M == pytest.approx(54.0)            # 42 + 12
    assert r["total_debt"] / M == pytest.approx(162.0)       # 10 + 12 + 140
    assert r["net_debt"] / M == pytest.approx(147.0)         # 162 - 15
    assert r["debt_to_ebitda"] == pytest.approx(3.0)         # 162 / 54
    assert r["net_leverage"] == pytest.approx(147 / 54)      # 2.7222
    assert r["interest_coverage"] == pytest.approx(42 / 11)  # 3.8182
    assert r["dscr"] == pytest.approx(54 / 23)               # 54 / (11 + 12)
    assert r["fccr"] == pytest.approx(40 / 29)               # (54 + 6 - 14 - 6) / (11 + 6 + 12)
    assert r["current_ratio"] == pytest.approx(1.5)
    assert r["free_cash_flow"] / M == pytest.approx(24.0)    # 38 - 14
    assert r["ebitda_margin"] == pytest.approx(54 / 420)
    assert r["debt_to_equity"] == pytest.approx(162 / 130)


def test_covenant_headroom(fy2024):
    cov = load_borrowers()["sample_borrower"]["covenants"]
    res = {c.metric: c for c in run_covenants(compute_ratios(fy2024), cov)}
    assert res["debt_to_ebitda"].headroom == pytest.approx((3.5 - 3.0) / 3.5)
    assert res["interest_coverage"].headroom == pytest.approx((42 / 11 - 3) / 3)
    assert res["fccr"].headroom == pytest.approx((40 / 29 - 1.25) / 1.25)
    assert res["current_ratio"].headroom == pytest.approx(0.25)
    assert all(c.passed for c in res.values())


def test_negative_ebitda_and_impairment_addback(fy2024):
    y = dict(fy2024, operating_income=-20 * M)
    r = compute_ratios(y)
    assert math.isinf(r["debt_to_ebitda"]) and math.isinf(r["net_leverage"])
    assert headroom(r["debt_to_ebitda"], "<=", 3.5) == -math.inf
    y = dict(fy2024, operating_income=2 * M, impairments=40 * M)
    r = compute_ratios(y)
    assert r["ebitda"] / M == pytest.approx(54.0)
    assert r["interest_coverage"] == pytest.approx(42 / 11)


def test_headroom_sign_conventions():
    assert headroom(4.0, "<=", 3.5) < 0
    assert headroom(2.0, ">=", 3.0) == pytest.approx(-1 / 3)
    with pytest.raises(ValueError):
        headroom(1.0, "<", 1.0)
