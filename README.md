# Commercial Credit Risk Engine

Gives commercial-banking and credit-research analysts a full first-pass credit memo for a public borrower: it spreads SEC XBRL filings, tests covenants under stress, and estimates probability of default. Its bankruptcy scorecard reaches a **held-out AUC of 0.749 vs 0.690 for Altman Z''** (ΔAUC +0.059, 95% CI [+0.045, +0.073]) on 43,405 real firm-years.

![PD model benchmark](docs/benchmark.png)

| Model (held-out 30%, 627 bankruptcies) | AUC [95% CI] | KS | Brier | ECE |
|---|---|---|---|---|
| WoE scorecard (6 ratios a US spread can supply) | 0.749 [0.730, 0.768] | 0.418 | 0.044 | 0.008 |
| Altman Z'' baseline | 0.690 [0.668, 0.712] | 0.294 | 0.045 | 0.016 |
| Gradient boosting, same 17 candidate ratios | 0.838 [0.824, 0.853] | 0.536 | 0.041 | 0.007 |
| Gradient boosting, all 64 ratios | 0.971 [0.966, 0.976] | 0.817 | 0.019 | 0.009 |

Full tables with CIs for every metric and decile calibration: [reports/benchmark.md](reports/benchmark.md).

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[test]"
CREDIT_ENGINE_USER_AGENT="Your Name you@example.com" credit-engine memo --cik 106640 --out out/   # Whirlpool, live from EDGAR
credit-engine memo --fixture hasbro --out out/                                                    # offline, recorded filing
```

For the Excel recalculation check, install LibreOffice Calc: `sudo apt-get install -y --no-install-recommends libreoffice-calc`. Without it, the memo is still written and the workbook simply calculates when opened.

Each run writes `out/<borrower>_memo.md` and `out/<borrower>_spread.xlsx`. Finished examples for Hasbro, Whirlpool, Kohl's, Mattel and Macy's (plus an illustrative private borrower) are in [examples/](examples/).

## Why

A credit analyst spreads a borrower's statements into a standard template, computes leverage and coverage, checks covenant headroom, and judges default risk. This is usually done by hand in spreadsheets, and the default judgment is rarely checked against outcomes. This engine automates the spread from public XBRL data, finds the exact shock that breaks each covenant, and backs its PD with a model measured against real bankruptcies and the Altman Z'' baseline.

## Reading a memo

| Section | What it tells you |
|---|---|
| 1. Summary | Risk grade (1–10 master scale), leverage/coverage headline, covenant pass count, the first covenant to break under each stress, Z'' zone and market-implied PD. |
| 2. Financial spread | 26 standardized line items for the last 4 fiscal years, in $M. |
| 3. Credit ratios | EBITDA, Debt/EBITDA, net leverage, EBIT/interest, DSCR, fixed-charge coverage, current ratio, free cash flow, debt/equity. `n/m` when EBITDA ≤ 0. |
| 4. Covenant compliance | Threshold, actual, headroom (% of threshold) and PASS/BREACH for the latest year. Covenants come from `fixtures/borrowers.json` or `--covenants my_covenants.json`. |
| 5. Stress tests | The EBITDA decline, floating-rate shock (bp) and revenue decline at which each covenant breaks. |
| 6. Probability of default | Scorecard PD and points with per-ratio contributions; Altman Z'' and zone; Merton inputs (equity value, 252-day volatility, KMV default point) and solved asset value/volatility, distance-to-default and PD. |
| 7. Data sources and checks | The XBRL tag behind every latest-year cell, and the LibreOffice formula-parity result for the Excel file. |

In the Excel spread, blue cells on `Spread` are inputs. `Ratios` and `Covenants` are live formulas, so an analyst can overwrite an input (for example, an EBITDA adjustment) and watch headroom update.

## How it works

- **Spreading** (`credit_engine/spreading.py`): reads EDGAR `companyfacts` JSON (free; only a User-Agent is needed). Each line item has an ordered list of US-GAAP tags and derived fallbacks, e.g. interest expense → `InterestExpense` → `InterestExpenseNonoperating` → −`InterestIncomeExpenseNet` → `InterestPaidNet`. Only 10-K facts are used, with flows of 350–380 days and instants within 10 days of the year-end. Restated values from later filings take precedence, and retail 52/53-week years are labelled the way the companies label them. Every cell records its source tag.
- **Ratios and covenants** (`ratios.py`): EBITDA adds back non-cash impairments, a standard covenant add-back. Formulas are in the module docstring.
- **Stress** (`stress.py`): each scenario is a function of shock size. A grid brackets the first sign change of covenant headroom, and `scipy.optimize.brentq` refines it to 1e-10.
- **PD scorecard** (`scorecard.py`): the scorecard is trained on the UCI Polish companies bankruptcy data (`polish.py`), using only the 17 ratios that can also be computed from a US spread. Features are quantile-binned, and adjacent bins are merged until they are monotonic with at least 5% of rows each. Weight-of-evidence and information value come with Laplace smoothing. Features are then filtered on IV ≥ 0.02 and |WoE correlation| ≤ 0.8, and a sign-checked logistic regression is fitted. Points are scaled to 600 at 50:1 odds, with 20 points to double the odds.
- **Baselines** (`altman.py`, `benchmark.py`): Altman Z'' = 6.56·WC/TA + 3.26·RE/TA + 6.72·EBIT/TA + 1.05·BVE/TL, mapped to a PD by a one-feature logistic fit. scikit-learn `HistGradientBoostingClassifier` is fitted on the same 17 ratios and on all 64.
- **Evaluation** (`metrics.py`): stratified 70/30 split. AUC, KS, Brier and ECE use 1,000 stratified bootstrap resamples, plus paired bootstrap AUC differences.
- **Merton** (`merton.py`): solves E = V·N(d1) − D·e^(−rT)·N(d2) and σE·E = N(d1)·σV·V jointly in log space with `scipy.optimize.root`. Equity value is the latest price × shares outstanding (dei), and σE comes from 252 daily log returns.
- **Excel** (`excel.py`): openpyxl writes formula cells, headless LibreOffice recalculates them, and every ratio cell is compared with the Python value (relative tolerance 1e-9).

## Data

- UCI Polish companies bankruptcy data (Tomczak, Zięba et al., 2016; [UCI #365](https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data), CC BY 4.0).
- SEC EDGAR XBRL [companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
- Free daily adjusted closes (Yahoo Finance chart endpoint, saved as `date,adj_close` CSV). `--prices my.csv` accepts any CSV in that format.

`python scripts/download_data.py` fetches all of it into `data/`; `--record` refreshes the small trimmed copies in `fixtures/` that make every test and the acceptance commands run offline. The offline benchmark uses a committed 8,000-row random sample of the Polish data. `python scripts/plot_results.py` regenerates the figure from `reports/*.csv`.

## Tests

```bash
python3 -m pytest -q                                              # 80 tests, ~6 s
python3 -m credit_engine benchmark --offline-fixtures --quick     # benchmark on the committed sample
python3 -m credit_engine memo --fixture sample_borrower --out out/
```

The suite checks:
- FY2023 revenue, operating income and net income for 5 recorded filers against their 10-Ks, plus tag priority and fallbacks.
- Every ratio, headroom and stress breakpoint for the round-number sample borrower against hand-worked closed forms.
- WoE/IV against a hand-computed two-bin case, plus binning monotonicity.
- The Merton round-trip on 40 random synthetic firms to 1e-6, and the Hull textbook example.
- Excel formula parity after LibreOffice recalculation; these tests are skipped only if `soffice` is not installed.

## Design notes and limitations

- **Population mismatch.** The scorecard learns from Polish (mostly manufacturing) firms, so its PD is a relative-risk signal for US borrowers, not a calibrated 1-year US PD. The memo grade therefore takes the more conservative of the scorecard and Merton PDs.
- **Gradient boosting on 64 ratios scores far higher**, but it uses ratios a GAAP spread cannot supply. The Polish files also repeat firms across horizons without IDs, so a random split likely flatters flexible models. The scorecard is kept for transparency and portability.
- **Reported EBITDA.** EBITDA is reported, with impairment add-backs only. There are no other management adjustments, and lease cost uses `OperatingLeaseCost` where it is tagged.
- **Stress simplifications.** Stress holds cash taxes, capex and the balance sheet at base values. The floating-rate share of debt is an input, not something read from filings.
- **Spreading coverage.** Spreading covers common commercial and industrial filers. Banks, insurers and REITs use different statement structures and are out of scope.
- **Illustrative scale.** The 10-grade master scale and default covenant thresholds are illustrative and are not any institution's methodology.
