"""Tag mapping and spreads checked against figures read off each company's 10-K."""

import math

import pytest

from credit_engine.edgar import load_fixture
from credit_engine.spreading import Derived, fiscal_year_label, spread_companyfacts
from datetime import date

M = 1e6

# FY2023 figures as printed in each company's FY2023 Form 10-K ($ millions):
# revenue (contract revenue: total revenue for Kohl's, net sales for Macy's, which reports
# $774M of credit card and other revenue separately), operating income (loss), and
# net income (loss) attributable to the company.
HAND_VERIFIED_FY2023 = {
    "hasbro": {"revenue": 5003.3, "operating_income": -1538.8, "net_income": -1489.3},
    "mattel": {"revenue": 5441.2, "operating_income": 561.7, "net_income": 214.4},
    "whirlpool": {"revenue": 19455.0, "operating_income": 1015.0, "net_income": 481.0},
    "kohls": {"revenue": 17476.0, "operating_income": 717.0, "net_income": 317.0},
    "macys": {"revenue": 23092.0, "operating_income": 301.0, "net_income": 45.0},
}


@pytest.mark.parametrize("name", sorted(HAND_VERIFIED_FY2023))
def test_fixture_spreads_match_10k(name):
    s = spread_companyfacts(load_fixture(name))
    assert 2023 in s.years
    for item, expected in HAND_VERIFIED_FY2023[name].items():
        assert s.values.at[item, 2023] / M == pytest.approx(expected, abs=0.05), item


@pytest.mark.parametrize("name", sorted(HAND_VERIFIED_FY2023))
def test_balance_sheet_identity_and_completeness(name):
    s = spread_companyfacts(load_fixture(name))
    for fy in s.years:
        y = s.year(fy)
        for item in ("revenue", "operating_income", "total_assets", "total_liabilities", "cfo", "cash"):
            assert math.isfinite(y[item]), (fy, item)
        # liabilities + equity cannot exceed total assets by more than noncontrolling/mezzanine items
        assert y["total_liabilities"] + y["total_equity"] == pytest.approx(y["total_assets"], rel=0.02)
        assert y["current_assets"] <= y["total_assets"]


def test_hasbro_revenue_prefers_contract_revenue_over_gross_revenues_tag():
    s = spread_companyfacts(load_fixture("hasbro"))
    # Hasbro's later filings tag a larger "Revenues" total; reported net revenue for FY2024 is $4,135.5M
    assert s.values.at["revenue", 2024] / M == pytest.approx(4135.5)
    assert s.sources[("revenue", 2024)] == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_documented_fallbacks_are_used():
    kohls = spread_companyfacts(load_fixture("kohls"))
    assert kohls.sources[("interest_expense", 2023)].startswith("-InterestIncomeExpenseNet")
    assert kohls.values.at["interest_expense", 2023] / M == pytest.approx(344.0)
    whr = spread_companyfacts(load_fixture("whirlpool"))
    assert "LiabilitiesAndStockholdersEquity" in whr.sources[("total_liabilities", 2023)]
    mattel = spread_companyfacts(load_fixture("mattel"))
    assert mattel.sources[("capex", 2024)] == "PaymentsToAcquireOtherPropertyPlantAndEquipment"


def _facts(tag_values, start=True, filed="2024-02-01"):
    out = {}
    for tag, rows in tag_values.items():
        facts = []
        for end, val, *rest in rows:
            f = {"end": end, "val": val, "form": "10-K", "filed": rest[0] if rest else filed}
            if start:
                f["start"] = f"{int(end[:4])}-01-01"
            facts.append(f)
        out[tag] = {"units": {"USD": facts}}
    return out


def test_priority_order_latest_filing_and_period_filters():
    gaap = _facts({
        "NetIncomeLoss": [("2023-12-31", 10)],
        "RevenueFromContractWithCustomerExcludingAssessedTax": [("2023-12-31", 100, "2024-02-01"),
                                                                ("2023-12-31", 105, "2025-02-01")],
        "Revenues": [("2023-12-31", 999)],
        "OperatingIncomeLoss": [("2023-12-31", 20)],
        "Depreciation": [("2023-12-31", 3)],
        "AmortizationOfIntangibleAssets": [("2023-12-31", 2)],
    })
    gaap.update(_facts({"LongTermDebt": [("2023-12-31", 50)], "LongTermDebtCurrent": [("2023-12-31", 5)],
                        "Assets": [("2023-12-31", 200)]}, start=False))
    # a quarterly fact must be ignored
    gaap["OperatingIncomeLoss"]["units"]["USD"].append(
        {"start": "2023-10-01", "end": "2023-12-31", "val": 7, "form": "10-K", "filed": "2026-01-01"})
    s = spread_companyfacts({"entityName": "T", "facts": {"us-gaap": gaap}})
    y = s.year(2023)
    assert y["revenue"] == 105  # restated value from the later filing wins; Revenues tag is lower priority
    assert y["operating_income"] == 20
    assert y["depreciation_amortization"] == 5
    assert s.sources[("depreciation_amortization", 2023)] == "Depreciation + AmortizationOfIntangibleAssets"
    assert y["long_term_debt"] == 45 and y["current_portion_ltd"] == 5
    assert y["short_term_borrowings"] == 0 and s.sources[("short_term_borrowings", 2023)] == "not reported (0)"
    assert math.isnan(y["cfo"]) and any("cfo" in n for n in s.notes)


def test_retail_fiscal_year_labels():
    assert fiscal_year_label(date(2024, 2, 3)) == 2023
    assert fiscal_year_label(date(2026, 1, 31)) == 2025
    assert fiscal_year_label(date(2023, 12, 31)) == 2023
    assert fiscal_year_label(date(2025, 12, 28)) == 2025
    assert isinstance(Derived(("a",), abs, "x"), Derived)
