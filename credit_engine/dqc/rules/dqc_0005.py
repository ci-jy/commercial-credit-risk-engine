"""DQC_0005 - Context Dates After Period End Date.

Rule text (XBRL US DQC): "This rule tests that the use of dates associated with
subsequent events, forecasts and the element Entity Common Stock, Shares
Outstanding are appropriate." Compared with the document period end date:

* 17 - ``dei:EntityCommonStockSharesOutstanding`` must not be dated *before* it
* 48 - facts on ``SubsequentEventTypeAxis`` must be dated *after* it
* 49 - facts with ``StatementScenarioAxis = ScenarioForecastMember`` must be dated *after* it

The data sets round both the fact dates and the balance-sheet date (``sub.period``)
to the nearest month end, so a subsequent event dated a few days after the
period end (common: a financing closed in the first week of the next month)
rounds onto the period end and is indistinguishable from one dated exactly on
it. To avoid flagging those valid facts, 48 and 49 only fire when the rounded
date is *earlier* than the period end; facts dated exactly on the period end
(an error under the rule) are missed.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, make_findings
from credit_engine.dqc.rules._forms import PERIODIC, applicable

RULE_ID = "DQC_0005"
TITLE = "Context dates after period end (cover shares, subsequent events, forecasts)"
FORMS = PERIODIC | {"8-K", "8-K/A", "6-K", "11-K", "11-K/A"}


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    num = num[num.doc_period.notna()]
    seg = num.segments.astype(object).fillna("")
    period = num.doc_period.dt.strftime("%Y%m%d").astype(int)
    out = []
    shares = num[(num.tag == "EntityCommonStockSharesOutstanding") & (num.ddate < period)]
    if len(shares):
        out.append(make_findings(shares, RULE_ID, "17", lambda r: [
            f"EntityCommonStockSharesOutstanding is dated {d} but should be on or after the period end date "
            f"{p:%Y-%m-%d}." for d, p in zip(r.ddate, r.doc_period)]))
    subseq = num[seg.str.contains("SubsequentEventType=", regex=False) & (num.ddate < period)]
    if len(subseq):
        out.append(make_findings(subseq, RULE_ID, "48", lambda r: [
            f"{t} is reported with SubsequentEventTypeAxis for a period ending {d}, before the period end date "
            f"{p:%Y-%m-%d}." for t, d, p in zip(r.tag, r.ddate, r.doc_period)]))
    forecast = num[seg.str.contains("Scenario=ScenarioForecast;", regex=False) & (num.ddate < period)]
    if len(forecast):
        out.append(make_findings(forecast, RULE_ID, "49", lambda r: [
            f"{t} is reported as a forecast for a period ending {d}, before the period end date {p:%Y-%m-%d}."
            for t, d, p in zip(r.tag, r.ddate, r.doc_period)]))
    out = [o for o in out if len(o)]
    return pd.concat(out, ignore_index=True) if out else empty()


