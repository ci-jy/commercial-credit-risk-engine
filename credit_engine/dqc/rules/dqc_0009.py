"""DQC_0009 - Element A must be less than or equal to Element B.

Rule text (XBRL US DQC): "This rule tests that the fact value for certain
elements are less than or equal to the fact value of other elements." A pair
fires when A and B are reported in the same context (period, unit and
dimensions), ``A > B`` and ``|round(A, d) - round(B, d)| > 10**-d``.

Element IDs 15 and 21 (shares outstanding/issued vs authorized) are skipped for
filings that report two or more different stock-split concepts.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, exceeds_tolerance, fmt, make_findings, pivot_concepts
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0009"
TITLE = "Element A must be <= element B (e.g. shares outstanding <= issued)"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K"}

PAIRS = {
    "15": ("CommonStockSharesOutstanding", "CommonStockSharesAuthorized"),
    "19": ("PreferredStockSharesOutstanding", "PreferredStockSharesIssued"),
    "21": ("CommonStockSharesIssued", "CommonStockSharesAuthorized"),
    "22": ("PreferredStockSharesIssued", "PreferredStockSharesAuthorized"),
    "23": ("PreferredStockSharesOutstanding", "PreferredStockSharesAuthorized"),
    "24": ("CommonStockSharesOutstanding", "CommonStockSharesIssued"),
    "47": ("DeferredTaxLiabilityNotRecognizedAmountOfUnrecognizedDeferredTaxLiabilityUndistributedEarningsOfForeignSubsidiaries",
           "UndistributedEarningsOfForeignSubsidiaries"),
    "40": ("DefinedBenefitPlanPensionPlansWithAccumulatedBenefitObligationsInExcessOfPlanAssetsAggregateAccumulatedBenefitObligation",
           "DefinedBenefitPlanAccumulatedBenefitObligation"),
    "41": ("DefinedBenefitPlanPensionPlansWithAccumulatedBenefitObligationsInExcessOfPlanAssetsAggregateFairValueOfPlanAssets",
           "DefinedBenefitPlanFairValueOfPlanAssets"),
    "42": ("DefinedBenefitPlanPensionPlansWithAccumulatedBenefitObligationsInExcessOfPlanAssetsAggregateProjectedBenefitObligation",
           "DefinedBenefitPlanBenefitObligation"),
    "45": ("DefinedBenefitPlanExpectedFutureEmployerContributionsRemainderOfFiscalYear",
           "DefinedBenefitPlanExpectedFutureEmployerContributionsCurrentFiscalYear"),
    "46": ("DefinedBenefitPlanAccumulatedBenefitObligation", "DefinedBenefitPlanBenefitObligation"),
}
SPLIT_CONCEPTS = ["StockIssuedDuringPeriodSharesStockSplits", "StockIssuedDuringPeriodSharesReverseStockSplits",
                  "StockholdersEquityNoteStockSplitConversionRatio1"]


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    concepts = sorted({c for pair in PAIRS.values() for c in pair})
    w = pivot_concepts(num, concepts)
    if w.empty:
        return empty()
    splits = num[num.tag.isin(SPLIT_CONCEPTS)].groupby("adsh", observed=True).tag.nunique()
    split_filers = set(splits[splits > 1].index.astype(str))
    out = []
    for eid, (a, b) in PAIRS.items():
        ww = w[~w.adsh.isin(split_filers)] if eid in ("15", "21") else w
        both = ww[a].notna() & ww[b].notna()
        dec = ww[[f"{a}__dec", f"{b}__dec"]].min(axis=1).fillna(0)
        bad = both & (ww[a] > ww[b]) & exceeds_tolerance(ww[a].fillna(0), ww[b].fillna(0), dec, 1.0)
        rows = ww[bad].copy()
        if rows.empty:
            continue
        rows["tag"], rows["value"] = a, rows[a]
        rows["segments"] = rows.segments.mask(rows.segments == "")
        msgs = [f"The value of {a}, {fmt(x)}, should be less than or equal to {b}, {fmt(y)}."
                for x, y in zip(rows[a], rows[b])]
        out.append(make_findings(rows, RULE_ID, eid, msgs, suggested=rows[b].to_numpy()))
    return pd.concat(out, ignore_index=True) if out else empty()
