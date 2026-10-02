"""DQC_0008 - Reversed Calculation.

Rule text (XBRL US DQC): "This rule identifies calculation relationships in
the company's extension taxonomy that are the opposite of a calculation defined
in the base US GAAP taxonomy" - e.g. a filer summing OperatingLeaseLiability
into OperatingLeaseLiabilityNoncurrent, when US GAAP sums the noncurrent part
into the total; this usually means a wrong tag. Element ID 6819
fires when the filing has parent P -> child C with weight w and US GAAP has
C -> P with the same weight.

Needs a calculation table (``Quarter.cal``, the ``cal.txt`` of the SEC
"Financial Statement and Notes" data sets); the quarterly data sets have none,
so on those the rule returns nothing. Base relationships are the US GAAP 2025
calculation linkbases (``resources/ugt_2025_axis_members.json``, key ``calc``).
One finding is reported per filing and reversed pair, with concept
``parent->child`` as filed.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from credit_engine.dqc.base import FINDING_COLS, empty
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION
from credit_engine.dqc.rules.dqc_0001 import RESOURCE

RULE_ID = "DQC_0008"
TITLE = "Reversed calculation relative to the US GAAP taxonomy"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K"}


@lru_cache(maxsize=1)
def base_calculations() -> set[tuple[str, str, float]]:
    return {(p, c, float(w)) for p, c, w in json.loads(RESOURCE.read_text())["calc"]}


def check(q) -> pd.DataFrame:
    cal = getattr(q, "cal", None)
    if cal is None or cal.empty:
        return empty()
    forms = q.sub.set_index("adsh").form
    c = cal[cal.adsh.map(forms).isin(FORMS)]
    c = c[c.pversion.str.startswith("us-gaap/") & c.cversion.str.startswith("us-gaap/") & (c.ptag != c.ctag)]
    base = base_calculations()
    weight = c.negative.astype(int).map({0: 1.0, 1: -1.0})
    rev = c[[(ct, pt, w) in base for pt, ct, w in zip(c.ptag, c.ctag, weight)]]
    rev = rev.drop_duplicates(["adsh", "ptag", "ctag"])
    if rev.empty:
        return empty()
    return pd.DataFrame({
        "adsh": rev.adsh.to_numpy(), "rule": RULE_ID, "element_id": "6819",
        "concept": (rev.ptag + "->" + rev.ctag).to_numpy(), "ddate": 0, "qtrs": 0, "segments": "", "uom": "",
        "value": float("nan"), "suggested": float("nan"),
        "message": [f"The calculation from {p} to {ch} is the opposite of the US GAAP calculation from {ch} to {p}. "
                    f"Check the calculation, or that the right elements are used." for p, ch in zip(rev.ptag, rev.ctag)],
    })[FINDING_COLS]
