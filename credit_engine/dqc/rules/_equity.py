"""Concept and member lists shared by DQC_0194 and DQC_0195 (equity components axis)."""

from __future__ import annotations

import pandas as pd

ISSUANCES = [
    "StockIssuedDuringPeriodValueNewIssues", "StockIssuedDuringPeriodSharesNewIssues",
    "StockIssuedDuringPeriodValueIssuedForServices", "StockIssuedDuringPeriodSharesIssuedForServices",
    "StockGrantedDuringPeriodValueSharebasedCompensationGross", "StockGrantedDuringPeriodValueSharebasedCompensationForfeited",
    "StockGrantedDuringPeriodValueSharebasedCompensation",
    "ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsGrantsInPeriodGross",
    "ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsForfeituresInPeriod",
    "ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsGrantsInPeriod",
    "StockIssuedDuringPeriodValueShareBasedCompensationGross", "StockIssuedDuringPeriodValueShareBasedCompensationForfeited",
    "StockIssuedDuringPeriodValueShareBasedCompensation", "StockIssuedDuringPeriodSharesShareBasedCompensationGross",
    "StockIssuedDuringPeriodSharesShareBasedCompensationForfeited", "StockIssuedDuringPeriodSharesShareBasedCompensation",
    "StockIssuedDuringPeriodValueRestrictedStockAwardGross", "StockIssuedDuringPeriodValueRestrictedStockAwardForfeitures",
    "StockIssuedDuringPeriodSharesRestrictedStockAwardGross", "StockIssuedDuringPeriodSharesRestrictedStockAwardForfeited",
    "StockIssuedDuringPeriodValueStockOptionsExercised", "StockIssuedDuringPeriodSharesStockOptionsExercised",
    "StockIssuedDuringPeriodValueEmployeeStockOwnershipPlan", "StockIssuedDuringPeriodSharesEmployeeStockOwnershipPlan",
    "StockIssuedDuringPeriodValueEmployeeStockPurchasePlan", "StockIssuedDuringPeriodSharesEmployeeStockPurchasePlans",
    "StockIssuedDuringPeriodValueEmployeeBenefitPlan", "StockIssuedDuringPeriodSharesEmployeeBenefitPlan",
    "StockIssuedDuringPeriodValueAcquisitions", "StockIssuedDuringPeriodSharesAcquisitions",
    "StockIssuedDuringPeriodValueConversionOfUnits", "StockIssuedDuringPeriodSharesConversionOfUnits",
    "StockIssuedDuringPeriodValueStockDividend", "StockDividendsShares",
    "StockIssuedDuringPeriodValueDividendReinvestmentPlan", "StockIssuedDuringPeriodSharesDividendReinvestmentPlan",
    "StockIssuedDuringPeriodValuePurchaseOfAssets", "StockIssuedDuringPeriodSharesPurchaseOfAssets",
    "StockIssuedDuringPeriodValueOther", "StockIssuedDuringPeriodSharesOther", "StockIssuedDuringPeriodSharesStockSplits",
    "StockIssuedDuringPeriodSharesReverseStockSplits", "StockRepurchasedAndRetiredDuringPeriodValue",
    "StockRepurchasedAndRetiredDuringPeriodShares", "StockRepurchasedDuringPeriodValue", "StockRepurchasedDuringPeriodShares",
    "StockRedeemedOrCalledDuringPeriodValue", "StockRedeemedOrCalledDuringPeriodShares",
    "TreasuryStockRetiredParValueMethodAmount", "TreasuryStockRetiredCostMethodAmount", "TreasuryStockSharesRetired",
    "AmortizationOfESOPAward",
]
COMMON_NON_NEG = ["SharesOutstanding", "CommonStockSharesOutstanding",
                  "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "CommonStockDividendsShares"] + ISSUANCES
PREFERRED_NON_NEG = ["SharesOutstanding", "PreferredStockSharesOutstanding",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                     "PreferredStockDividendsShares"] + ISSUANCES
NCI_NON_NEG = ["NoncontrollingInterestIncreaseFromSubsidiaryEquityIssuance",
               "NoncontrollingInterestIncreaseFromSaleOfParentEquityInterest",
               "NoncontrollingInterestIncreaseFromBusinessCombination", "NoncontrollingInterestDecreaseFromDeconsolidation",
               "MinorityInterestDecreaseFromDistributionsToNoncontrollingInterestHolders",
               "MinorityInterestDecreaseFromRedemptions"]
RETAINED_EARNINGS_MEMBERS = {"RetainedEarnings", "RetainedEarningsAppropriated", "RetainedEarningsUnappropriated"}
TREASURY_MEMBERS = {"TreasuryStockCommon", "TreasuryStockPreferred"}


def is_nci(member: str) -> bool:
    """Members of the NCI equity components: NoncontrollingInterestMember and its AOCI variants."""
    return "NoncontrollingInterest" in member


def equity_member(segments: pd.Series) -> pd.Series:
    """The StatementEquityComponentsAxis member of each fact ('' when the axis is absent)."""
    return segments.astype(object).fillna("").str.extract(r"(?:^|;)EquityComponents=([^;]*)")[0].fillna("")
