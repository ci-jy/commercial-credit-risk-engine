"""Differential comparison of the bulk screen against Arelle + XULE + the official DQC ruleset.

Findings are aligned on ``(filing, rule, concept, period end, dimensions)``.
Arelle reports real context dates and namespace-qualified dimensions, so they
are first normalised to the data-set form: the period end is rounded to the
nearest month end and ``us-gaap:StatementEquityComponentsAxis =
us-gaap:CommonStockMember`` becomes ``EquityComponents=CommonStock``.

Every finding reported by only one side is a *disagreement*. Each one gets a
root cause from the reviewed ``fixtures/dqc/root_causes.json``: a list of
``{"match": {column: value, ...}, "category": ..., "root_cause": ...}`` entries
(first match wins; ``category`` is one of :data:`CATEGORIES`). Anything left
over is reported as ``unexplained``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from credit_engine import FIXTURES_DIR
from credit_engine.dqc import RULE_IDS

DQC_FIXTURES = FIXTURES_DIR / "dqc"
ARELLE_DIR = DQC_FIXTURES / "arelle"
ROOT_CAUSE_FILE = DQC_FIXTURES / "root_causes.json"
CATEGORIES = ("bug", "flattening limitation", "rule-version difference")
KEY = ["adsh", "rule", "concept", "ddate", "segments"]


def _strip(name: str, suffix: str) -> str:
    name = name.split(":", 1)[-1]
    return name[: -len(suffix)] if name.endswith(suffix) else name


def month_end(date_str: str) -> int:
    """Round a date to the nearest month end, as the data sets do (yyyymmdd int)."""
    if not date_str:
        return 0
    d = pd.Timestamp(date_str)
    if d.day < 15:
        d = d - pd.offsets.MonthEnd(1)
    else:
        d = d + pd.offsets.MonthEnd(0)
    return int(d.strftime("%Y%m%d"))


def normalise_dims(dims: dict[str, str]) -> str:
    """``{'us-gaap:StatementEquityComponentsAxis': 'us-gaap:CommonStockMember'}`` -> ``EquityComponents=CommonStock;``.

    Data sets drop the ``Statement`` prefix of the equity components axis and
    the ``Axis``/``Member`` suffixes; dimensions are sorted by axis name.
    """
    parts = []
    for axis, member in dims.items():
        a = _strip(axis, "Axis")
        if a == "StatementEquityComponents":
            a = "EquityComponents"
        if a.startswith("Statement"):
            a = a[len("Statement"):]
        parts.append(f"{a}={_strip(member, 'Member')}")
    return "".join(f"{p};" for p in sorted(parts))


def load_arelle(adshs: list[str] | None = None, rules: list[str] | None = None,
                arelle_dir: Path = ARELLE_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(findings, runs) from the committed per-filing Arelle outputs."""
    rules = set(rules or RULE_IDS)
    rows, runs = [], []
    for path in sorted(Path(arelle_dir).glob("*.json")):
        d = json.loads(path.read_text())
        if adshs is not None and d["adsh"] not in adshs:
            continue
        runs.append({"adsh": d["adsh"], "ruleset": d["ruleset"], "runtime_s": d["runtime_s"],
                     "n_findings_all_rules": len(d["findings"])})
        for f in d["findings"]:
            if f["rule"] not in rules:
                continue
            concept, ddate, segments = f["concept"], month_end(f["end"]), normalise_dims(f["dims"])
            if f["rule"] == "DQC_0001":
                # one bulk finding per (axis, member); Arelle reports each fact using it
                m = re.search(r"the (\w+?)Axis and the unallowable member (\w+?)Member", f["message"])
                if m:
                    axis = m.group(1)[len("Statement"):] if m.group(1).startswith("Statement") else m.group(1)
                    concept, ddate, segments = f"{axis}={m.group(2)}", 0, ""
            rows.append({"adsh": d["adsh"], "rule": f["rule"], "element_id": f["element_id"],
                         "concept": concept, "ddate": ddate, "segments": segments, "value": f["value"],
                         "message": f["message"]})
    cols = ["adsh", "rule", "element_id", "concept", "ddate", "segments", "value", "message"]
    return pd.DataFrame(rows, columns=cols), pd.DataFrame(runs)


def disagreement_key(row) -> str:
    return "|".join(str(row[k]) for k in KEY)


def align(bulk: pd.DataFrame, arelle: pd.DataFrame) -> pd.DataFrame:
    """Outer join of the two finding sets on :data:`KEY`; ``side`` is both/bulk/arelle."""
    b = bulk.copy()
    b["segments"] = b.segments.fillna("").map(lambda s: "".join(f"{p};" for p in sorted(filter(None, s.split(";")))))
    b = b.drop_duplicates(KEY)[KEY + ["element_id", "value", "suggested", "message"]]
    a = arelle.drop_duplicates(KEY)[KEY + ["element_id", "value", "message"]]
    a = a.rename(columns={"element_id": "arelle_element_id", "value": "arelle_value", "message": "arelle_message"})
    b["ddate"] = b.ddate.astype(int)
    a["ddate"] = a.ddate.astype(int)
    m = b.merge(a, on=KEY, how="outer", indicator=True)
    m["side"] = m["_merge"].map({"both": "both", "left_only": "bulk", "right_only": "arelle"}).astype(str)
    m["key"] = m.apply(disagreement_key, axis=1)
    return m.drop(columns="_merge")


def load_root_causes(path: Path = ROOT_CAUSE_FILE) -> list[dict]:
    if not Path(path).exists():
        return []
    return json.loads(Path(path).read_text())


def _matches(row: dict, match: dict) -> bool:
    for col, want in match.items():
        have = str(row.get(col, ""))
        if col.endswith("_contains"):
            if want not in str(row.get(col[: -len("_contains")], "")):
                return False
        elif have != str(want):
            return False
    return True


def explain(aligned: pd.DataFrame, root_causes: list[dict] | None = None) -> pd.DataFrame:
    """Attach ``category`` and ``root_cause`` to each one-sided finding."""
    root_causes = load_root_causes() if root_causes is None else root_causes
    out = aligned.copy()
    cats, causes = [], []
    for row in out.to_dict("records"):
        if row["side"] == "both":
            cats.append("")
            causes.append("")
            continue
        rc = next((r for r in root_causes if _matches(row, r["match"])), None)
        if rc:
            assert rc["category"] in CATEGORIES, rc
            cats.append(rc["category"])
            causes.append(rc["root_cause"])
        else:
            cats.append("unexplained")
            causes.append("")
    out["category"] = cats
    out["root_cause"] = causes
    return out


def agreement_by_rule(explained: pd.DataFrame, n_filings: int, rules: list[str] | None = None) -> pd.DataFrame:
    """Per rule: matched / bulk-only / Arelle-only findings and two agreement rates.

    * ``finding_agreement`` = matched / (matched + bulk-only + Arelle-only)
    * ``filing_agreement``  = share of sample filings where both tools agree on
      whether the rule fires at all
    """
    rows = []
    for rid in rules or RULE_IDS:
        e = explained[explained.rule == rid]
        both, bulk, are = (e.side == "both").sum(), (e.side == "bulk").sum(), (e.side == "arelle").sum()
        fb = set(e[e.side.isin(["both", "bulk"])].adsh)
        fa = set(e[e.side.isin(["both", "arelle"])].adsh)
        rows.append({
            "rule": rid, "matched": int(both), "bulk_only": int(bulk), "arelle_only": int(are),
            "finding_agreement": both / (both + bulk + are) if (both + bulk + are) else 1.0,
            "filings_flagged_bulk": len(fb), "filings_flagged_arelle": len(fa),
            "filing_agreement": 1 - len(fb ^ fa) / n_filings if n_filings else 1.0,
            "unexplained": int((e.category == "unexplained").sum()),
        })
    return pd.DataFrame(rows)
