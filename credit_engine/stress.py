"""Covenant stress scenarios with root-finding for the breaking shock size.

Scenarios act on the latest fiscal year:

* ``ebitda_shock``    s in [0, 1]: EBITDA (and EBIT) fall by s x base EBITDA.
* ``rate_shock``      s in bp [0, 2000]: interest rises by floating debt x s / 10,000.
* ``revenue_decline`` s in [0, 1]: revenue falls by s; only cost of goods
  flexes, so EBITDA falls by s x revenue x gross margin.

Cash taxes, capex and the balance sheet are held at base values (a
conservative simplification: taxes would fall with earnings). For each
covenant the shock that drives headroom to exactly zero is bracketed on a
grid and refined with Brent's method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import brentq

from credit_engine.ratios import compute_ratios, headroom

SCENARIOS = {
    "ebitda_shock": {"label": "EBITDA decline", "max": 1.0, "unit": "%"},
    "rate_shock": {"label": "Rate shock on floating debt", "max": 2000.0, "unit": "bp"},
    "revenue_decline": {"label": "Revenue decline", "max": 1.0, "unit": "%"},
}


def apply_scenario(y: dict[str, float], scenario: str, s: float, floating_share: float) -> dict[str, float]:
    z = dict(y)
    base_ebitda = y["operating_income"] + y["depreciation_amortization"]
    if scenario == "ebitda_shock":
        z["operating_income"] = y["operating_income"] - s * base_ebitda
    elif scenario == "rate_shock":
        floating_debt = floating_share * (y["short_term_borrowings"] + y["current_portion_ltd"] + y["long_term_debt"])
        z["interest_expense"] = y["interest_expense"] + floating_debt * s / 10_000.0
    elif scenario == "revenue_decline":
        gross_margin = (y["revenue"] - y["cogs"]) / y["revenue"] if y["revenue"] else 0.0
        drop = s * y["revenue"]
        z["revenue"] = y["revenue"] - drop
        z["cogs"] = y["cogs"] - drop * (1 - gross_margin)
        z["operating_income"] = y["operating_income"] - drop * gross_margin
    else:
        raise ValueError(f"unknown scenario {scenario!r}")
    return z


@dataclass
class StressResult:
    scenario: str
    covenant: str
    breaking_shock: float | None  # None: not breached within the scenario range
    status: str  # "breached at base", "breaks at ...", "holds"


def _clip(h: float) -> float:
    if math.isinf(h):
        return 1e6 if h > 0 else -1e6
    return h


def find_breaking_shock(f: Callable[[float], float], s_max: float, grid: int = 400, xtol: float = 1e-10) -> float | None:
    """Smallest s in [0, s_max] where headroom f(s) crosses zero, or None."""
    xs = np.linspace(0.0, s_max, grid + 1)
    prev_x, prev_h = xs[0], _clip(f(xs[0]))
    if prev_h < 0:
        return 0.0
    for x in xs[1:]:
        h = _clip(f(x))
        if h < 0:
            if prev_h == 0:
                return float(prev_x)
            return float(brentq(lambda t: _clip(f(t)), prev_x, x, xtol=xtol))
        prev_x, prev_h = x, h
    return None


def run_stress(y: dict[str, float], covenants: list[dict], floating_share: float) -> list[StressResult]:
    results = []
    for scenario, meta in SCENARIOS.items():
        for c in covenants:
            def f(s, c=c, scenario=scenario):
                r = compute_ratios(apply_scenario(y, scenario, s, floating_share))
                return headroom(r[c["metric"]], c["op"], c["threshold"])

            shock = find_breaking_shock(f, meta["max"])
            if shock is None:
                status = f"holds to {format_shock(meta['max'], scenario)}"
            elif shock == 0.0:
                status = "breached at base"
            else:
                status = f"breaks at {format_shock(shock, scenario)}"
            results.append(StressResult(scenario, c["name"], shock, status))
    return results


def format_shock(s: float, scenario: str) -> str:
    if SCENARIOS[scenario]["unit"] == "bp":
        return f"+{s:,.0f} bp"
    return f"-{s * 100:.1f}%"
