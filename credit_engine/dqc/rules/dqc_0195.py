"""DQC_0195 - Facts using an invalid member with the Equity Components Axis.

Rule text (XBRL US DQC): "This rule identifies where facts are reported with
the StatementEquityComponentsAxis using a member that is not appropriate for
the line item." Implemented element IDs:

* 10622 - preferred-stock, NCI, OCI and APIC-adjustment items on ``CommonStockMember``
* 10623 - ``StockholdersEquity`` (parent equity) on a noncontrolling-interest member
* 10624 - shares outstanding/issued on a treasury-stock member
* 10626 - both ``SharesIssued`` and ``SharesOutstanding`` on ``CommonStockMember``
* 10627 - share and stock-issuance items on a retained-earnings member, when larger
  than 10% of the line item's total (or no total is reported)

10625 (treasury-share method consistency) is not implemented. Zero values never fire.
"""

from __future__ import annotations

import pandas as pd

from credit_engine.dqc.base import empty, fmt, make_findings
from credit_engine.dqc.rules._equity import (ISSUANCES, NCI_NON_NEG, RETAINED_EARNINGS_MEMBERS, TREASURY_MEMBERS,
                                             equity_member, is_nci)
from credit_engine.dqc.rules._forms import PERIODIC, REGISTRATION, applicable

RULE_ID = "DQC_0195"
TITLE = "Invalid member on the equity components axis for the line item"
FORMS = PERIODIC | REGISTRATION | {"8-K", "8-K/A", "6-K"}

APIC_ADJUSTMENTS = [
    "AdjustmentToAdditionalPaidInCapitalConvertibleDebtInstrumentIssuedAtSubstantialPremium",
    "AdjustmentsToAdditionalPaidInCapitalConvertibleDebtWithConversionFeature",
    "AdjustmentsToAdditionalPaidInCapitalDividendsInExcessOfRetainedEarnings",
    "AdjustmentsToAdditionalPaidInCapitalIncreaseInCarryingAmountOfRedeemablePreferredStock",
    "AdjustmentsToAdditionalPaidInCapitalMarkToMarket", "AdjustmentsToAdditionalPaidInCapitalOther",
    "AdjustmentsToAdditionalPaidInCapitalShareBasedCompensationEmployeeStockPurchaseProgramRequisiteServicePeriodRecognition",
    "AdjustmentsToAdditionalPaidInCapitalShareBasedCompensationRestrictedStockUnitsRequisiteServicePeriodRecognition",
    "AdjustmentsToAdditionalPaidInCapitalShareBasedCompensationStockOptionsRequisiteServicePeriodRecognition",
    "AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationOtherLongtermIncentivePlansRequisiteServicePeriodRecognition",
    "AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationRequisiteServicePeriodRecognitionValue",
    "AdjustmentsToAdditionalPaidInCapitalStockIssuedIssuanceCosts",
    "AdjustmentsToAdditionalPaidInCapitalStockIssuedOwnshareLendingArrangementIssuanceCosts",
    "AdjustmentsToAdditionalPaidInCapitalStockSplit", "AdjustmentsToAdditionalPaidInCapitalWarrantIssued",
]
NOT_ON_COMMON = [
    "PreferredStockSharesOutstanding", "AdjustmentsToAdditionalPaidInCapitalEquityComponentOfConvertibleDebt",
    "AdjustmentsToAdditionalPaidInCapitalEquityComponentOfConvertibleDebtSubsequentAdjustments",
    "PreferredStockDividendsShares", "StockIssuedDuringPeriodValueTreasuryStockReissued", "TreasuryStockPreferredValue",
    "ProfitLoss", "NetIncomeLossAttributableToRedeemableNoncontrollingInterest",
    "NetIncomeLossIncludingPortionAttributableToNonredeemableNoncontrollingInterest",
    "OtherComprehensiveIncomeLossNetOfTax", "PreferredStockRedemptionPremium", "PreferredStockRedemptionDiscount",
    "PreferredStockAccretionOfRedemptionDiscount", "IncreaseInCarryingAmountOfRedeemablePreferredStock",
    "PreferredStockConvertibleDownRoundFeatureIncreaseDecreaseInEquityAmount1",
    "ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest",
] + NCI_NON_NEG + APIC_ADJUSTMENTS
SHARE_COUNTS = ["SharesOutstanding", "CommonStockSharesOutstanding", "PreferredStockSharesOutstanding", "SharesIssued",
                "CommonStockSharesIssued", "PreferredStockSharesIssued"]
NOT_ON_RETAINED = sorted(set(
    ["SharesOutstanding", "CommonStockSharesOutstanding", "CommonStockDividendsShares",
     "StockIssuedDuringPeriodValueRestrictedStockAwardNetOfForfeitures",
     "StockIssuedDuringPeriodSharesRestrictedStockAwardNetOfForfeitures",
     "StockIssuedDuringPeriodValueConversionOfConvertibleSecurities",
     "StockIssuedDuringPeriodSharesConversionOfConvertibleSecurities",
     "StockIssuedDuringPeriodValueConversionOfConvertibleSecuritiesNetOfAdjustments",
     "PreferredStockSharesOutstanding", "AdjustmentsToAdditionalPaidInCapitalEquityComponentOfConvertibleDebt",
     "AdjustmentsToAdditionalPaidInCapitalEquityComponentOfConvertibleDebtSubsequentAdjustments",
     "PreferredStockDividendsShares", "TreasuryStockPreferredValue", "PreferredStockRedemptionDiscount",
     "PreferredStockAccretionOfRedemptionDiscount", "ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest",
     "TreasuryStockCommonValue", "TreasuryStockValue", "TreasuryStockCarryingBasis",
     "OtherComprehensiveIncomeLossNetOfTax", "OtherComprehensiveIncomeLossBeforeTax", "OtherComprehensiveIncomeLossTax"]
    + [c for c in ISSUANCES if c not in ("StockIssuedDuringPeriodValueDividendReinvestmentPlan",
                                          "StockRepurchasedAndRetiredDuringPeriodValue",
                                          "StockRedeemedOrCalledDuringPeriodValue",
                                          "TreasuryStockRetiredCostMethodAmount")]
    + NCI_NON_NEG))
TREASURY_EXCEPTION = {"StockIssuedDuringPeriodValueEmployeeBenefitPlan", "StockIssuedDuringPeriodValueShareBasedCompensation"}


def _without_equity_axis(seg: str) -> str:
    return "".join(f"{p};" for p in seg.strip(";").split(";") if p and not p.startswith("EquityComponents="))


def check(q) -> pd.DataFrame:
    num = applicable(q.num, FORMS)
    eq = num[num.segments.astype(object).fillna("").str.contains("EquityComponents=", regex=False)].copy()
    if eq.empty:
        return empty()
    eq["member"] = equity_member(eq.segments).to_numpy()
    eq["tag_s"] = eq.tag.astype(str)
    nz = eq[(eq.value != 0) & ~eq.custom]
    out = []

    def emit(rows, eid, why):
        if len(rows):
            out.append(make_findings(rows, RULE_ID, eid, lambda r: [
                f"{t} with a value of {fmt(v)} is reported with the equity components member {m}. {why}"
                for t, v, m in zip(r.tag, r.value, r.member)]))

    emit(nz[(nz.member == "CommonStock") & nz.tag_s.isin(NOT_ON_COMMON)], "10622",
         "This line item does not apply to common stock.")
    emit(nz[nz.member.map(is_nci) & (nz.tag_s == "StockholdersEquity")], "10623",
         "StockholdersEquity excludes noncontrolling interests; use the NCI-inclusive total.")
    emit(nz[nz.member.isin(TREASURY_MEMBERS) & nz.tag_s.isin(SHARE_COUNTS)], "10624",
         "Shares issued or outstanding cannot be reported on a treasury stock member.")
    common = eq[eq.member == "CommonStock"]
    both = set(common[common.tag_s == "SharesIssued"].adsh.astype(str)) & \
        set(common[common.tag_s == "SharesOutstanding"].adsh.astype(str))
    emit(common[common.adsh.astype(str).isin(both) & (common.tag_s == "SharesIssued")]
         .drop_duplicates("adsh"), "10626",
         "Use either shares issued or shares outstanding with CommonStockMember, not both.")

    re_ = nz[nz.member.isin(RETAINED_EARNINGS_MEMBERS) & nz.tag_s.isin(NOT_ON_RETAINED)].copy()
    if len(re_):
        treas = nz[(nz.member == "TreasuryStockCommon") & (nz.value > 0) & nz.tag_s.isin(TREASURY_EXCEPTION)]
        tkeys = set(zip(treas.adsh.astype(str), treas.tag_s, treas.ddate, treas.qtrs))
        re_ = re_[[k not in tkeys for k in zip(re_.adsh.astype(str), re_.tag_s, re_.ddate, re_.qtrs)]]
        totals = num[num.tag.isin(re_.tag_s.unique())].copy()
        totals["seg_k"] = totals.segments.astype(object).fillna("")
        totals = totals[~totals.seg_k.str.contains("EquityComponents=", regex=False)]
        tot = {(str(a), str(t), d, qq, s, str(u)): v for a, t, d, qq, s, u, v in
               zip(totals.adsh, totals.tag, totals.ddate, totals.qtrs, totals.seg_k, totals.uom, totals.value)}
        keep = []
        for r in re_.itertuples():
            key = (str(r.adsh), r.tag_s, r.ddate, r.qtrs, _without_equity_axis(str(r.segments)), str(r.uom))
            t = tot.get(key)
            keep.append(t is None or abs(r.value) > abs(0.1 * t))
        emit(re_[keep], "10627", "Share issuances and other capital items do not belong in retained earnings.")
    out = [o for o in out if len(o)]
    return pd.concat(out, ignore_index=True) if out else empty()
