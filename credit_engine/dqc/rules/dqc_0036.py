"""DQC_0036 - Document Period End Date Context / Fact Value Check (data-set approximation).

Rule text (XBRL US DQC): "This rule tests that the ending context date for the
Document Period End Date is not different by more than 3 days from the value
of that element." The usual cause is a filing rolled forward from the prior
period without updating ``dei:DocumentPeriodEndDate``.

The data sets do not carry the DocumentPeriodEndDate value or its context, so
this module checks the same consistency one step removed: the filing's period
of report (``sub.period``, the balance-sheet date) against the period the face
statements actually report. That is the latest instant used on the balance
sheet (``pre`` statement ``BS``) and the latest end of the filing's own flow
durations (4 quarters for a 10-K, 1 for a 10-Q). Element ID 1 fires when
neither matches ``sub.period``. Dates are compared after the data sets'
month-end rounding, so differences of a few days cannot be seen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_engine.dqc.base import FINDING_COLS, empty
from credit_engine.dqc.rules._forms import PERIODIC, applicable

RULE_ID = "DQC_0036"
TITLE = "Document period end date vs the period the statements report"


def check(q) -> pd.DataFrame:
    num = applicable(q.num, PERIODIC)
    num = num[num.dimensionless & num.doc_period.notna()]
    if num.empty or q.pre is None:
        return empty()
    bs = q.pre[q.pre.stmt.astype(str) == "BS"][["adsh", "tag"]].astype(str).drop_duplicates()
    keys = set(zip(bs.adsh, bs.tag))
    adsh, tag = num.adsh.astype(str), num.tag.astype(str)
    inst = num[(num.qtrs == 0).to_numpy() & np.array([k in keys for k in zip(adsh, tag)], dtype=bool)]
    want_q = num.form.str.startswith("10-K").map({True: 4, False: 1})
    flows = num[num.qtrs == want_q]
    latest_bs = inst.groupby(inst.adsh.astype(str)).ddate.max()
    latest_flow = flows.groupby(flows.adsh.astype(str)).ddate.max()
    period = num.groupby(num.adsh.astype(str)).doc_period.first().dt.strftime("%Y%m%d").astype(int)
    df = pd.DataFrame({"period": period, "bs": latest_bs, "flow": latest_flow}).dropna(subset=["period"])
    df = df[df.bs.notna() | df.flow.notna()]
    bad = df[(df.bs != df.period) & (df.flow != df.period)]
    if bad.empty:
        return empty()
    stmt_end = bad.bs.fillna(bad.flow).astype(int)
    return pd.DataFrame({
        "adsh": bad.index.to_numpy(), "rule": RULE_ID, "element_id": "1", "concept": "DocumentPeriodEndDate",
        "ddate": stmt_end.to_numpy(), "qtrs": 0, "segments": "", "uom": "", "value": bad.period.to_numpy(dtype=float),
        "suggested": stmt_end.to_numpy(dtype=float),
        "message": [f"The period of report {p} does not match the period the statements report ({s}). Check that "
                    f"DocumentPeriodEndDate was updated for this filing." for p, s in zip(bad.period, stmt_end)],
    })[FINDING_COLS]
