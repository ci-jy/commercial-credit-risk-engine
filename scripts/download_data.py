"""Download public data: UCI Polish bankruptcy data, EDGAR companyfacts and daily prices.

Usage:
    python scripts/download_data.py            # everything into data/
    python scripts/download_data.py --record   # also refresh the trimmed fixtures/ copies
    python scripts/download_data.py --fsds 2026q2   # only an SEC Financial Statement Data Set quarter

Set CREDIT_ENGINE_USER_AGENT="Your Name your@email" for EDGAR, as the SEC requests.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_engine.edgar import fetch_companyfacts, load_borrowers, trim_companyfacts, user_agent  # noqa: E402
from credit_engine.prices import download_prices, write_prices  # noqa: E402
from credit_engine.polish import ARFF_FILES, POLISH_URL, read_arff  # noqa: E402
from credit_engine.spreading import ALL_TAGS  # noqa: E402

DATA = ROOT / "data"
FIX = ROOT / "fixtures"


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


def record_polish_fixture(polish_dir: Path, n: int = 8000, seed: int = 7) -> None:
    import pandas as pd

    df = pd.concat([read_arff(polish_dir / f, horizon=i + 1) for i, f in enumerate(ARFF_FILES)], ignore_index=True)
    sample = df.sample(n=n, random_state=seed)
    out = FIX / "polish" / "polish_sample.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False, float_format="%.6g", compression={"method": "gzip", "mtime": 0})


FSDS_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{quarter}.zip"


def download_fsds(quarter: str) -> Path:
    """One SEC Financial Statement Data Set quarter (sub/num/pre/tag, ~50-100 MB zipped)."""
    target = DATA / "fsds" / f"{quarter}.zip"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(FSDS_URL.format(quarter=quarter), headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=600) as resp:
        target.write_bytes(resp.read())
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record", action="store_true", help="refresh trimmed fixtures under fixtures/")
    ap.add_argument("--min-year", type=int, default=2019)
    ap.add_argument("--fsds", metavar="QUARTER", help="download only this Financial Statement Data Set quarter")
    args = ap.parse_args()
    if args.fsds:
        print(f"SEC Financial Statement Data Set -> {download_fsds(args.fsds)}")
        return 0

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
