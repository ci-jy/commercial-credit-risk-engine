"""DQC_0095 - Scale - Common Stock Outstanding.

Rule text (XBRL US DQC): "This rule tests that the value of
EntityCommonStockSharesOutstanding is consistent in scale with the value of
CommonStockSharesOutstanding" - a ratio above 99 or below 0.099 usually means
one of them was scaled wrongly (e.g. shares tagged in thousands). The two
facts must share dimensions, and the balance-sheet date must be less than 90
days before the cover-page date. Filings with more than one subsequent-event
share fact or more than one stock-split fact are skipped.

Suggested correction: the cover-page value rescaled by the nearest power of
1,000 to the balance-sheet value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._forms import PERIODIC, applicable

RULE_ID = "DQC_0095"
TITLE = "Scale of cover-page shares outstanding vs balance-sheet shares"
FORMS = PERIODIC | {"11-K", "11-K/A"}
SPLITS = ["StockIssuedDuringPeriodSharesStockSplits", "StockIssuedDuringPeriodSharesReverseStockSplits",
          "StockholdersEquityNoteStockSplitConversionRatio1"]


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    seg = num.segments.astype(object).fillna("")
    sub_ev = num[(num.uom.astype(str) == "shares") & seg.str.contains("SubsequentEventType=SubsequentEvent;", regex=False)]
    splits = num[num.tag.isin(SPLITS)]
    skip = set(sub_ev.adsh.astype(str).value_counts().loc[lambda s: s > 1].index) \
        | set(splits.adsh.astype(str).value_counts().loc[lambda s: s > 1].index)
    e = num[(num.tag == "EntityCommonStockSharesOutstanding") & (num.value > 0)].copy()
    c = num[(num.tag == "CommonStockSharesOutstanding") & (num.value > 0) & ~num.custom].copy()
    if e.empty or c.empty:
        return empty()
    for df in (e, c):
        df["seg_k"] = df.segments.astype(object).where(df.segments.notna(), "")
        df["adsh_k"] = df.adsh.astype(str)
    m = e.merge(c[["adsh_k", "seg_k", "value", "end"]], on=["adsh_k", "seg_k"], suffixes=("", "_c"))
    m = m[~m.adsh_k.isin(skip) & (pd.to_datetime(m.end_c) + pd.Timedelta(days=90) > pd.to_datetime(m.end))]
    m["factor"] = m.value / m.value_c
    m = m[(m.factor > 99) | (m.factor < 0.099)].drop_duplicates(["adsh_k", "seg_k", "ddate", "value"])
    if m.empty:
        return empty()
    power = np.round(np.log10(m.factor.to_numpy()) / 3) * 3
    return make_findings(
        m, RULE_ID, "9528",
        lambda r: [f"EntityCommonStockSharesOutstanding of {fmt(v)} is {f:,.4g} times CommonStockSharesOutstanding "
                   f"of {fmt(cv)}; one of the values is probably scaled incorrectly."
                   for v, cv, f in zip(r.value, r.value_c, r.factor)],
        suggested=m.value.to_numpy() / np.power(10.0, power))
