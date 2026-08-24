"""Fetch and load SEC EDGAR XBRL companyfacts JSON.

The EDGAR API is free and needs no key, but the SEC asks every client to send a
descriptive User-Agent with a contact address. Set ``CREDIT_ENGINE_USER_AGENT``
to your own "Name email" string before fetching.
"""

from __future__ import annotations

import gzip
import json
import os
import time
import urllib.request
from pathlib import Path

from credit_engine import FIXTURES_DIR

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
DEFAULT_USER_AGENT = "commercial-credit-risk-engine/0.1 (contact@example.com)"
EDGAR_FIXTURE_DIR = FIXTURES_DIR / "edgar"


def user_agent() -> str:
    return os.environ.get("CREDIT_ENGINE_USER_AGENT", DEFAULT_USER_AGENT)


def fetch_companyfacts(cik: int | str, cache_dir: Path | None = None, retries: int = 3) -> dict:
    """Download companyfacts for a CIK, optionally caching the raw JSON."""
    cik = int(cik)
    if cache_dir is not None:
        cached = Path(cache_dir) / f"CIK{cik:010d}.json"
        if cached.exists():
            return json.loads(cached.read_text())
    req = urllib.request.Request(COMPANYFACTS_URL.format(cik=cik), headers={"User-Agent": user_agent()})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
            break
        except Exception as err:  # network errors and HTTP 429/5xx
            last_err = err
            time.sleep(1.0 + attempt)
    else:
        raise RuntimeError(f"could not fetch companyfacts for CIK {cik}: {last_err}")
    data = json.loads(raw)
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        (Path(cache_dir) / f"CIK{cik:010d}.json").write_bytes(raw)
    return data


def trim_companyfacts(data: dict, tags: set[str], min_year: int) -> dict:
    """Keep only 10-K facts for the tags the spreader uses, ending on/after ``min_year``."""
    out = {"cik": data.get("cik"), "entityName": data.get("entityName"), "facts": {}}
    for taxonomy in ("us-gaap", "dei"):
        kept = {}
        for tag, body in data.get("facts", {}).get(taxonomy, {}).items():
            if taxonomy == "us-gaap" and tag not in tags:
                continue
            units = {}
            for unit, facts in body.get("units", {}).items():
                rows = [
                    f for f in facts
                    if (taxonomy == "dei" or f.get("form") in ("10-K", "10-K/A"))
                    and int(f.get("end", "0000")[:4]) >= min_year
                ]
                if rows:
                    units[unit] = rows
            if units:
                kept[tag] = {"units": units}
        out["facts"][taxonomy] = kept
    return out


def load_fixture(name: str) -> dict:
    """Load a recorded companyfacts fixture by name (e.g. ``hasbro``)."""
    for candidate in (EDGAR_FIXTURE_DIR / f"{name}.json.gz", EDGAR_FIXTURE_DIR / f"{name}.json"):
        if candidate.exists():
            if candidate.suffix == ".gz":
                with gzip.open(candidate, "rt") as fh:
                    return json.load(fh)
            return json.loads(candidate.read_text())
    raise FileNotFoundError(f"no EDGAR fixture named {name!r} in {EDGAR_FIXTURE_DIR}")


def load_borrowers() -> dict:
    """Borrower registry: fixture name -> CIK, ticker and covenant package."""
    return json.loads((FIXTURES_DIR / "borrowers.json").read_text())
