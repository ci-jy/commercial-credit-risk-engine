"""DQC_0004 - Element Values Are Equal.

Rule text (XBRL US DQC): "This rule tests that the values reported between
element relationships that are identified as an accounting constant are
consistent within the filing. For example Assets equals Liability and Equity."
Values are compared at the lowest decimals of the facts involved and fire when
``|round(L, d) - round(R, d)| > 2 * 10**-d``. The rule runs in every context
(period, unit and dimension set) where the base concept is reported and, as the
rule text says, "checks that the components of the calculation are present
before checking the calculation".

Implemented element IDs: 16 (Assets = LiabilitiesAndStockholdersEquity),
9280-9284 and 9286-9291. 9285 is omitted: its alternative branch depends on
the calculation linkbase, which the data sets do not carry.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_engine.dqc.base import empty, exceeds_tolerance, fmt, make_findings, pivot_concepts
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0004"
TITLE = "Element values are equal (e.g. assets = liabilities + equity)"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K", "DEF 14A", "PRE 14A"}

# element id -> (base, components, tolerance function kind)
CHECKS = {
    "16": ("Assets", ["LiabilitiesAndStockholdersEquity"], "plain"),
    "9280": ("Assets", ["AssetsCurrent", "AssetsNoncurrent"], "comp"),
    "9281": ("Liabilities", ["LiabilitiesCurrent", "LiabilitiesNoncurrent"], "comp"),
    "9282": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
             ["StockholdersEquity", "MinorityInterest"], "comp"),
    "9284": ("ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest",
             ["ProfitLoss", "OtherComprehensiveIncomeLossNetOfTax"], "comp"),
    "9286": ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect",
             ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInInvestingActivities",
              "NetCashProvidedByUsedInFinancingActivities"], "comp"),
    "9287": ("NetCashProvidedByUsedInFinancingActivities",
             ["NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
              "CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations"], "plain"),
    "9288": ("NetCashProvidedByUsedInInvestingActivities",
             ["NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
              "CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations"], "plain"),
    "9289": ("NetCashProvidedByUsedInOperatingActivities",
             ["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
              "CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations"], "plain"),
    "9290": ("NetCashProvidedByUsedInDiscontinuedOperations",
             ["CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations",
              "CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations",
              "CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations"], "plain"),
    "9291": ("NetCashProvidedByUsedInContinuingOperations",
             ["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
              "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
              "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"], "plain"),
}
LSE_COMPONENTS = ["LiabilitiesAndStockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                  "StockholdersEquity", "MinorityInterest", "Liabilities", "LiabilitiesCurrent", "LiabilitiesNoncurrent",
                  "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests"]


def _sum(w: pd.DataFrame, cols: list[str]) -> pd.Series:
    """XULE ``<+>``: missing operands count as zero; all missing gives NaN."""
    return w[cols].sum(axis=1, min_count=1)


def _mindec(w: pd.DataFrame, cols: list[str]) -> pd.Series:
    return w[[f"{c}__dec" for c in cols]].min(axis=1)


def _emit(w, mask, base, expected, eid, label) -> pd.DataFrame:
    rows = w[mask].copy()
    if rows.empty:
        return empty()
    rows["tag"] = base
    rows["value"] = rows[base]
    rows["segments"] = rows.segments.mask(rows.segments == "")
    exp = expected[mask].to_numpy()
    msgs = [f"{base} with a value of {fmt(v)} is not equal to {label} with a value of {fmt(e)}. "
            f"These values should be equal." for v, e in zip(rows.value, exp)]
    return make_findings(rows, RULE_ID, eid, msgs, suggested=exp)


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    concepts = sorted({c for b, comps, _ in CHECKS.values() for c in [b, *comps]} | set(LSE_COMPONENTS))
    w = pivot_concepts(num, concepts)
    if w.empty:
        return empty()
    out = []
    for eid, (base, comps, kind) in CHECKS.items():
        ww = w
        if eid == "9282":
            ww = w[~w.segments.str.contains("ConsolidationItems=", regex=False)]
        calc = _sum(ww, comps)
        has = ww[base].notna() & ww[comps].notna().all(axis=1)
        dec = ww[f"{base}__dec"] if kind == "plain" else _mindec(ww, [base, *comps])
        if kind == "plain":
            dec = np.fmin(ww[f"{base}__dec"], _mindec(ww, comps))
        dec = dec.fillna(0)
        bad = has & exceeds_tolerance(ww[base].fillna(0), calc.fillna(0), dec, 2.0)
        label = "the total of " + " + ".join(comps)
        out.append(_emit(ww, bad, base, calc, eid, label))
    # 9283: LiabilitiesAndStockholdersEquity = equity + liabilities + temporary equity
    # equity: the NCI-inclusive total, else parent equity (+ NCI when reported);
    # liabilities: the total, else current + noncurrent when both are reported
    equity = w["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"].fillna(
        w["StockholdersEquity"] + w["MinorityInterest"].fillna(0))
    liabs = w["Liabilities"].fillna(w["LiabilitiesCurrent"] + w["LiabilitiesNoncurrent"])
    temp = w["TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests"]
    calc = equity + liabs + temp
    # XULE binds every factset in the assertion, so the check only runs where
    # temporary equity is reported too (as Arelle's output confirms).
    has = w["LiabilitiesAndStockholdersEquity"].notna() & equity.notna() & liabs.notna() & temp.notna()
    dec = _mindec(w, LSE_COMPONENTS[:7]).fillna(0)
    bad = has & exceeds_tolerance(w["LiabilitiesAndStockholdersEquity"].fillna(0), calc.fillna(0), dec, 2.0)
    out.append(_emit(w, bad, "LiabilitiesAndStockholdersEquity", calc, "9283",
                     "the total of equity, liabilities and temporary equity"))
    out = [o for o in out if len(o)]
    return pd.concat(out, ignore_index=True) if out else empty()
