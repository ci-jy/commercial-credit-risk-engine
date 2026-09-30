"""DQC_0125 - Lease Cost Cannot be Negative.

Rule text (XBRL US DQC): "The rule tests that the element LeaseCost is not
negative ... unless the filer has reported sublease income" (in which case net
lease cost can legitimately be negative). Annual forms only; dimensional facts
use the DQC_0015 exclusions.

Suggested correction: the absolute value.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._exclusions import excluded
from credit_engine.dqc.rules._forms import applicable

RULE_ID = "DQC_0125"
TITLE = "Lease cost cannot be negative (unless sublease income is reported)"
FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A", "11-K", "11-K/A"}


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    sublease = set(num[num.tag == "SubleaseIncome"].adsh.astype(str))
    neg = num[(num.tag == "LeaseCost") & (num.value < 0) & ~num.custom]
    neg = neg[~neg.adsh.astype(str).isin(sublease)]
    if neg.empty:
        return empty()
    neg = neg[~excluded(neg.segments)]
    if neg.empty:
        return empty()
    return make_findings(
        neg, RULE_ID, "9589",
        lambda r: [f"LeaseCost has a negative value of {fmt(v)} and no SubleaseIncome is reported. Lease cost "
                   f"should be positive." for v in r.value],
        suggested=lambda r: r.value.abs().to_numpy())
