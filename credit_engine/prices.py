"""Load daily adjusted close CSVs (columns: date, adj_close)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit_engine import FIXTURES_DIR, REPO_ROOT

PRICE_DIRS = [REPO_ROOT / "data" / "prices", FIXTURES_DIR / "prices"]


def load_prices(ticker: str, path: Path | None = None) -> pd.DataFrame | None:
    candidates = [Path(path)] if path else [d / f"{ticker}.csv" for d in PRICE_DIRS]
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c, parse_dates=["date"]).dropna()
            return df.sort_values("date").reset_index(drop=True)
    return None
