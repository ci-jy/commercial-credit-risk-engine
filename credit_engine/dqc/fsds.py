"""Load SEC Financial Statement Data Set quarters (sub/num/pre) and normalise them.

A quarter zip (e.g. ``2026q2.zip`` from https://www.sec.gov/dera/data/financial-statement-data-sets)
holds one row per numeric fact in ``num.txt``. The data set flattens each XBRL
context to:

* ``ddate``    - period end, **rounded to the nearest month end** (yyyymmdd)
* ``qtrs``     - duration in quarters (0 = instant, 4 = annual)
* ``segments`` - dimensions as ``Axis=Member;`` with the ``Axis``/``Member``
                 suffixes and namespace prefixes removed
* ``coreg``    - co-registrant (a legal-entity dimension), blank if none

The quarterly data sets have no calculation linkbase. When a ``cal.txt`` table
is present (the SEC's monthly "Financial Statement and Notes" data sets ship
one, in the same ``adsh grp arc negative ptag pversion ctag cversion`` layout)
it is loaded into ``Quarter.cal`` for DQC_0008; otherwise ``cal`` is None.

Filings that use the IFRS taxonomy are dropped from ``num``: the DQC US rules
do not apply to them.

There is no ``decimals`` column, so :func:`normalise_num` estimates it. A value
reported with ``decimals = d`` is a multiple of ``10**-d``, so its trailing zeros
give a lower bound on ``d``; filers tag (almost) every amount in one unit at the
same precision, so the estimate is ``max(own bound, most common bound for that
filing and unit)``. These flattening choices are the main sources of disagreement
with a full XBRL processor and are documented in ``reports/dqc_results.md``.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from credit_engine import REPO_ROOT

NUM_DTYPES = {"adsh": "category", "tag": "category", "version": "category", "uom": "category",
              "segments": "category", "coreg": "category", "ddate": "int32", "qtrs": "int16"}
NUM_COLS = ["adsh", "tag", "version", "ddate", "qtrs", "uom", "segments", "coreg", "value"]
PRE_COLS = ["adsh", "report", "line", "stmt", "inpth", "tag", "version", "plabel", "negating"]
TAG_COLS = ["tag", "version", "custom", "datatype"]
CAL_COLS = ["adsh", "grp", "arc", "negative", "ptag", "pversion", "ctag", "cversion"]
SUB_COLS = ["adsh", "cik", "name", "sic", "afs", "fye", "form", "period", "fy", "fp", "filed", "instance"]


@dataclass
class Quarter:
    sub: pd.DataFrame
    num: pd.DataFrame | None = None
    pre: pd.DataFrame | None = None
    tag: pd.DataFrame | None = None
    cal: pd.DataFrame | None = None


FSDS_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{quarter}.zip"


def quarter_path(quarter: str) -> Path:
    return REPO_ROOT / "data" / "fsds" / f"{quarter}.zip"


def download_quarter(quarter: str) -> Path:
    """Fetch one data-set quarter (~50-100 MB) into data/fsds/, with the SEC-requested User-Agent."""
    from credit_engine.edgar import user_agent

    target = quarter_path(quarter)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(FSDS_URL.format(quarter=quarter), headers={"User-Agent": user_agent()})
    tmp = target.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=600) as resp:
        tmp.write_bytes(resp.read())
    tmp.rename(target)
    return target


def _open(source: Path, name: str):
    """A file handle for ``name`` inside a quarter zip, or ``name``(.gz) inside a directory."""
    source = Path(source)
    if source.suffix == ".zip":
        return zipfile.ZipFile(source).open(name)
    for cand in (source / f"{name}.gz", source / name):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"{name} not found in {source}")


def _has(source: Path, name: str) -> bool:
    source = Path(source)
    if source.suffix == ".zip":
        return name in zipfile.ZipFile(source).namelist()
    return (source / f"{name}.gz").exists() or (source / name).exists()


def _read(source: Path, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(_open(source, name), sep="\t", quoting=3, encoding="utf-8",
                       encoding_errors="replace", compression="infer" if not str(source).endswith(".zip") else None,
                       **kw)


def load_quarter(source: Path, tables=("sub", "num", "pre", "tag"), adsh: set[str] | None = None) -> Quarter:
    """Read a quarter zip (or a directory of tab-separated files) into pandas."""
    sub = _read(source, "sub.txt", dtype=str, usecols=SUB_COLS)
    if adsh is not None:
        sub = sub[sub.adsh.isin(adsh)]
    q = Quarter(sub=sub.reset_index(drop=True))
    if "num" in tables:
        num = _read(source, "num.txt", dtype=NUM_DTYPES, usecols=NUM_COLS)
        if adsh is not None:
            num = num[num.adsh.isin(adsh)]
        q.num = normalise_num(num, q.sub)
    if "pre" in tables:
        pre = _read(source, "pre.txt", dtype={"adsh": "category", "tag": "category", "version": "category",
                                              "stmt": "category", "plabel": str},
                    usecols=PRE_COLS)
        if adsh is not None:
            pre = pre[pre.adsh.isin(adsh)]
        q.pre = pre.reset_index(drop=True)
    if "tag" in tables:
        q.tag = _read(source, "tag.txt", dtype=str, usecols=TAG_COLS)
    if _has(source, "cal.txt"):
        cal = _read(source, "cal.txt", dtype=str, usecols=CAL_COLS)
        q.cal = cal[cal.adsh.isin(adsh)] if adsh is not None else cal
    return q


def infer_decimals(values: np.ndarray) -> np.ndarray:
    """Largest ``d`` in [-6, 4] such that the value is a multiple of 10**-d (0 -> 4).

    Filers report in units, thousands or millions, so ``d`` is capped at -6.
    """
    v = np.abs(np.asarray(values, dtype=float))
    out = np.full(v.shape, 4, dtype=np.int8)
    scaled = np.round(v * 1e4)
    nz = scaled > 0
    out[~nz] = 4
    for d in range(3, -7, -1):
        step = 10.0 ** (4 - d)
        ok = nz & (np.fmod(scaled, step) == 0)
        out[ok] = d
    return out


def parse_segments(seg: str | float) -> dict[str, str]:
    """``'EquityComponents=CommonStock;ClassOfStock=CommonClassA;'`` -> {axis: member}."""
    if not isinstance(seg, str) or not seg:
        return {}
    out = {}
    for part in seg.strip(";").split(";"):
        if "=" in part:
            axis, member = part.split("=", 1)
            out[axis] = member
    return out


def normalise_num(num: pd.DataFrame, sub: pd.DataFrame) -> pd.DataFrame:
    """Add period, dimension, precision and filing-level columns used by the rules.

    Added columns: ``end``/``start`` (Timestamps; ``start`` is NaT for instants),
    ``ndims`` (number of dimensions incl. a co-registrant), ``dimensionless``,
    ``custom`` (extension concept: version equals the accession number),
    ``inferred_decimals``, ``doc_period`` (sub.period) and ``form``.
    """
    num = num[num.value.notna()]
    # DQC US rules apply to US GAAP filings; IFRS filers have their own ruleset.
    ifrs = set(num.adsh[num.version.astype(str).str.startswith("ifrs")].astype(str))
    num = num[~num.adsh.astype(str).isin(ifrs)].copy()
    num["end"] = pd.to_datetime(num.ddate.astype(str), format="%Y%m%d")
    months = (num.qtrs.astype(int) * 3).to_numpy()
    ym = num.end.dt.year.to_numpy() * 12 + num.end.dt.month.to_numpy() - 1 - months
    start = pd.to_datetime({"year": ym // 12, "month": ym % 12 + 1, "day": 1}) + pd.offsets.MonthEnd(0)
    num["start"] = start.where(months > 0).to_numpy()
    seg = num.segments.astype(object)
    num["ndims"] = seg.map(lambda s: s.count("=") if isinstance(s, str) else 0).astype(int) \
        + num.coreg.notna().astype(int)
    num["dimensionless"] = num.ndims == 0
    num["custom"] = num.version.astype(str) == num.adsh.astype(str)
    num["inferred_decimals"] = infer_decimals(num.value.to_numpy())
    mode = num.groupby(["adsh", "uom"], observed=True).inferred_decimals.agg(lambda s: s.mode().iat[0])
    filing_dec = pd.MultiIndex.from_frame(num[["adsh", "uom"]]).map(mode.to_dict())
    num["decimals"] = np.maximum(num.inferred_decimals.to_numpy(), np.asarray(filing_dec, dtype=float)).astype(int)
    meta = sub.set_index("adsh")
    num["doc_period"] = pd.to_datetime(num.adsh.astype(str).map(meta.period), format="%Y%m%d", errors="coerce")
    num["form"] = num.adsh.astype(str).map(meta.form)
    return num.reset_index(drop=True)


def write_sample(q: Quarter, adsh: set[str], out_dir: Path) -> None:
    """Write the raw rows of ``adsh`` filings as gzipped TSVs (the offline fixture format)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sub = q.sub[q.sub.adsh.isin(adsh)][SUB_COLS]
    sub.to_csv(out_dir / "sub.txt.gz", sep="\t", index=False)
    num = q.num[q.num.adsh.isin(adsh)][NUM_COLS].copy()
    num["value"] = num.value.map(lambda v: f"{v:.4f}")
    num.to_csv(out_dir / "num.txt.gz", sep="\t", index=False)
    if q.pre is not None:
        q.pre[q.pre.adsh.isin(adsh)][PRE_COLS].to_csv(out_dir / "pre.txt.gz", sep="\t", index=False)
    if q.tag is not None:
        used = set(zip(num.tag.astype(str), num.version.astype(str)))
        tag = q.tag[[tv in used for tv in zip(q.tag.tag, q.tag.version)]]
        tag[TAG_COLS].to_csv(out_dir / "tag.txt.gz", sep="\t", index=False)


def read_text_table(text: str) -> pd.DataFrame:
    """Parse a small tab-separated table (used by tests to build planted-error filings)."""
    return pd.read_csv(io.StringIO(text), sep="\t", dtype=str)
