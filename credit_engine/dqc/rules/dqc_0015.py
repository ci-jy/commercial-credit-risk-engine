"""DQC_0015 - Negative Values.

Rule text (XBRL US DQC): "The rule identifies elements that should not be
negative. It does not check where elements are negative and where specified
members, axes and axis-member combinations allow the fact value to be negative."
The element list (about 6,400 us-gaap, srt and dei concepts, each with its own
rule element ID) is the official ``dqc_15_*_concepts.csv`` resource; the
dimensional exclusions are in :mod:`credit_engine.dqc.rules._exclusions`.

Suggested correction: the absolute value (the most common cause is a sign
entered for presentation, e.g. "(1,234)" tagged as negative).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._exclusions import excluded
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0015"
TITLE = "Negative values for elements that cannot be negative"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K", "DEF 14A", "PRE 14A", "486BPOS"}
RESOURCES = Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def non_negative_concepts() -> dict[str, str]:
    """concept local name -> rule element ID, from the us-gaap, srt and dei resource lists."""
    out: dict[str, str] = {}
    for name in ("dqc_15_usgaap_2025_concepts.csv", "dqc_15_srt_2025_concepts.csv", "dqc_15_dei_concepts.csv"):
        for line in (RESOURCES / name).read_text().splitlines():
            if "," in line:
                eid, concept = line.split(",", 1)
                out[concept.strip().split(":")[-1]] = eid.strip()
    return out


def check(q) -> pd.DataFrame:
    concepts = non_negative_concepts()
    num = applicable(q.num, FORMS)
    neg = num[(num.value < 0) & num.tag.isin(list(concepts)) & ~num.custom]
    if neg.empty:
        return empty()
    neg = neg[~excluded(neg.segments)]
    if neg.empty:
        return empty()
    return make_findings(
        neg, RULE_ID, lambda r: r.tag.astype(str).map(concepts).to_numpy(),
        lambda r: [f"The concept {t} with a value of {fmt(v)} is negative. This element should not have a "
                   f"negative value." for t, v in zip(r.tag, r.value)],
        suggested=lambda r: r.value.abs().to_numpy())
