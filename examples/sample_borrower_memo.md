# Credit memo: Northwind Industrial Supply Co. (illustrative)

Borrower key: `sample_borrower` · latest fiscal year FY2024 (period end 2024-12-31) · amounts in $ millions

## 1. Summary

- **Risk grade: 7 – Watch (B+/B)** on PD 2.17% (the more conservative of the scorecard and Merton PDs; basis: scorecard).
- Leverage 3.00x Debt/EBITDA, 2.72x net; interest coverage 3.82x; FCCR 1.38x; free cash flow $24.0M.
- Covenants: 4 of 4 pass at FY2024.
- Stress (EBITDA decline): first covenant to break is *Min fixed-charge coverage* at -6.9%.
- Stress (Rate shock on floating debt): first covenant to break is *Min fixed-charge coverage* at +309 bp.
- Stress (Revenue decline): first covenant to break is *Min fixed-charge coverage* at -3.0%.
- Altman Z'' = 2.92 (safe zone); scorecard PD 2.17%; no traded equity, so no Merton estimate.

## 2. Financial spread

| Line item | FY2022 | FY2023 | FY2024 |
|---|---:|---:|---:|
| Revenue | 365.0 | 398.0 | 420.0 |
| Cost of goods sold | 259.0 | 280.0 | 294.0 |
| Operating income (EBIT) | 33.0 | 38.0 | 42.0 |
| Depreciation & amortization | 10.0 | 11.0 | 12.0 |
| Non-cash impairments | 0.0 | 0.0 | 0.0 |
| Interest expense | 8.0 | 10.0 | 11.0 |
| Pretax income | 25.0 | 28.0 | 31.0 |
| Income tax expense | 6.0 | 6.0 | 7.0 |
| Net income | 19.0 | 22.0 | 24.0 |
| Operating lease cost | 5.0 | 6.0 | 6.0 |
| Cash & equivalents | 12.0 | 14.0 | 15.0 |
| Receivables | 52.0 | 57.0 | 60.0 |
| Inventory | 61.0 | 66.0 | 70.0 |
| Current assets | 130.0 | 142.0 | 150.0 |
| Total assets | 345.0 | 364.0 | 380.0 |
| Current liabilities | 88.0 | 95.0 | 100.0 |
| Short-term borrowings | 8.0 | 9.0 | 10.0 |
| Current portion of LTD | 10.0 | 11.0 | 12.0 |
| Long-term debt | 135.0 | 140.0 | 140.0 |
| Total liabilities | 235.0 | 243.0 | 250.0 |
| Total equity | 110.0 | 121.0 | 130.0 |
| Retained earnings | 70.0 | 80.0 | 90.0 |
| Cash from operations | 29.0 | 33.0 | 38.0 |
| Capital expenditures | 12.0 | 13.0 | 14.0 |
| Cash taxes paid | 5.0 | 6.0 | 6.0 |
| Dividends paid | 4.0 | 4.0 | 5.0 |

## 3. Credit ratios

| Ratio | FY2022 | FY2023 | FY2024 |
|---|---:|---:|---:|
| EBITDA | 43.0 | 49.0 | 54.0 |
| Total debt | 153.0 | 160.0 | 162.0 |
| Net debt | 141.0 | 146.0 | 147.0 |
| EBITDA margin | 11.8% | 12.3% | 12.9% |
| Debt / EBITDA (x) | 3.56x | 3.27x | 3.00x |
| Net debt / EBITDA (x) | 3.28x | 2.98x | 2.72x |
| EBIT / interest (x) | 4.12x | 3.80x | 3.82x |
| DSCR (x) | 2.39x | 2.33x | 2.35x |
| Fixed-charge coverage (x) | 1.35x | 1.33x | 1.38x |
| Current ratio (x) | 1.48x | 1.49x | 1.50x |
| Free cash flow | 17.0 | 20.0 | 24.0 |
| Debt / equity (x) | 1.39x | 1.32x | 1.25x |

EBITDA and EBIT coverage add back non-cash impairments. n/m = not meaningful (EBITDA or denominator ≤ 0).

## 4. Covenant compliance (FY2024)

| Covenant | Test | Threshold | Actual | Headroom | Status |
|---|---|---:|---:|---:|---|
| Max total leverage | Debt / EBITDA (x) <= | 3.50x | 3.00x | +14.3% | PASS |
| Min interest coverage | EBIT / interest (x) >= | 3.00x | 3.82x | +27.3% | PASS |
| Min fixed-charge coverage | Fixed-charge coverage (x) >= | 1.25x | 1.38x | +10.3% | PASS |
| Min current ratio | Current ratio (x) >= | 1.20x | 1.50x | +25.0% | PASS |

Headroom is the distance to the threshold as a share of the threshold.

## 5. Stress tests

Shock size at which each covenant first breaks, found by root-finding (Brent's method). Rate shock applies to the floating share of debt (60%); revenue decline flexes cost of goods only, so EBITDA falls by the gross margin on lost revenue.

| Covenant | EBITDA decline | Rate shock on floating debt | Revenue decline |
|---|---|---|---|
| Max total leverage | breaks at -14.3% | holds to +2,000 bp | breaks at -6.1% |
| Min interest coverage | breaks at -16.7% | breaks at +309 bp | breaks at -7.1% |
| Min fixed-charge coverage | breaks at -6.9% | breaks at +309 bp | breaks at -3.0% |
| Min current ratio | holds to -100.0% | holds to +2,000 bp | holds to -100.0% |

## 6. Probability of default

**Scorecard** (WoE logistic regression trained on UCI Polish companies bankruptcy (all 5 horizons), 30,383 firm-years): PD **2.17%**, 597 points (600 points = 50:1 odds, 20 points to double the odds).

| Ratio | Definition | Value | Points vs neutral |
|---|---|---:|---:|
| Attr26 | (net profit + depreciation) / total liabilities | 0.144 | -0.1 |
| Attr9 | sales / total assets | 1.105 | +0.7 |
| Attr51 | short-term liabilities / total assets | 0.263 | +2.6 |
| Attr46 | (current assets - inventory) / short-term liabilities | 0.800 | +3.0 |
| Attr42 | operating profit / sales | 0.100 | +3.8 |
| Attr6 | retained earnings / total assets | 0.237 | +13.9 |

**Altman Z''**: 2.92 → safe zone (safe > 2.60, distress < 1.10); PD via logistic map fitted on the same training data: 4.86%.

**Merton**: not applicable – no traded equity price series for this borrower.

**Risk grade 7** (Watch (B+/B)) on an illustrative 10-grade master scale; the grade uses the higher of the scorecard and Merton PDs.

## 7. Data sources and checks

- Excel spread: `sample_borrower_spread.xlsx` (Spread inputs in blue; Ratios and Covenants are live formulas). 36 ratio formula cells recalculated in headless LibreOffice; all match the Python values (relative tolerance 1e-9).
- XBRL tags behind the latest-year spread:

| Line item | Source |
|---|---|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` |
| Cost of goods sold | `CostOfGoodsAndServicesSold` |
| Operating income (EBIT) | `OperatingIncomeLoss` |
| Depreciation & amortization | `DepreciationDepletionAndAmortization` |
| Non-cash impairments | `not reported (0)` |
| Interest expense | `InterestExpense` |
| Pretax income | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` |
| Income tax expense | `IncomeTaxExpenseBenefit` |
| Net income | `NetIncomeLoss` |
| Operating lease cost | `OperatingLeaseCost` |
| Cash & equivalents | `CashAndCashEquivalentsAtCarryingValue` |
| Receivables | `AccountsReceivableNetCurrent` |
| Inventory | `InventoryNet` |
| Current assets | `AssetsCurrent` |
| Total assets | `Assets` |
| Current liabilities | `LiabilitiesCurrent` |
| Short-term borrowings | `ShortTermBorrowings` |
| Current portion of LTD | `LongTermDebtCurrent` |
| Long-term debt | `LongTermDebtNoncurrent` |
| Total liabilities | `Liabilities` |
| Total equity | `StockholdersEquity` |
| Retained earnings | `RetainedEarningsAccumulatedDeficit` |
| Cash from operations | `NetCashProvidedByUsedInOperatingActivities` |
| Capital expenditures | `PaymentsToAcquirePropertyPlantAndEquipment` |
| Cash taxes paid | `IncomeTaxesPaidNet` |
| Dividends paid | `PaymentsOfDividends` |

Caveats: the scorecard was trained on Polish manufacturing firms, so its PD level is a relative-risk signal for US borrowers rather than a calibrated 1-year PD; EBITDA is reported, with only impairment add-backs; stress tests hold taxes, capex and the balance sheet at base values.
