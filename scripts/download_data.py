"""Download public data: UCI Polish bankruptcy data, EDGAR companyfacts and daily prices.

Usage:
    python scripts/download_data.py            # everything into data/
    python scripts/download_data.py --record   # also refresh the trimmed fixtures/ copies

Set CREDIT_ENGINE_USER_AGENT="Your Name your@email" for EDGAR, as the SEC requests.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_engine.edgar import fetch_companyfacts, load_borrowers, trim_companyfacts  # noqa: E402
from credit_engine.polish import ARFF_FILES, POLISH_URL, read_arff  # noqa: E402
from credit_engine.spreading import ALL_TAGS  # noqa: E402

DATA = ROOT / "data"
FIX = ROOT / "fixtures"
PRICE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range}&interval=1d"


def download_polish() -> Path:
    target = DATA / "polish"
    target.mkdir(parents=True, exist_ok=True)
    if all((target / f).exists() for f in ARFF_FILES):
        return target
    with urllib.request.urlopen(POLISH_URL, timeout=120) as resp:
        z = zipfile.ZipFile(io.BytesIO(resp.read()))
    for name in ARFF_FILES:
        (target / name).write_bytes(z.read(name))
    return target


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


def record_polish_fixture(polish_dir: Path, n: int = 8000, seed: int = 7) -> None:
    import pandas as pd

    df = pd.concat([read_arff(polish_dir / f, horizon=i + 1) for i, f in enumerate(ARFF_FILES)], ignore_index=True)
    sample = df.sample(n=n, random_state=seed)
    out = FIX / "polish" / "polish_sample.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False, float_format="%.6g", compression={"method": "gzip", "mtime": 0})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record", action="store_true", help="refresh trimmed fixtures under fixtures/")
    ap.add_argument("--min-year", type=int, default=2019)
    args = ap.parse_args()

    polish_dir = download_polish()
    print(f"UCI Polish bankruptcy data -> {polish_dir}")
    for name, b in load_borrowers().items():
        if not b.get("cik"):
            continue
        data = fetch_companyfacts(b["cik"], cache_dir=DATA / "edgar")
        print(f"EDGAR companyfacts {name} ({data.get('entityName')})")
        rows = download_prices(b["ticker"]) if b.get("ticker") else []
        if rows:
            write_prices(rows, DATA / "prices" / f"{b['ticker']}.csv")
        if args.record:
            trimmed = trim_companyfacts(data, ALL_TAGS, args.min_year)
            with gzip.GzipFile(FIX / "edgar" / f"{name}.json.gz", "wb", mtime=0) as fh:
                fh.write(json.dumps(trimmed, separators=(",", ":")).encode())
            if rows:
                write_prices(rows, FIX / "prices" / f"{b['ticker']}.csv")
    if args.record:
        record_polish_fixture(polish_dir)
        print("fixtures refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
