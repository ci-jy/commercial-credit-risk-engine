"""Write the illustrative private borrower fixture in EDGAR companyfacts format.

Northwind Industrial Supply Co. is a fictitious mid-market distributor with
round-number financials, so every ratio in tests/test_ratios.py can be worked
by hand. It is stored in the same JSON shape as SEC companyfacts so it goes
through exactly the same spreading code as real filers.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "edgar" / "sample_borrower.json"
M = 1_000_000

# tag -> {fiscal year: value in $M}
FLOWS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {2022: 365, 2023: 398, 2024: 420},
    "CostOfGoodsAndServicesSold": {2022: 259, 2023: 280, 2024: 294},
    "OperatingIncomeLoss": {2022: 33, 2023: 38, 2024: 42},
    "DepreciationDepletionAndAmortization": {2022: 10, 2023: 11, 2024: 12},
    "InterestExpense": {2022: 8, 2023: 10, 2024: 11},
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {2022: 25, 2023: 28, 2024: 31},
    "IncomeTaxExpenseBenefit": {2022: 6, 2023: 6, 2024: 7},
    "NetIncomeLoss": {2022: 19, 2023: 22, 2024: 24},
    "OperatingLeaseCost": {2022: 5, 2023: 6, 2024: 6},
    "NetCashProvidedByUsedInOperatingActivities": {2022: 29, 2023: 33, 2024: 38},
    "PaymentsToAcquirePropertyPlantAndEquipment": {2022: 12, 2023: 13, 2024: 14},
    "IncomeTaxesPaidNet": {2022: 5, 2023: 6, 2024: 6},
    "PaymentsOfDividends": {2022: 4, 2023: 4, 2024: 5},
}
INSTANTS = {
    "CashAndCashEquivalentsAtCarryingValue": {2022: 12, 2023: 14, 2024: 15},
    "AccountsReceivableNetCurrent": {2022: 52, 2023: 57, 2024: 60},
    "InventoryNet": {2022: 61, 2023: 66, 2024: 70},
    "AssetsCurrent": {2022: 130, 2023: 142, 2024: 150},
    "Assets": {2022: 345, 2023: 364, 2024: 380},
    "LiabilitiesCurrent": {2022: 88, 2023: 95, 2024: 100},
    "ShortTermBorrowings": {2022: 8, 2023: 9, 2024: 10},
    "LongTermDebtCurrent": {2022: 10, 2023: 11, 2024: 12},
    "LongTermDebtNoncurrent": {2022: 135, 2023: 140, 2024: 140},
    "Liabilities": {2022: 235, 2023: 243, 2024: 250},
    "StockholdersEquity": {2022: 110, 2023: 121, 2024: 130},
    "RetainedEarningsAccumulatedDeficit": {2022: 70, 2023: 80, 2024: 90},
}


def fact(fy, value, start=True):
    f = {"end": f"{fy}-12-31", "val": value * M, "fy": fy, "fp": "FY", "form": "10-K", "filed": f"{fy + 1}-02-20"}
    if start:
        f = {"start": f"{fy}-01-01", **f}
    return f


def main():
    gaap = {}
    for tag, vals in FLOWS.items():
        gaap[tag] = {"units": {"USD": [fact(fy, v) for fy, v in vals.items()]}}
    for tag, vals in INSTANTS.items():
        gaap[tag] = {"units": {"USD": [fact(fy, v, start=False) for fy, v in vals.items()]}}
    data = {"cik": None, "entityName": "Northwind Industrial Supply Co. (illustrative)", "facts": {"us-gaap": gaap, "dei": {}}}
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
