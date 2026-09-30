"""Each rule on hand-built tables with planted errors (and the near-misses it must not flag)."""

import pytest

from conftest import ADSH, build_quarter, fact
from credit_engine.dqc import RULE_IDS, rule_module, run_screen
from credit_engine.dqc.base import FINDING_COLS


def run(rule, facts, **kw):
    return rule_module(rule).check(build_quarter(facts, **kw))


def test_every_rule_module_cites_its_rule_and_returns_the_schema():
    assert len(RULE_IDS) == 12
    for rid in RULE_IDS:
        mod = rule_module(rid)
        assert mod.RULE_ID == rid and rid in mod.__doc__ and "Rule text" in mod.__doc__
        assert list(mod.check(build_quarter([fact("Assets", 1)])).columns) == FINDING_COLS


# DQC_0001 ---------------------------------------------------------------------------------------

def test_0001_class_of_stock_member_on_equity_components_axis():
    f = run("DQC_0001", [fact("StockIssuedDuringPeriodValueNewIssues", 5, qtrs=4, segments="EquityComponents=CommonClassA;"),
                         fact("StockIssuedDuringPeriodValueNewIssues", 5, qtrs=4, segments="EquityComponents=CommonStock;"),
                         fact("StockIssuedDuringPeriodValueNewIssues", 5, qtrs=4, segments="EquityComponents=MyCustomReserve;")])
    assert f.concept.tolist() == ["EquityComponents=CommonClassA"] and f.element_id.tolist() == ["75"]


def test_0001_closed_axis_rejects_extension_members_but_allows_whitelist():
    f = run("DQC_0001", [fact("Revenues", 1, qtrs=4, segments="ConsolidationItems=WidgetSegment;"),
                         fact("Revenues", 1, qtrs=4, segments="ConsolidationItems=OperatingSegments;"),
                         fact("Revenues", 1, qtrs=4, segments="ConsolidationItems=CorporateAndEliminations;"),
                         fact("Revenues", 1, qtrs=4, segments="Range=Maximum;"),
                         fact("Revenues", 1, qtrs=4, segments="Range=Ceiling;")])
    assert sorted(f.concept) == ["ConsolidationItems=WidgetSegment", "Range=Ceiling"]


# DQC_0004 ---------------------------------------------------------------------------------------

def test_0004_assets_not_equal_to_liabilities_and_equity():
    f = run("DQC_0004", [fact("Assets", 10_500_000), fact("LiabilitiesAndStockholdersEquity", 10_000_000),
                         fact("Assets", 9_000_000, ddate=20241231),
                         fact("LiabilitiesAndStockholdersEquity", 9_000_000, ddate=20241231)])
    assert len(f) == 1 and f.element_id.iat[0] == "16" and f.ddate.iat[0] == 20251231
    assert f.suggested.iat[0] == 10_000_000


def test_0004_tolerance_is_two_units_of_the_lowest_decimals():
    # reported in thousands (decimals -3): a 2,000 difference passes, 3,000 fails
    ok = run("DQC_0004", [fact("Assets", 10_002_000), fact("LiabilitiesAndStockholdersEquity", 10_000_000),
                          fact("Cash", 1_234_000)])
    bad = run("DQC_0004", [fact("Assets", 10_003_000), fact("LiabilitiesAndStockholdersEquity", 10_000_000),
                           fact("Cash", 1_234_000)])
    assert ok.empty and len(bad) == 1


def test_0004_components_must_be_present():
    f = run("DQC_0004", [fact("Assets", 10_000_000), fact("AssetsCurrent", 4_000_000)])
    assert f.empty
    f = run("DQC_0004", [fact("Assets", 10_000_000), fact("AssetsCurrent", 4_000_000), fact("AssetsNoncurrent", 5_000_000)])
    assert f.element_id.tolist() == ["9280"] and f.suggested.iat[0] == 9_000_000


def test_0004_runs_per_dimension_set():
    seg = "LegalEntity=SubsidiaryIssuer;"
    f = run("DQC_0004", [fact("Assets", 500_000, segments=seg), fact("LiabilitiesAndStockholdersEquity", 400_000, segments=seg),
                         fact("Assets", 900_000), fact("LiabilitiesAndStockholdersEquity", 900_000)])
    assert f.segments.tolist() == [seg]


# DQC_0005 ---------------------------------------------------------------------------------------

def test_0005_cover_shares_dated_before_period_end():
    f = run("DQC_0005", [fact("EntityCommonStockSharesOutstanding", 1e6, ddate=20250930, uom="shares", version="dei/2025"),
                         fact("EntityCommonStockSharesOutstanding", 1e6, ddate=20260228, uom="shares", version="dei/2025")])
    assert f.element_id.tolist() == ["17"] and f.ddate.tolist() == [20250930]


def test_0005_subsequent_events_and_forecasts_must_be_after_period_end():
    f = run("DQC_0005", [fact("DebtInstrumentFaceAmount", 5e6, ddate=20250930, segments="SubsequentEventType=SubsequentEvent;"),
                         # on the (rounded) period end: may be a date a few days later, so not flagged
                         fact("DebtInstrumentFaceAmount", 6e6, ddate=20251231, segments="SubsequentEventType=SubsequentEvent;"),
                         fact("DebtInstrumentFaceAmount", 5e6, ddate=20260228, segments="SubsequentEventType=SubsequentEvent;"),
                         fact("Revenues", 1, ddate=20250630, qtrs=2, segments="Scenario=ScenarioForecast;"),
                         fact("Revenues", 1, ddate=20261231, qtrs=4, segments="Scenario=ScenarioForecast;")])
    assert sorted(zip(f.element_id, f.ddate)) == [("48", 20250930), ("49", 20250630)]


# DQC_0009 ---------------------------------------------------------------------------------------

def test_0009_outstanding_greater_than_issued():
    f = run("DQC_0009", [fact("CommonStockSharesOutstanding", 1_200_123, uom="shares"),
                         fact("CommonStockSharesIssued", 1_000_456, uom="shares"),
                         fact("CommonStockSharesAuthorized", 10_000_000, uom="shares"),
                         fact("CommonStockSharesOutstanding", 1_000_456, ddate=20241231, uom="shares"),
                         fact("CommonStockSharesIssued", 1_000_456, ddate=20241231, uom="shares")])
    assert f.element_id.tolist() == ["24"] and f.suggested.iat[0] == 1_000_456


def test_0009_stock_split_filings_skip_authorized_checks():
    facts = [fact("CommonStockSharesIssued", 5000, uom="shares"), fact("CommonStockSharesAuthorized", 1000, uom="shares")]
    assert run("DQC_0009", facts).element_id.tolist() == ["21"]
    splits = [fact("StockIssuedDuringPeriodSharesStockSplits", 10, qtrs=4, uom="shares"),
              fact("StockholdersEquityNoteStockSplitConversionRatio1", 2, qtrs=4, uom="pure")]
    assert run("DQC_0009", facts + splits).empty


# DQC_0013 ---------------------------------------------------------------------------------------

def test_0013_negative_tax_credit_with_positive_pretax_income():
    pre = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
    rate = "EffectiveIncomeTaxRateReconciliationTaxCredits"
    f = run("DQC_0013", [fact(pre, 5_000_000, qtrs=4), fact(rate, -0.03, qtrs=4, uom="pure"),
                         fact(pre, -2_000_000, ddate=20241231, qtrs=4), fact(rate, -0.05, ddate=20241231, qtrs=4, uom="pure")])
    assert len(f) == 1 and f.ddate.iat[0] == 20251231 and f.element_id.iat[0] == "2774"
    assert f.suggested.iat[0] == pytest.approx(0.03)


def test_0013_pretax_from_domestic_plus_foreign():
    f = run("DQC_0013", [fact("IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic", -1_000_000, qtrs=4),
                         fact("IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign", 3_000_000, qtrs=4),
                         fact("EffectiveIncomeTaxRateReconciliationDeductions", -0.01, qtrs=4, uom="pure")])
    assert f.element_id.tolist() == ["2873"]


# DQC_0014 ---------------------------------------------------------------------------------------

def test_0014_negative_goodwill_only_without_dimensions():
    f = run("DQC_0014", [fact("Goodwill", -5_000_000), fact("Goodwill", -1_000_000, segments="BusinessSegments=Retail;"),
                         fact("Goodwill", 7_000_000, ddate=20241231)])
    assert f.element_id.tolist() == ["2807"] and f.suggested.iat[0] == 5_000_000


# DQC_0015 ---------------------------------------------------------------------------------------

def test_0015_negative_non_negative_concept_and_exclusions():
    f = run("DQC_0015", [
        fact("LongTermDebt", -2_000_000),                                         # flagged
        fact("LongTermDebt", -100_000, segments="ConsolidationItems=IntersegmentElimination;"),  # 'eliminat'
        fact("LongTermDebt", -100_000, segments="BusinessSegments=Retail;"),     # excluded axis
        fact("LongTermDebt", -100_000, segments="ConsolidatedEntities=ParentCompany;"),  # excluded pair
        fact("LongTermDebt", -100_000, segments="ProductOrService=Widgets;"),     # flagged
        fact("LongTermDebt", -1_000, version=ADSH),                                         # extension concept
        fact("NetIncomeLoss", -5_000_000, qtrs=4),                                           # may be negative
    ])
    assert sorted(f.segments.fillna("")) == ["", "ProductOrService=Widgets;"]
    assert set(f.suggested) == {2_000_000, 100_000}
    assert (f.element_id != "").all()


# DQC_0091 ---------------------------------------------------------------------------------------

def test_0091_percent_above_ten():
    tags = [{"tag": t, "version": "us-gaap/2025", "custom": "0", "datatype": "percent"} for t in
            ("DebtInstrumentInterestRateStatedPercentage", "EffectiveIncomeTaxRateContinuingOperations",
             "EffectiveIncomeTaxRateReconciliationAtFederalStatutoryIncomeTaxRate")]
    f = run("DQC_0091", [fact("DebtInstrumentInterestRateStatedPercentage", 5.25, uom="pure"),
                         fact("DebtInstrumentInterestRateStatedPercentage", 0.0525, ddate=20241231, uom="pure"),
                         fact("DebtInstrumentInterestRateStatedPercentage", 52.5, ddate=20231231, uom="pure"),
                         fact("EffectiveIncomeTaxRateContinuingOperations", 21, qtrs=4, uom="pure"),
                         fact("EffectiveIncomeTaxRateReconciliationAtFederalStatutoryIncomeTaxRate", 21, qtrs=4, uom="pure")],
            tags=tags)
    assert sorted(f.concept) == ["DebtInstrumentInterestRateStatedPercentage",
                                 "EffectiveIncomeTaxRateReconciliationAtFederalStatutoryIncomeTaxRate"]
    assert sorted(f.suggested) == pytest.approx([0.21, 0.525])


# DQC_0095 ---------------------------------------------------------------------------------------

def test_0095_cover_shares_scaled_by_a_thousand():
    f = run("DQC_0095", [fact("EntityCommonStockSharesOutstanding", 25_000, ddate=20260131, uom="shares", version="dei/2025"),
                         fact("CommonStockSharesOutstanding", 25_000_000, uom="shares")])
    assert f.element_id.tolist() == ["9528"] and f.suggested.iat[0] == pytest.approx(25_000_000)
    ok = run("DQC_0095", [fact("EntityCommonStockSharesOutstanding", 25_100_000, ddate=20260131, uom="shares", version="dei/2025"),
                          fact("CommonStockSharesOutstanding", 25_000_000, uom="shares")])
    assert ok.empty


# DQC_0125 ---------------------------------------------------------------------------------------

def test_0125_negative_lease_cost_unless_sublease_income():
    facts = [fact("LeaseCost", -3_000_000, qtrs=4)]
    assert run("DQC_0125", facts).suggested.tolist() == [3_000_000]
    assert run("DQC_0125", facts + [fact("SubleaseIncome", 4_000_000, qtrs=4)]).empty
    assert run("DQC_0125", facts, form="10-Q").empty


# DQC_0194 ---------------------------------------------------------------------------------------

def test_0194_negative_repurchase_on_common_stock_member():
    f = run("DQC_0194", [
        fact("StockRepurchasedDuringPeriodShares", -50_000, qtrs=4, uom="shares", segments="EquityComponents=CommonStock;"),
        fact("StockRepurchasedDuringPeriodShares", -50_000, qtrs=4, uom="shares",
             segments="ClassOfStock=CommonClassA;EquityComponents=CommonStock;"),
        fact("StockRepurchasedDuringPeriodValue", -900_000, qtrs=4, segments="EquityComponents=TreasuryStockCommon;"),
        fact("MinorityInterestDecreaseFromRedemptions", -10_000, qtrs=4, segments="EquityComponents=NoncontrollingInterest;"),
        # a filer's own NCI member is not in the DQC member list
        fact("MinorityInterestDecreaseFromRedemptions", -10_000, qtrs=4,
             segments="EquityComponents=RedeemableNoncontrollingInterest;"),
    ])
    assert sorted(zip(f.element_id, f.concept)) == [("10621", "StockRepurchasedDuringPeriodShares"),
                                                    ("10637", "MinorityInterestDecreaseFromRedemptions")]


# DQC_0195 ---------------------------------------------------------------------------------------

def test_0195_line_items_on_wrong_equity_member():
    f = run("DQC_0195", [
        fact("ProfitLoss", 1_000_000, qtrs=4, segments="EquityComponents=CommonStock;"),                 # 10622
        fact("ProfitLoss", 1_000_000, qtrs=4, segments="EquityComponents=RetainedEarnings;"),             # fine
        fact("StockholdersEquity", 300_000, segments="EquityComponents=NoncontrollingInterest;"),         # 10623
        fact("CommonStockSharesOutstanding", 9_000, uom="shares", segments="EquityComponents=TreasuryStockCommon;"),  # 10624
        fact("StockIssuedDuringPeriodValueNewIssues", 500_000, qtrs=4, segments="EquityComponents=RetainedEarnings;"),  # 10627
        fact("StockIssuedDuringPeriodValueNewIssues", 600_000, qtrs=4),
        fact("StockIssuedDuringPeriodValueOther", 1_000, qtrs=4, segments="EquityComponents=RetainedEarnings;"),  # < 10% of total
        fact("StockIssuedDuringPeriodValueOther", 900_000, qtrs=4),
    ])
    assert sorted(zip(f.element_id, f.concept)) == [
        ("10622", "ProfitLoss"), ("10623", "StockholdersEquity"), ("10624", "CommonStockSharesOutstanding"),
        ("10627", "StockIssuedDuringPeriodValueNewIssues")]


def test_run_screen_combines_rules():
    q = build_quarter([fact("Goodwill", -5_000_000), fact("Assets", 10_500_000),
                       fact("LiabilitiesAndStockholdersEquity", 10_000_000)])
    f = run_screen(q)
    assert set(f.rule) == {"DQC_0004", "DQC_0014"}
