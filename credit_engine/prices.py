"""Daily adjusted close prices: load CSVs (columns: date, adj_close) or download free daily history."""

from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from credit_engine import FIXTURES_DIR, REPO_ROOT

PRICE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range}&interval=1d"
PRICE_DIRS = [REPO_ROOT / "data" / "prices", FIXTURES_DIR / "prices"]


def load_prices(ticker: str, path: Path | None = None) -> pd.DataFrame | None:
    candidates = [Path(path)] if path else [d / f"{ticker}.csv" for d in PRICE_DIRS]
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c, parse_dates=["date"]).dropna()
            return df.sort_values("date").reset_index(drop=True)
    return None


def download_prices(ticker: str, rng: str = "3y") -> list[tuple[str, float]]:
    req = urllib.request.Request(PRICE_URL.format(ticker=ticker, range=rng), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    res = payload["chart"]["result"][0]
    closes = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or res["indicators"]["quote"][0]["close"]
    rows = []
    for ts, c in zip(res["timestamp"], closes):
        if c is not None:
            rows.append((datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(), round(float(c), 4)))
    return rows


def write_prices(rows, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "adj_close"])
        w.writerows(rows)
