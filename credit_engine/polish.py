"""UCI Polish companies bankruptcy data (Tomczak et al., 2016).

43,405 firm-years from the Emerging Markets Information Service, 64 financial
ratios each, labelled with whether the company went bankrupt within the
forecasting horizon (1-5 years). Source:
https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_engine import FIXTURES_DIR, REPO_ROOT

POLISH_URL = "https://archive.ics.uci.edu/static/public/365/polish+companies+bankruptcy+data.zip"
ARFF_FILES = ["1year.arff", "2year.arff", "3year.arff", "4year.arff", "5year.arff"]
FIXTURE_PATH = FIXTURES_DIR / "polish" / "polish_sample.csv.gz"
DATA_DIR = REPO_ROOT / "data" / "polish"

ATTR_COLS = [f"Attr{i}" for i in range(1, 65)]

# Ratios that can also be computed from a standard US spread, so a scorecard
# trained on them can score a borrower in a memo. "Gross profit" in the Polish
# definitions is profit before tax.
SPREAD_FEATURES = {
    "Attr1": "net profit / total assets",
    "Attr2": "total liabilities / total assets",
    "Attr3": "working capital / total assets",
    "Attr4": "current assets / short-term liabilities",
    "Attr6": "retained earnings / total assets",
    "Attr7": "EBIT / total assets",
    "Attr8": "book value of equity / total liabilities",
    "Attr9": "sales / total assets",
    "Attr10": "equity / total assets",
    "Attr16": "(pretax profit + depreciation) / total liabilities",
    "Attr18": "pretax profit / total assets",
    "Attr23": "net profit / sales",
    "Attr26": "(net profit + depreciation) / total liabilities",
    "Attr42": "operating profit / sales",
    "Attr46": "(current assets - inventory) / short-term liabilities",
    "Attr50": "current assets / total liabilities",
    "Attr51": "short-term liabilities / total assets",
}


def read_arff(path: Path, horizon: int) -> pd.DataFrame:
    rows = []
    in_data = False
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        if line.lower().startswith("@data"):
            in_data = True
            continue
        if in_data:
            rows.append(line.split(","))
    df = pd.DataFrame(rows, columns=ATTR_COLS + ["class"])
    df = df.replace("?", np.nan)
    df[ATTR_COLS] = df[ATTR_COLS].astype(float)
    df["class"] = df["class"].astype(int)
    df.insert(0, "horizon", horizon)
    return df


def load_polish(offline: bool = False) -> pd.DataFrame:
    """Full dataset from data/polish (see scripts/download_data.py) or the committed sample."""
    if not offline and all((DATA_DIR / f).exists() for f in ARFF_FILES):
        return pd.concat([read_arff(DATA_DIR / f, i + 1) for i, f in enumerate(ARFF_FILES)], ignore_index=True)
    if not offline:
        raise FileNotFoundError(
            f"full Polish data not found in {DATA_DIR}; run scripts/download_data.py or use --offline-fixtures"
        )
    return pd.read_csv(FIXTURE_PATH)


def spread_to_polish_ratios(y: dict[str, float]) -> dict[str, float]:
    """Compute the SPREAD_FEATURES ratios from one fiscal year of a standardized spread."""
    ta, tl = y["total_assets"], y["total_liabilities"]
    ca, cl = y["current_assets"], y["current_liabilities"]
    ebit = y["operating_income"]
    pretax, ni, da = y["pretax_income"], y["net_income"], y["depreciation_amortization"]
    rev, eq = y["revenue"], y["total_equity"]

    def div(a, b):
        return float(a / b) if b not in (0, 0.0) and np.isfinite(b) else np.nan

    return {
        "Attr1": div(ni, ta),
        "Attr2": div(tl, ta),
        "Attr3": div(ca - cl, ta),
        "Attr4": div(ca, cl),
        "Attr6": div(y["retained_earnings"], ta),
        "Attr7": div(ebit, ta),
        "Attr8": div(eq, tl),
        "Attr9": div(rev, ta),
        "Attr10": div(eq, ta),
        "Attr16": div(pretax + da, tl),
        "Attr18": div(pretax, ta),
        "Attr23": div(ni, rev),
        "Attr26": div(ni + da, tl),
        "Attr42": div(ebit, rev),
        "Attr46": div(ca - y["inventory"], cl),
        "Attr50": div(ca, tl),
        "Attr51": div(cl, ta),
    }
