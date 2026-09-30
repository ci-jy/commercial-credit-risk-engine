"""DQC_0091 - Invalid Value for Percentage Items.

Rule text (XBRL US DQC): "This rule tests that percentage items in the base
taxonomy do not have a value greater than 10 (1,000%)" - percentages must be
tagged as decimals (25% = 0.25), so a value like 25 is almost always a scale
error. Extension concepts, dei, ``InvestmentOwnedPercentOfNetAssets`` and
effective-tax-rate items (except the federal statutory rate) are not tested.
The data type comes from the data set's ``tag`` table (``datatype = percent``).

Suggested correction: the value divided by 100.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0091"
TITLE = "Percentage items greater than 1,000% (value > 10)"
FORMS = PERIODIC | REGISTRATION | {"11-K", "11-K/A"}
STATUTORY = "EffectiveIncomeTaxRateReconciliationAtFederalStatutoryIncomeTaxRate"


def check(q) -> pd.DataFrame:
    if q.tag is None:
        return empty()
    num = applicable(q.num, FORMS)
    pct = q.tag[(q.tag.datatype == "percent") & (q.tag.custom == "0")]
    pct_keys = set(zip(pct.tag, pct.version))
    big = num[(num.value > 10) & ~num.custom & ~num.version.astype(str).str.startswith("dei/")]
    if big.empty:
        return empty()
    big = big[[k in pct_keys for k in zip(big.tag.astype(str), big.version.astype(str))]]
    tag = big.tag.astype(str)
    big = big[(~tag.str.contains("EffectiveIncomeTaxRate") | (tag == STATUTORY))
              & (tag != "InvestmentOwnedPercentOfNetAssets")]
    if big.empty:
        return empty()
    return make_findings(
        big, RULE_ID, "9376",
        lambda r: [f"The percentage concept {t} has a value of {fmt(v)} ({v * 100:,.0f}%). Percentages should be "
                   f"reported as decimals, e.g. 0.25 for 25%." for t, v in zip(r.tag, r.value)],
        suggested=lambda r: (r.value / 100).to_numpy())
