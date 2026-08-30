"""Credit ratios and covenant tests on one fiscal year of a standardized spread.

Definitions (all on annual figures):

* EBITDA            = operating income + depreciation & amortization
                      + non-cash impairment charges (a standard covenant add-back)
* Total debt        = short-term borrowings + current portion of LTD + long-term debt
* Debt / EBITDA     = total debt / EBITDA
* Net leverage      = (total debt - cash) / EBITDA
* Interest coverage = EBIT (with the same impairment add-back) / interest expense
* DSCR              = EBITDA / (interest + current portion of LTD)
* FCCR              = (EBITDA + lease cost - capex - cash taxes)
                      / (interest + lease cost + current portion of LTD)
* Current ratio     = current assets / current liabilities
* Free cash flow    = cash from operations - capex

Leverage ratios are reported as infinite when EBITDA is zero or negative, and
coverage ratios as infinite when the denominator is zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RATIO_LABELS = {
    "ebitda": "EBITDA",
    "total_debt": "Total debt",
    "net_debt": "Net debt",
    "ebitda_margin": "EBITDA margin",
    "debt_to_ebitda": "Debt / EBITDA (x)",
    "net_leverage": "Net debt / EBITDA (x)",
    "interest_coverage": "EBIT / interest (x)",
    "dscr": "DSCR (x)",
    "fccr": "Fixed-charge coverage (x)",
    "current_ratio": "Current ratio (x)",
    "free_cash_flow": "Free cash flow",
    "debt_to_equity": "Debt / equity (x)",
}
AMOUNT_RATIOS = {"ebitda", "total_debt", "net_debt", "free_cash_flow"}

DEFAULT_COVENANTS = [
    {"name": "Max total leverage", "metric": "debt_to_ebitda", "op": "<=", "threshold": 3.5},
    {"name": "Min interest coverage", "metric": "interest_coverage", "op": ">=", "threshold": 3.0},
    {"name": "Min fixed-charge coverage", "metric": "fccr", "op": ">=", "threshold": 1.25},
    {"name": "Min current ratio", "metric": "current_ratio", "op": ">=", "threshold": 1.0},
]


def _leverage(num: float, ebitda: float) -> float:
    return num / ebitda if ebitda > 0 else math.inf


def _coverage(num: float, den: float) -> float:
    if den == 0:
        return math.inf if num >= 0 else -math.inf
    return num / den


def compute_ratios(y: dict[str, float]) -> dict[str, float]:
    ebitda = y["operating_income"] + y["depreciation_amortization"] + y.get("impairments", 0.0)
    total_debt = y["short_term_borrowings"] + y["current_portion_ltd"] + y["long_term_debt"]
    net_debt = total_debt - y["cash"]
    interest, cpltd, lease = y["interest_expense"], y["current_portion_ltd"], y["operating_lease_cost"]
    return {
        "ebitda": ebitda,
        "total_debt": total_debt,
        "net_debt": net_debt,
        "ebitda_margin": ebitda / y["revenue"] if y["revenue"] else math.nan,
        "debt_to_ebitda": _leverage(total_debt, ebitda),
        "net_leverage": _leverage(net_debt, ebitda),
        "interest_coverage": _coverage(y["operating_income"] + y.get("impairments", 0.0), interest),
        "dscr": _coverage(ebitda, interest + cpltd),
        "fccr": _coverage(ebitda + lease - y["capex"] - y["cash_taxes"], interest + lease + cpltd),
        "current_ratio": _coverage(y["current_assets"], y["current_liabilities"]),
        "free_cash_flow": y["cfo"] - y["capex"],
        "debt_to_equity": _coverage(total_debt, y["total_equity"]) if y["total_equity"] > 0 else math.inf,
    }


@dataclass
class CovenantResult:
    name: str
    metric: str
    op: str
    threshold: float
    value: float
    headroom: float  # fraction of threshold; negative = breached
    passed: bool


def headroom(value: float, op: str, threshold: float) -> float:
    """Distance to the covenant as a fraction of the threshold (negative when breached)."""
    if op == "<=":
        if math.isinf(value):
            return -math.inf
        return (threshold - value) / threshold
    if op == ">=":
        if math.isinf(value):
            return math.inf if value > 0 else -math.inf
        return (value - threshold) / threshold
    raise ValueError(f"unknown covenant operator {op!r}")


def test_covenants(ratios: dict[str, float], covenants: list[dict] | None = None) -> list[CovenantResult]:
    out = []
    for c in covenants or DEFAULT_COVENANTS:
        v = ratios[c["metric"]]
        h = headroom(v, c["op"], c["threshold"])
        out.append(CovenantResult(c["name"], c["metric"], c["op"], c["threshold"], v, h, h >= 0))
    return out


test_covenants.__test__ = False  # not a pytest test
