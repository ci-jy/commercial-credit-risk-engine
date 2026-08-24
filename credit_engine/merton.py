"""Merton (1974) structural model: distance-to-default from equity market data.

Equity is a call option on the firm's assets V with strike equal to the
default point D at horizon T:

    E       = V N(d1) - D exp(-rT) N(d2)
    sigma_E = N(d1) V sigma_V / E
    d1 = [ln(V/D) + (r + sigma_V^2 / 2) T] / (sigma_V sqrt(T)),  d2 = d1 - sigma_V sqrt(T)

Given observed E and sigma_E, the two equations are solved jointly for V and
sigma_V. Distance-to-default is d2 (with drift r), and the implied PD is N(-d2).
The default point follows the KMV convention: short-term debt plus half of
long-term debt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import root
from scipy.stats import norm


def equity_value(V: float, sigma_V: float, D: float, r: float, T: float) -> tuple[float, float]:
    """Return (E, sigma_E) implied by asset value and volatility."""
    sq = sigma_V * math.sqrt(T)
    d1 = (math.log(V / D) + (r + 0.5 * sigma_V**2) * T) / sq
    d2 = d1 - sq
    E = V * norm.cdf(d1) - D * math.exp(-r * T) * norm.cdf(d2)
    sigma_E = norm.cdf(d1) * V * sigma_V / E
    return E, sigma_E


@dataclass
class MertonResult:
    asset_value: float
    asset_vol: float
    distance_to_default: float
    pd: float
    converged: bool


def solve_merton(E: float, sigma_E: float, D: float, r: float = 0.04, T: float = 1.0) -> MertonResult:
    if E <= 0 or sigma_E <= 0 or D <= 0:
        raise ValueError("equity value, equity volatility and default point must be positive")

    # Solve in log-space so V and sigma_V stay positive; residuals are relative.
    def residuals(x):
        V, sV = math.exp(x[0]), math.exp(x[1])
        e, se = equity_value(V, sV, D, r, T)
        return [e / E - 1.0, se / sigma_E - 1.0]

    V0 = E + D * math.exp(-r * T)
    x0 = [math.log(V0), math.log(max(sigma_E * E / V0, 1e-4))]
    sol = root(residuals, x0, method="hybr", options={"xtol": 1e-14})
    if not sol.success or np.max(np.abs(sol.fun)) > 1e-9:
        sol = root(residuals, x0, method="lm", options={"xtol": 1e-14, "ftol": 1e-14})
    V, sV = math.exp(sol.x[0]), math.exp(sol.x[1])
    dd = (math.log(V / D) + (r - 0.5 * sV**2) * T) / (sV * math.sqrt(T))
    ok = bool(np.max(np.abs(residuals(sol.x))) < 1e-8)
    return MertonResult(V, sV, dd, float(norm.cdf(-dd)), ok)


def default_point(short_term_debt: float, long_term_debt: float) -> float:
    return short_term_debt + 0.5 * long_term_debt


def equity_volatility(prices: np.ndarray, window: int = 252) -> float:
    """Annualized volatility of daily log returns over the last ``window`` days."""
    p = np.asarray(prices, dtype=float)[-(window + 1):]
    rets = np.diff(np.log(p))
    return float(np.std(rets, ddof=1) * math.sqrt(252))
