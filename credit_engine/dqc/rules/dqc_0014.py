"""DQC_0014 - Negative Values With No Dimensions.

Rule text (XBRL US DQC): "The rule identifies elements that should not be
negative when reported without dimensions" - for example Goodwill, revenue
from contracts with customers, cost of revenue, derivative assets and
liabilities. Facts with any dimension are not tested.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0014"
TITLE = "Negative values with no dimensions (goodwill, revenue, cost of revenue...)"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K", "DEF 14A", "PRE 14A"}

CONCEPTS = {
    "DerivativeFairValueOfDerivativeLiability": "2786", "DerivativeLiabilities": "2787",
    "FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetValue": "2788",
    "FairValueMeasurementWithUnobservableInputsReconciliationsRecurringBasisLiabilityValue": "2789",
    "LiabilitiesFairValueDisclosure": "2790", "AmortizationOfIntangibleAssets": "2791",
    "DerivativeFairValueOfDerivativeLiabilityAmountNotOffsetAgainstCollateral": "2792", "DerivativeAssets": "2793",
    "FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetTransfersOutOfLevel3": "2794",
    "DerivativeFairValueOfDerivativeAssetAmountOffsetAgainstCollateral": "2795",
    "DerivativeFairValueOfDerivativeLiabilityAmountOffsetAgainstCollateral": "2796",
    "DerivativeFairValueOfDerivativeAssetAmountNotOffsetAgainstCollateral": "2797",
    "DerivativeLiabilityFairValueGrossAsset": "2798", "FinancialInstrumentsOwnedAtFairValue": "2799",
    "DerivativeAssetFairValueGrossLiability": "2800", "CashDividendsPaidToParentCompany": "2801",
    "DerivativeFairValueOfDerivativeAsset": "2802", "DerivativeLiabilitiesCurrent": "2803",
    "InvestmentsFairValueDisclosure": "2804", "CashDividendsPaidToParentCompanyByConsolidatedSubsidiaries": "2805",
    "DerivativeCollateralObligationToReturnCash": "2806", "Goodwill": "2807", "LoansAndLeasesReceivableAllowance": "2808",
    "FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetTransfersIntoLevel3": "2809",
    "PriceRiskDerivativeLiabilitiesAtFairValue": "3003", "DerivativeAssetsNoncurrent": "3004",
    "ConversionOfStockSharesConverted1": "3005", "ConversionOfStockAmountConverted1": "3006",
    "OtherLiabilitiesNoncurrent": "3007", "ConversionOfStockSharesIssued1": "3009",
    "FairValueMeasurementWithUnobservableInputsReconciliationLiabilityTransfersOutOfLevel3": "3096",
    "RevenueFromContractWithCustomerIncludingAssessedTax": "7651",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "7652", "CostOfGoodsAndServicesSold": "2695",
    "CostOfRevenue": "2697", "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization": "9093",
}


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    neg = num[num.dimensionless & (num.value < 0) & num.tag.isin(list(CONCEPTS)) & ~num.custom]
    if neg.empty:
        return empty()
    return make_findings(
        neg, RULE_ID, lambda r: r.tag.astype(str).map(CONCEPTS).to_numpy(),
        lambda r: [f"The concept {t} with a value of {fmt(v)} is negative and has no dimensions. It should not be "
                   f"negative." for t, v in zip(r.tag, r.value)],
        suggested=lambda r: r.value.abs().to_numpy())
