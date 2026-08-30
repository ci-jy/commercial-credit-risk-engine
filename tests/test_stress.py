"""Covenant breaking points found by root-finding vs closed-form hand calculations."""

import pytest

from credit_engine.edgar import load_borrowers, load_fixture
from credit_engine.spreading import spread_companyfacts
from credit_engine.stress import apply_scenario, find_breaking_shock, run_stress


@pytest.fixture(scope="module")
def results():
    b = load_borrowers()["sample_borrower"]
    y = spread_companyfacts(load_fixture("sample_borrower")).year(2024)
    return {(r.scenario, r.covenant): r for r in run_stress(y, b["covenants"], b["floating_rate_share"])}


def test_ebitda_shock_breakpoints(results):
    # leverage: 162 / (54 (1 - s)) = 3.5  ->  s = 1 - 162 / (3.5 * 54) = 1/7
    assert results[("ebitda_shock", "Max total leverage")].breaking_shock == pytest.approx(1 / 7, abs=1e-9)
    # coverage: (42 - 54 s) / 11 = 3  ->  s = 9 / 54
    assert results[("ebitda_shock", "Min interest coverage")].breaking_shock == pytest.approx(9 / 54, abs=1e-9)
    # FCCR: (40 - 54 s) / 29 = 1.25  ->  s = 3.75 / 54
    assert results[("ebitda_shock", "Min fixed-charge coverage")].breaking_shock == pytest.approx(3.75 / 54, abs=1e-9)
    assert results[("ebitda_shock", "Min current ratio")].breaking_shock is None


def test_rate_shock_breakpoints(results):
    floating = 0.6 * 162  # $M
    # 42 / (11 + floating * bp / 1e4) = 3  ->  bp = 3 / floating * 1e4
    expected = 3 / floating * 1e4
    assert results[("rate_shock", "Min interest coverage")].breaking_shock == pytest.approx(expected, abs=1e-6)
    assert results[("rate_shock", "Min fixed-charge coverage")].breaking_shock == pytest.approx(expected, abs=1e-6)
    assert results[("rate_shock", "Max total leverage")].breaking_shock is None


def test_revenue_decline_breakpoints(results):
    # EBITDA falls by 420 * 0.30 * s; leverage breaks when 54 - 126 s = 162 / 3.5
    assert results[("revenue_decline", "Max total leverage")].breaking_shock == pytest.approx(
        (54 - 162 / 3.5) / 126, abs=1e-9)
    assert results[("revenue_decline", "Min fixed-charge coverage")].breaking_shock == pytest.approx(3.75 / 126, abs=1e-9)


def test_scenario_is_exact_at_breaking_point(results):
    y = spread_companyfacts(load_fixture("sample_borrower")).year(2024)
    s = results[("ebitda_shock", "Max total leverage")].breaking_shock
    z = apply_scenario(y, "ebitda_shock", s, 0.6)
    assert 162e6 / (z["operating_income"] + z["depreciation_amortization"]) == pytest.approx(3.5, rel=1e-9)


def test_root_finder_edge_cases():
    assert find_breaking_shock(lambda s: -1.0, 1.0) == 0.0
    assert find_breaking_shock(lambda s: 1.0, 1.0) is None
    assert find_breaking_shock(lambda s: 0.3 - s, 1.0) == pytest.approx(0.3, abs=1e-10)
