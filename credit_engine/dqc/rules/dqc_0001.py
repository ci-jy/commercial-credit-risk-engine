"""DQC_0001 - Axis with Inappropriate Members.

Rule text (XBRL US DQC): "Certain axes in the US GAAP taxonomy should only have
certain members as shown in the US GAAP taxonomy. This rule tests whether these
axes have inappropriate members." Two patterns are used:

* closed axes - only US GAAP members of the axis (plus a short list of named
  extension members) may be used: ConsolidationItems (70), SubsequentEventType
  (74), Range (61), FairValueByFairValueHierarchyLevel (51)
* open axes - extension members are fine, but a *US GAAP* member from another
  part of the taxonomy is not: StatementEquityComponents (75, e.g. a class of
  stock member used as an equity component), StatementBusinessSegments (81)

Allowed members per axis come from the US GAAP 2025 definition linkbases
(``resources/ugt_2025_axis_members.json``, built by ``scripts/build_ugt_members.py``).
One finding is reported per filing, axis and member. The data sets strip
namespaces, so a US GAAP member is recognised by its name alone.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from credit_engine.dqc.base import FINDING_COLS, empty
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0001"
TITLE = "Axis with inappropriate members"
FORMS = PERIODIC | REGISTRATION
RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "ugt_2025_axis_members.json"

# axis -> (element id, closed?, extra allowed member names)
AXES = {
    "ConsolidationItems": ("70", True, {
        "CorporateReconcilingItemsAndEliminations", "CorporateAndReconcilingItems", "CorporateAndEliminations",
        "EliminationsAndReconcilingItems", "OperatingSegmentsAndCorporateNonSegment",
        "OperatingSegmentsExcludingIntersegmentElimination", "OtherOperatingSegmentsAndIntersegmentEliminations",
        "OperatingSegmentsAfterReconcilingItemsAndEliminations"}),
    "SubsequentEventType": ("74", True, set()),
    "Range": ("61", True, set()),
    "FairValueByFairValueHierarchyLevel": ("51", True, {
        "FairValueInputsLevel1AndLevel2", "FairValueInputsLevel2AndLevel3", "FairValueInputsLevel1AndLevel3"}),
    "EquityComponents": ("75", False, {
        "TrustForBenefitOfEmployees",
        "AccumulatedNetGainLossFromCashFlowHedgesIncludingPortionAttributableToNoncontrollingInterest",
        "AccumulatedNetGainLossFromDesignatedOrQualifyingCashFlowHedges",
        "AccumulatedNetGainLossFromCashFlowHedgesAttributableToNoncontrollingInterest"}),
    "BusinessSegments": ("81", False, set()),
}


@lru_cache(maxsize=1)
def taxonomy() -> tuple[dict[str, set[str]], set[str]]:
    d = json.loads(RESOURCE.read_text())
    return {k: set(v) for k, v in d["axes"].items()}, set(d["base_members"])


def axis_members(num: pd.DataFrame) -> pd.DataFrame:
    """Distinct (filing, axis, member) triples, with the number of facts using each."""
    seg = num[num.segments.notna()][["adsh", "segments"]]
    counts = seg.groupby(["adsh", "segments"], observed=True).size().reset_index(name="n")
    rows = []
    for adsh, s, n in counts.itertuples(index=False):
        for part in str(s).strip(";").split(";"):
            if "=" in part:
                axis, member = part.split("=", 1)
                if axis in AXES:
                    rows.append((str(adsh), axis, member, n))
    df = pd.DataFrame(rows, columns=["adsh", "axis", "member", "n"])
    return df.groupby(["adsh", "axis", "member"], as_index=False).n.sum()


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    am = axis_members(num)
    if am.empty:
        return empty()
    ugt, base = taxonomy()
    bad = []
    for r in am.itertuples(index=False):
        eid, closed, extra = AXES[r.axis]
        allowed = ugt.get(r.axis, set()) | extra
        if r.member in allowed:
            continue
        if closed or r.member in base:
            bad.append(r)
    if not bad:
        return empty()
    b = pd.DataFrame(bad)
    return pd.DataFrame({
        "adsh": b.adsh, "rule": RULE_ID, "element_id": b.axis.map(lambda a: AXES[a][0]),
        "concept": b.axis + "=" + b.member, "ddate": 0, "qtrs": 0, "segments": "", "uom": "",
        "value": b.n.astype(float), "suggested": float("nan"),
        "message": [f"The axis {a}Axis uses the member {m}Member ({n} facts), which is not an appropriate member "
                    f"for this axis." + (" Only US GAAP members of the axis may be used." if AXES[a][1] else
                                         " This US GAAP member belongs to a different axis.")
                    for a, m, n in zip(b.axis, b.member, b.n)],
    })[FINDING_COLS]
