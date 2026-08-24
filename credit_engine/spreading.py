"""Map US-GAAP XBRL facts into a standardized annual spread.

Each standardized line item has an ordered list of candidate sources. A
candidate is either a single us-gaap tag or a derived formula over other
tags; the first candidate available for a fiscal year wins and is recorded as
that cell's provenance, so every number in the spread can be traced back to
the tag it came from.

Period rules
------------
* Annual flows (income statement, cash flow) must come from a 10-K and span
  350-380 days.
* Balance sheet instants must fall within 10 days of the fiscal year end.
* Revenue prefers RevenueFromContractWithCustomerExcludingAssessedTax over
  the broader ``Revenues`` tag, which some filers use for gross totals that
  differ from reported net revenue.
* When the same period is reported in several filings (original and later
  comparative columns), the most recently filed value is used, so restatements
  flow through.
* Fiscal years ending in January or the first week of February (retailers'
  52/53-week years) are labelled with the prior calendar year, matching how
  those companies name their fiscal years.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import pandas as pd

FLOW = "flow"
INSTANT = "instant"


@dataclass(frozen=True)
class Derived:
    """A candidate source computed from other tags (all must be present)."""

    tags: tuple[str, ...]
    fn: Callable[..., float]
    label: str


def _sum(*xs: float) -> float:
    return float(sum(xs))


def _neg(a: float) -> float:
    return float(-a)


def _diff(a: float, b: float) -> float:
    return float(a - b)


# (statement, kind, candidates, default-if-missing)
LINE_ITEMS: dict[str, tuple[str, str, list, float | None]] = {
    # Income statement
    "revenue": ("IS", FLOW, [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ], None),
    "cogs": ("IS", FLOW, [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    ], None),
    "operating_income": ("IS", FLOW, [
        "OperatingIncomeLoss",
        Derived(("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                 "InterestExpense"), _sum, "pretax income + InterestExpense"),
    ], None),
    "depreciation_amortization": ("IS", FLOW, [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        Derived(("Depreciation", "AmortizationOfIntangibleAssets"), _sum,
                "Depreciation + AmortizationOfIntangibleAssets"),
        "Depreciation",
    ], None),
    "interest_expense": ("IS", FLOW, [
        "InterestExpense",
        "InterestExpenseNonoperating",
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
        Derived(("InterestIncomeExpenseNet",), _neg, "-InterestIncomeExpenseNet (net interest)"),
        Derived(("InterestIncomeExpenseNonoperatingNet",), _neg, "-InterestIncomeExpenseNonoperatingNet (net interest)"),
        "InterestPaidNet",
    ], 0.0),
    "pretax_income": ("IS", FLOW, [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ], None),
    "income_tax": ("IS", FLOW, ["IncomeTaxExpenseBenefit"], 0.0),
    "net_income": ("IS", FLOW, [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ], None),
    "operating_lease_cost": ("IS", FLOW, ["OperatingLeaseCost", "OperatingLeasesRentExpenseNet", "LeaseCost"], 0.0),
    # Balance sheet
    "cash": ("BS", INSTANT, [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ], None),
    "receivables": ("BS", INSTANT, ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"], 0.0),
    "inventory": ("BS", INSTANT, ["InventoryNet", "InventoryFinishedGoodsNetOfReserves"], 0.0),
    "current_assets": ("BS", INSTANT, ["AssetsCurrent"], None),
    "total_assets": ("BS", INSTANT, ["Assets"], None),
    "current_liabilities": ("BS", INSTANT, ["LiabilitiesCurrent"], None),
    "short_term_borrowings": ("BS", INSTANT, [
        "ShortTermBorrowings", "CommercialPaper", "ShortTermBankLoansAndNotesPayable",
    ], 0.0),
    "current_portion_ltd": ("BS", INSTANT, [
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "DebtCurrent",
    ], 0.0),
    "long_term_debt": ("BS", INSTANT, [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        Derived(("LongTermDebt", "LongTermDebtCurrent"), _diff, "LongTermDebt - LongTermDebtCurrent"),
        "LongTermDebt",
        "SeniorLongTermNotes",
    ], 0.0),
    "total_liabilities": ("BS", INSTANT, [
        "Liabilities",
        Derived(("LiabilitiesAndStockholdersEquity",
                 "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"), _diff,
                "LiabilitiesAndStockholdersEquity - total equity"),
        Derived(("LiabilitiesAndStockholdersEquity", "StockholdersEquity"), _diff,
                "LiabilitiesAndStockholdersEquity - StockholdersEquity"),
    ], None),
    "total_equity": ("BS", INSTANT, [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ], None),
    "retained_earnings": ("BS", INSTANT, ["RetainedEarningsAccumulatedDeficit"], 0.0),
    # Cash flow
    "cfo": ("CF", FLOW, [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ], None),
    "capex": ("CF", FLOW, [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        "PaymentsForCapitalImprovements",
    ], 0.0),
    "cash_taxes": ("CF", FLOW, ["IncomeTaxesPaidNet", "IncomeTaxesPaid"], None),
    "dividends": ("CF", FLOW, ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"], 0.0),
}

ALL_TAGS: set[str] = set()
for _stmt, _kind, _cands, _default in LINE_ITEMS.values():
    for _c in _cands:
        ALL_TAGS.update(_c.tags if isinstance(_c, Derived) else (_c,))
ALL_TAGS.update({"NetIncomeLoss", "Revenues"})

STATEMENT_ORDER = [k for k in LINE_ITEMS]


@dataclass
class Spread:
    company: str
    cik: int | None
    values: pd.DataFrame  # index: line items, columns: fiscal years (ascending)
    sources: dict[tuple[str, int], str]
    period_ends: dict[int, str]
    shares_outstanding: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def years(self) -> list[int]:
        return list(self.values.columns)

    @property
    def latest_year(self) -> int:
        return self.years[-1]

    def year(self, fy: int | None = None) -> dict[str, float]:
        fy = self.latest_year if fy is None else fy
        return {k: float(v) for k, v in self.values[fy].items()}


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def fiscal_year_label(end: date) -> int:
    if end.month == 1 or (end.month == 2 and end.day <= 7):
        return end.year - 1
    return end.year


def _usd_facts(gaap: dict, tag: str) -> list[dict]:
    body = gaap.get(tag)
    if not body:
        return []
    return body.get("units", {}).get("USD", [])


def _annual_flows(facts: list[dict]) -> dict[date, float]:
    """end date -> value, for ~1-year 10-K durations, latest filing wins."""
    best: dict[date, tuple[str, float]] = {}
    for f in facts:
        if f.get("form") not in ("10-K", "10-K/A") or "start" not in f:
            continue
        start, end = _parse(f["start"]), _parse(f["end"])
        if not 350 <= (end - start).days <= 380:
            continue
        filed = f.get("filed", "")
        if end not in best or filed > best[end][0]:
            best[end] = (filed, float(f["val"]))
    return {k: v for k, (_, v) in best.items()}


def _instants(facts: list[dict]) -> dict[date, float]:
    best: dict[date, tuple[str, float]] = {}
    for f in facts:
        if f.get("form") not in ("10-K", "10-K/A") or "start" in f:
            continue
        end = _parse(f["end"])
        filed = f.get("filed", "")
        if end not in best or filed > best[end][0]:
            best[end] = (filed, float(f["val"]))
    return {k: v for k, (_, v) in best.items()}


def _lookup(series: dict[date, float], fy_end: date, kind: str) -> float | None:
    if fy_end in series:
        return series[fy_end]
    tol = 10 if kind == INSTANT else 7
    near = [(abs((d - fy_end).days), d) for d in series if abs((d - fy_end).days) <= tol]
    if near:
        return series[min(near)[1]]
    return None


def fiscal_year_ends(gaap: dict) -> list[date]:
    """Fiscal year end dates, from annual revenue / net income durations."""
    ends: set[date] = set()
    for tag in ("NetIncomeLoss", "ProfitLoss", "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax"):
        ends.update(_annual_flows(_usd_facts(gaap, tag)).keys())
    # collapse ends within a week of each other (52/53-week calendars)
    out: list[date] = []
    for d in sorted(ends):
        if out and (d - out[-1]).days < 300:
            out[-1] = d
        else:
            out.append(d)
    return out


def spread_companyfacts(data: dict, n_years: int = 4) -> Spread:
    """Build a standardized spread for the most recent ``n_years`` fiscal years."""
    gaap = data.get("facts", {}).get("us-gaap", {})
    ends = fiscal_year_ends(gaap)
    if not ends:
        raise ValueError("no annual 10-K periods found in companyfacts")
    ends = ends[-n_years:]
    cache: dict[tuple[str, str], dict[date, float]] = {}

    def series(tag: str, kind: str) -> dict[date, float]:
        key = (tag, kind)
        if key not in cache:
            facts = _usd_facts(gaap, tag)
            cache[key] = _annual_flows(facts) if kind == FLOW else _instants(facts)
        return cache[key]

    values: dict[int, dict[str, float]] = {}
    sources: dict[tuple[str, int], str] = {}
    period_ends: dict[int, str] = {}
    notes: list[str] = []
    for end in ends:
        fy = fiscal_year_label(end)
        period_ends[fy] = end.isoformat()
        col: dict[str, float] = {}
        for item, (_stmt, kind, candidates, default) in LINE_ITEMS.items():
            val, src = None, None
            for cand in candidates:
                if isinstance(cand, Derived):
                    parts = [_lookup(series(t, kind), end, kind) for t in cand.tags]
                    if all(p is not None for p in parts):
                        val, src = cand.fn(*parts), cand.label
                        break
                else:
                    v = _lookup(series(cand, kind), end, kind)
                    if v is not None:
                        val, src = v, cand
                        break
            if val is None:
                if default is None:
                    notes.append(f"FY{fy}: {item} not reported; left blank")
                    val, src = float("nan"), "missing"
                else:
                    val, src = default, "not reported (0)"
            col[item] = val
            sources[(item, fy)] = src
        # Cash taxes fall back to the income-statement provision when not disclosed.
        if pd.isna(col["cash_taxes"]):
            col["cash_taxes"] = col["income_tax"]
            sources[("cash_taxes", fy)] = "IncomeTaxExpenseBenefit (provision proxy)"
        values[fy] = col
    df = pd.DataFrame(values)[sorted(values)]
    df = df.loc[STATEMENT_ORDER]
    shares = None
    dei = data.get("facts", {}).get("dei", {})
    so = dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if so:
        shares = float(max(so, key=lambda f: (f.get("end", ""), f.get("filed", "")))["val"])
    return Spread(
        company=data.get("entityName", "Unknown"),
        cik=data.get("cik"),
        values=df,
        sources=sources,
        period_ends=period_ends,
        shares_outstanding=shares,
        notes=notes,
    )
