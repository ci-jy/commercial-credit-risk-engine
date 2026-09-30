"""The shared "non-negative" exclusions of DQC_0015, also used by DQC_0013, 0125 and 0194.

A negative dimensional fact is allowed when any dimension matches:

1. a member whose name contains one of :data:`MEMBER_SUBSTRINGS` (case-insensitive)
2. a member in :data:`EXCLUDED_MEMBERS` on any axis
3. any member of an axis in :data:`EXCLUDED_AXES`
4. an (axis, member) pair in :data:`EXCLUDED_PAIRS`

Lists are from the 2025 ``dqcrules-0015`` taxonomy and the v30 XULE source, with
the data sets' naming (``Axis``/``Member`` suffixes removed).
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.fsds import parse_segments

MEMBER_SUBSTRINGS = ("adjust", "consolidat", "eliminat", "netting", "reconcili", "reclass", "basisswap", "unfunded")
EXCLUDED_MEMBERS = {
    "CorporateNonSegment", "FairValueConcentrationOfRiskMarketRiskManagementEffectsOnIncomeOrNetAssets",
    "AccumulatedNetGainLossFromDesignatedOrQualifyingCashFlowHedges", "AccumulatedNetUnrealizedInvestmentGainLoss",
    "DeferredDerivativeGainLoss", "AboveMarketLeases", "UnallocatedFinancingReceivables", "DischargeOfDebt",
    "ExchangeOfStockForStock", "EffectOfModifiedRetrospectiveApplicationAccountingStandardsUpdate201812",
}
EXCLUDED_AXES = {
    "EquityComponents", "ErrorCorrectionsAndPriorPeriodAdjustmentsRestatementByRestatementPeriodAndAmount",
    "AdjustmentsForChangeInAccountingPrinciple", "AdjustmentsForNewAccountingPronouncements", "PartnerCapitalComponents",
    "ChangeInAccountingEstimateByType", "PartnerTypeOfPartnersCapitalAccount", "BusinessSegments", "InvestmentIdentifier",
    "IncomeTaxEffectChangeInLaw",
}
EXCLUDED_PAIRS = {
    ("BusinessSegments", "CorporateAndOther"), ("BusinessSegments", "Corporate"), ("BusinessSegments", "AllOtherSegments"),
    ("ConsolidatedEntities", "ParentCompany"), ("ConsolidatedEntities", "Subsidiaries"),
    ("ConsolidatedEntities", "GuarantorSubsidiaries"), ("ConsolidatedEntities", "NonGuarantorSubsidiaries"),
    ("ConsolidatedEntities", "SubsidiaryIssuer"),
    ("FairValueByMeasurementBasis", "ChangeDuringPeriodFairValueDisclosure"),
}


def dims_excluded(dims: dict[str, str], axes: set[str] = EXCLUDED_AXES) -> bool:
    for axis, member in dims.items():
        low = member.lower()
        if any(s in low for s in MEMBER_SUBSTRINGS) or member in EXCLUDED_MEMBERS or axis in axes \
                or (axis, member) in EXCLUDED_PAIRS:
            return True
    return False


def excluded(segments: pd.Series, coreg: pd.Series | None = None, axes: set[str] = EXCLUDED_AXES) -> pd.Series:
    """True where a fact's dimensions allow a negative value (always False for dimensionless facts)."""
    seg = segments.astype(object)
    cache: dict[str, bool] = {}

    def one(s):
        if not isinstance(s, str) or not s:
            return False
        if s not in cache:
            cache[s] = dims_excluded(parse_segments(s), axes)
        return cache[s]

    return seg.map(one).astype(bool)
