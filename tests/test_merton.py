"""Merton solver round-trips synthetic firms to 1e-6."""

import math

import numpy as np
import pytest
from scipy.stats import norm

from credit_engine.merton import default_point, equity_value, equity_volatility, solve_merton

rng = np.random.default_rng(2024)
FIRMS = [(float(rng.uniform(50, 5000)), float(rng.uniform(0.05, 0.8)), float(rng.uniform(0.2, 1.1)),
          float(rng.uniform(0.0, 0.08)), float(rng.choice([0.5, 1.0, 2.0]))) for _ in range(40)]


@pytest.mark.parametrize("V,sigma_V,lev,r,T", FIRMS)
def test_round_trip(V, sigma_V, lev, r, T):
    D = lev * V
    E, sigma_E = equity_value(V, sigma_V, D, r, T)
    res = solve_merton(E, sigma_E, D, r, T)
    assert res.converged
    assert res.asset_value == pytest.approx(V, rel=1e-6)
    assert res.asset_vol == pytest.approx(sigma_V, rel=1e-6)
    dd = (math.log(V / D) + (r - 0.5 * sigma_V**2) * T) / (sigma_V * math.sqrt(T))
    assert res.distance_to_default == pytest.approx(dd, abs=1e-6)
    assert res.pd == pytest.approx(norm.cdf(-dd), abs=1e-6)


def test_textbook_example():
    # Hull, Options Futures and Other Derivatives: E=3, sigma_E=0.80, D=10, r=5%, T=1 -> V~12.40, sigma_V~0.2123
    res = solve_merton(3.0, 0.80, 10.0, 0.05, 1.0)
    assert res.asset_value == pytest.approx(12.40, abs=0.01)
    assert res.asset_vol == pytest.approx(0.2123, abs=0.001)


def test_helpers_and_input_validation():
    assert default_point(10, 100) == 60
    rng2 = np.random.default_rng(1)
    prices = 100 * np.exp(np.cumsum(rng2.normal(0, 0.02, 600)))
    assert equity_volatility(prices) == pytest.approx(0.02 * math.sqrt(252), rel=0.15)
    with pytest.raises(ValueError):
        solve_merton(-1, 0.3, 10)
