"""DQC_0194 - Negative Values for Members on the Statement of Equity Components Axis.

Rule text (XBRL US DQC): "The rule identifies elements that should not be
negative when reported with specific members of the StatementEquityComponentsAxis":
share counts, issuances, grants and repurchases with ``CommonStockMember``
(10621) or ``PreferredStockMember`` (10636), and NCI increases/decreases with a
noncontrolling-interest member (10637). A fact with only the equity axis is
always tested; with more dimensions the DQC_0015 exclusions apply, with the
class-of-stock axis added to and the equity axis removed from the axis list.

Suggested correction: the absolute value (the movement's direction is already
in the element name, e.g. "repurchased").
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._equity import (COMMON_NON_NEG, NCI_NON_NEG, PREFERRED_NON_NEG, equity_member,
                                             is_nci)
from credit_engine.dqc.rules._exclusions import EXCLUDED_AXES, excluded
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0194"
TITLE = "Negative equity movements on the equity components axis"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K"}
AXES = (EXCLUDED_AXES | {"ClassOfStock"}) - {"EquityComponents"}


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    neg = num[(num.value < 0) & ~num.custom & num.segments.notna()].copy()
    if neg.empty:
        return empty()
    neg["member"] = equity_member(neg.segments).to_numpy()
    tag = neg.tag.astype(str)
    eid = pd.Series("", index=neg.index)
    eid[(neg.member == "CommonStock") & tag.isin(COMMON_NON_NEG)] = "10621"
    eid[(neg.member == "PreferredStock") & tag.isin(PREFERRED_NON_NEG)] = "10636"
    eid[neg.member.map(is_nci) & tag.isin(NCI_NON_NEG)] = "10637"
    neg["eid"] = eid
    neg = neg[neg.eid != ""]
    if neg.empty:
        return empty()
    neg = neg[(neg.ndims == 1) | ~excluded(neg.segments, axes=AXES)]
    if neg.empty:
        return empty()
    return make_findings(
        neg, RULE_ID, lambda r: r.eid.to_numpy(),
        lambda r: [f"{t} is reported with a negative value of {fmt(v)} on the equity components member {m}. "
                   f"The value should not be negative." for t, v, m in zip(r.tag, r.value, r.member)],
        suggested=lambda r: r.value.abs().to_numpy())
