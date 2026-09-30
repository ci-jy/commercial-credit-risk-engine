import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from credit_engine.dqc.fsds import NUM_DTYPES, Quarter, normalise_num  # noqa: E402

ADSH = "0000000001-26-000001"


def fact(tag, value, ddate=20251231, qtrs=0, segments=None, uom="USD", adsh=ADSH, version="us-gaap/2025", coreg=None):
    return {"adsh": adsh, "tag": tag, "version": version, "ddate": ddate, "qtrs": qtrs, "uom": uom,
            "segments": segments, "coreg": coreg, "value": float(value)}


# Unrelated facts that make the planted filing look like a real one reported in
# thousands of dollars and in whole shares (they set its typical precision).
BACKGROUND = [
    {"tag": "OtherAssetsNoncurrent", "ddate": d, "uom": "USD", "value": v}
    for d, v in [(20141231 + 10000 * i, 1_234_000 + 1_111_000 * i) for i in range(8)]
] + [
    {"tag": "WeightedAverageNumberOfSharesOutstandingBasic", "ddate": d, "uom": "shares", "value": v}
    for d, v in [(20201231, 1_234_567), (20211231, 2_345_671), (20221231, 3_456_781)]
]


def build_quarter(facts: list[dict], form: str = "10-K", period: int = 20251231, extra_subs=(), tags=None,
                  background: bool = True) -> Quarter:
    """A one-filing quarter from planted facts, normalised like a real data set."""
    if background:
        facts = list(facts) + [fact(b["tag"], b["value"], ddate=b["ddate"], qtrs=4, uom=b["uom"]) for b in BACKGROUND]
    subs = [{"adsh": ADSH, "cik": "1", "name": "PLANTED CO", "sic": "1000", "afs": "1-LAF", "fye": "1231",
             "form": form, "period": str(period), "fy": "2025", "fp": "FY", "filed": "20260301", "instance": "x.xml"}]
    subs += list(extra_subs)
    sub = pd.DataFrame(subs).astype(str)
    num = pd.DataFrame(facts)
    num = num.astype({k: v for k, v in NUM_DTYPES.items() if k in num})
    tag = pd.DataFrame(tags or [], columns=["tag", "version", "custom", "datatype"]).astype(str)
    return Quarter(sub=sub, num=normalise_num(num, sub), pre=None, tag=tag)


@pytest.fixture
def quarter():
    return build_quarter
