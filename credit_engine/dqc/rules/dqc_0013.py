"""DQC_0013 - Negative Values With Dependence.

Rule text (XBRL US DQC): "The rule identifies elements that should not be
negative ... when income before taxes is positive" - effective tax-rate
reconciliation items such as tax credits, deductions and nondeductible
expenses. Income before tax is taken, in order, from
``IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest``,
then the ``...MinorityInterestAndIncomeLossFromEquityMethodInvestments`` total
plus equity-method income, then domestic + foreign + equity-method income.
Both facts must share period and dimensions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings, pivot_concepts
from credit_engine.dqc.rules._exclusions import excluded
from credit_engine.dqc.rules._forms import PERIODIC, applicable

RULE_ID = "DQC_0013"
TITLE = "Negative tax-rate reconciliation items when pre-tax income is positive"
FORMS = PERIODIC | {"11-K", "11-K/A"}

ITEMS = {
    "EffectiveIncomeTaxRateReconciliationTaxCredits": "2774",
    "EffectiveIncomeTaxRateReconciliationDeductionsOther": "2779",
    "EffectiveIncomeTaxRateReconciliationNondeductibleExpenseLifeInsurance": "2780",
    "EffectiveIncomeTaxRateReconciliationTaxCreditsOther": "2781",
    "EffectiveIncomeTaxRateReconciliationTaxCreditsInvestment": "2782",
    "EffectiveIncomeTaxRateReconciliationTaxCreditsForeign": "2783",
    "EffectiveIncomeTaxRateReconciliationDeductionsDividends": "2784",
    "EffectiveIncomeTaxRateReconciliationRepatriationOfForeignEarnings": "2785",
    "EffectiveIncomeTaxRateReconciliationTaxHolidays": "2871",
    "EffectiveIncomeTaxRateReconciliationNondeductibleExpenseResearchAndDevelopment": "2872",
    "EffectiveIncomeTaxRateReconciliationDeductions": "2873",
    "EffectiveIncomeTaxRateReconciliationNondeductibleExpenseImpairmentLosses": "2874",
    "EffectiveIncomeTaxRateReconciliationDeductionsEmployeeStockOwnershipPlanDividends": "3001",
    "EffectiveIncomeTaxRateReconciliationNondeductibleExpenseMealsAndEntertainment": "3002",
    "EffectiveIncomeTaxRateReconciliationDeductionsExtraterritorialIncomeExclusion": "3439",
    "EffectiveIncomeTaxRateReconciliationNondeductibleExpenseCharitableContributions": "3440",
    "EffectiveIncomeTaxRateReconciliationRepatriationForeignEarningsJobsCreationActOf2004": "3441",
    "EffectiveIncomeTaxRateReconciliationBeatPercent": "9789",
    "EffectiveIncomeTaxRateReconciliationFdiiPercent": "9791",
}
PRETAX = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
PRETAX_MI = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"
EQUITY_METHOD = "IncomeLossFromEquityMethodInvestments"
DOMESTIC = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"
FOREIGN = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign"


def income_before_tax(w: pd.DataFrame) -> pd.Series:
    em = w[EQUITY_METHOD].fillna(0)
    dom_for = w[[DOMESTIC, FOREIGN]].sum(axis=1, min_count=1)
    return w[PRETAX].fillna(w[PRETAX_MI] + em).fillna(dom_for + em)


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    pre_cols = [PRETAX, PRETAX_MI, EQUITY_METHOD, DOMESTIC, FOREIGN]
    keys = ["adsh", "ddate", "qtrs", "segments", "coreg"]
    pre = pivot_concepts(num[num.uom.astype(str) != "pure"], pre_cols, keys=tuple(keys))
    if pre.empty:
        return empty()
    pre["ibt"] = income_before_tax(pre)
    positive = pre[pre.ibt > 0][keys + ["ibt"]]
    items = num[num.tag.isin(list(ITEMS)) & (num.value < 0)].copy()
    if items.empty or positive.empty:
        return empty()
    items = items[~excluded(items.segments)]
    for c in ("segments", "coreg"):
        items[c + "_k"] = items[c].astype(object).where(items[c].notna(), "")
    m = items.merge(positive.rename(columns={"segments": "segments_k", "coreg": "coreg_k"}),
                    on=["adsh", "ddate", "qtrs", "segments_k", "coreg_k"], how="inner")
    if m.empty:
        return empty()
    m["segments"] = m.segments.astype(object)
    return make_findings(
        m, RULE_ID, lambda r: r.tag.astype(str).map(ITEMS).to_numpy(),
        lambda r: [f"{t} has a negative value of {fmt(v)} while income before taxes is positive ({fmt(i)}). "
                   f"The value should be positive." for t, v, i in zip(r.tag, r.value, r.ibt)],
        suggested=lambda r: np.abs(r.value.to_numpy()))
