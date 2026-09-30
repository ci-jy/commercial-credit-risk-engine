# Bulk DQC screen vs Arelle + XULE: results (2026q2)

Sample: **45 10-K/10-Q filings** from the SEC Financial Statement Data Set 2026q2 (15 10-K, 30 10-Q). Most were drawn at random (seed 7); the rest were added because the bulk screen flagged them, so that every rule that fires has real cases to compare. Reference: Arelle (`arelle-release`) with the XULE plugin and the official DQC v30 compiled ruleset for each filing's US GAAP year. Findings are aligned on (filing, rule, concept, period end, dimensions).

**Overall: 39 of 43 findings matched (90.7%); 0 unexplained disagreements.**

## Agreement per rule

| Rule | Title | Matched | Bulk only | Arelle only | Finding agreement | Filing agreement |
|---|---|---|---|---|---|---|
| DQC_0001 | Axis with inappropriate members | 2 | 1 | 0 | 66.7% | 97.8% |
| DQC_0004 | Element values are equal (e.g. assets = liabilities + equity) | 11 | 0 | 0 | 100.0% | 100.0% |
| DQC_0005 | Context dates after period end (cover shares, subsequent events, forecasts) | 0 | 0 | 0 | 100.0% | 100.0% |
| DQC_0009 | Element A must be <= element B (e.g. shares outstanding <= issued) | 2 | 1 | 0 | 66.7% | 97.8% |
| DQC_0013 | Negative tax-rate reconciliation items when pre-tax income is positive | 0 | 0 | 0 | 100.0% | 100.0% |
| DQC_0014 | Negative values with no dimensions (goodwill, revenue, cost of revenue...) | 1 | 0 | 0 | 100.0% | 100.0% |
| DQC_0015 | Negative values for elements that cannot be negative | 8 | 0 | 2 | 80.0% | 100.0% |
| DQC_0091 | Percentage items greater than 1,000% (value > 10) | 0 | 0 | 0 | 100.0% | 100.0% |
| DQC_0095 | Scale of cover-page shares outstanding vs balance-sheet shares | 0 | 0 | 0 | 100.0% | 100.0% |
| DQC_0125 | Lease cost cannot be negative (unless sublease income is reported) | 0 | 0 | 0 | 100.0% | 100.0% |
| DQC_0194 | Negative equity movements on the equity components axis | 4 | 0 | 0 | 100.0% | 100.0% |
| DQC_0195 | Invalid member on the equity components axis for the line item | 11 | 0 | 0 | 100.0% | 100.0% |

*Finding agreement* = matched / (matched + bulk only + Arelle only); 100% when neither side reports anything. *Filing agreement* = share of sample filings where both tools agree on whether the rule fires.

## Disagreements and root causes

| Rule | Reported by | Count | Category | Root cause |
|---|---|---|---|---|
| DQC_0001 | bulk only | 1 | flattening limitation | The filer's definition linkbase places ttc:OtherActivitiesMember under us-gaap:MaterialReconcilingItemsMember. DQC_0001.70 allows extension members there. The data sets do not carry the definition linkbase, so the bulk screen cannot see the member hierarchy. |
| DQC_0009 | bulk only | 1 | flattening limitation | CommonStockSharesIssued is 1,921,809 at 2026-03-31 (context c2). A second fact of 1.358 shares, from a preferred conversion dated 2026-04-06 (context c54), rounds to the same month end. The data set keeps only the 1.358 value, so outstanding appears to exceed issued. |
| DQC_0015 | Arelle only | 1 | flattening limitation | Arelle flags a negative -25,170,000 for this cash-flow supplemental fact. The fact is missing from the data set's num table for this filing, so the bulk screen never sees it. |
| DQC_0015 | Arelle only | 1 | flattening limitation | Arelle flags us-gaap:Capital = -1,600,000 (a broker-dealer regulatory capital fact). The fact is missing from the data set's num table for this filing, so the bulk screen never sees it. |

Every disagreement, with filing and concept: [dqc_disagreements.csv](dqc_disagreements.csv).

## Bugs found by the differential runs (fixed)

| Where | What was wrong and how it was fixed |
|---|---|
| DQC_0004 | Missing components were counted as zero, so Assets = AssetsCurrent + AssetsNoncurrent fired for every filer that does not tag AssetsNoncurrent. XULE binds every factset in the assertion, so a check runs only when all its components are reported (Arelle never fired on these). |
| DQC_0005 | Subsequent-event facts dated in the first two weeks after the period end (e.g. 2026-04-03 to 2026-04-08 for a 2026-03-31 10-Q) were rounded onto the period end and flagged. 48 and 49 now fire only for dates clearly before the period end. |
| DQC_0194 | Any member containing 'NoncontrollingInterest' was treated as an NCI member, including a filer's own lng:RedeemableNoncontrollingInterestMember; the DQC list holds US GAAP members only. |
| DQC_0009 and others | When month-end rounding merged two contexts with different values (e.g. 2026-03-31 and 2026-04-06), the pivot compared whichever came first. Such ambiguous context/concept pairs are now left out of the comparison. |
| harness | DQC_0001 was aligned per fact, while the bulk rule reports one finding per (axis, member). Arelle's findings are now grouped by the member named in their message. |
| harness | Arelle nests context dimensions under a 'dimensions' property; the first parser dropped them, so dimensional findings could not be aligned. |

## Runtime

- Arelle + XULE + DQC ruleset: **median 27.1 s per filing** (mean 32.1 s, min 20.2 s, max 97.9 s, 45 filings, one process, warm taxonomy cache). This runs all ~200 DQC rules on the full XBRL instance.
- Bulk screen, whole quarter: **8.2 s to load + 13.7 s to screen = 21.9 s for 7,421 US GAAP filings** (3,194,213 facts), i.e. 3.0 ms per filing.
- At Arelle's median, the same quarter would take about **56 CPU-hours** (9,202x the bulk time). The bulk screen only runs 12 rules, so this compares workflows, not rule-for-rule speed.

## Whole-quarter findings (2026q2)

| Rule | Findings | Filings flagged | Screen time (s) |
|---|---|---|---|
| DQC_0001 | 14 | 11 | 0.54 |
| DQC_0004 | 40 | 22 | 1.23 |
| DQC_0005 | 0 | 0 | 5.65 |
| DQC_0009 | 19 | 13 | 0.40 |
| DQC_0013 | 0 | 0 | 0.53 |
| DQC_0014 | 2 | 1 | 0.18 |
| DQC_0015 | 126 | 53 | 0.19 |
| DQC_0091 | 0 | 0 | 2.68 |
| DQC_0095 | 0 | 0 | 0.75 |
| DQC_0125 | 0 | 0 | 0.04 |
| DQC_0194 | 47 | 24 | 0.39 |
| DQC_0195 | 199 | 67 | 1.16 |

Excel exceptions workbook: [dqc_exceptions_2026q2.xlsx](dqc_exceptions_2026q2.xlsx) (summary sheet linking to one sheet per rule; each accession number links to the filing on EDGAR).

## Impact on the engine's credit ratios

Of 447 findings, **6 flag a value the engine's spread actually uses** (dimensionless, current period, with a suggested correction) in 6 filings. Applying the suggested correction changes at least one ratio by more than 0.5% for **0** of them, and a leverage or coverage ratio for **0**.

| Ratio | Findings hitting the spread | Ratio changed | Median abs. change | Max abs. change |
|---|---|---|---|---|
| debt_to_ebitda | 6 | 0 | n/a | n/a |
| net_leverage | 6 | 0 | n/a | n/a |
| interest_coverage | 6 | 0 | n/a | n/a |
| dscr | 6 | 0 | n/a | n/a |
| fccr | 6 | 0 | n/a | n/a |
| current_ratio | 6 | 0 | n/a | n/a |
| debt_to_equity | 6 | 0 | n/a | n/a |

Changes between a finite ratio and n/m (e.g. EBITDA turning positive) count as changed but are left out of the % columns. Detail: [dqc_ratio_impact_detail.csv](dqc_ratio_impact_detail.csv).
