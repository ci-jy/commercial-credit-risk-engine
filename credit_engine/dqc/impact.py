"""How much do flagged values move the engine's leverage and coverage ratios?

For each filing a one-period spread is built from the data set's dimensionless
facts, using the same tag priority as :mod:`credit_engine.spreading`
(``LINE_ITEMS``): annual flows (``qtrs`` = 4) for 10-Ks, the latest quarter
times four for 10-Qs, and balance-sheet instants at the report date. Ratios
come from :func:`credit_engine.ratios.compute_ratios`.

A finding *hits the spread* when its fact is the one the spread used. Its
suggested correction is then substituted and the ratios recomputed; a ratio
*changes* when it moves by more than 0.5% (or crosses between finite and n/m).
"""

from __future__ import annotations

import math

import pandas as pd

from credit_engine.ratios import compute_ratios
from credit_engine.spreading import FLOW, LINE_ITEMS, Derived

RATIOS = ["debt_to_ebitda", "net_leverage", "interest_coverage", "dscr", "fccr", "current_ratio", "debt_to_equity"]
CHANGE_TOL = 0.005


def _facts_for_filing(num: pd.DataFrame, form: str, period: int) -> dict[tuple[str, str], float]:
    """(tag, kind) -> value for the filing's own reporting period."""
    flows_q = 4 if form.startswith("10-K") else 1
    scale = 1.0 if flows_q == 4 else 4.0
    plain = num[num.dimensionless & (num.uom.astype(str) == "USD") & (num.ddate == period)]
    out = {}
    for r in plain.itertuples():
        if r.qtrs == flows_q:
            out.setdefault((str(r.tag), FLOW), r.value * scale)
        elif r.qtrs == 0:
            out.setdefault((str(r.tag), "instant"), r.value)
    return out


def spread_from_facts(facts: dict[tuple[str, str], float]) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Spread values and, per line item, the tags its value was computed from."""
    values, used = {}, {}
    for item, (_stmt, kind, candidates, default) in LINE_ITEMS.items():
        k = FLOW if kind == FLOW else "instant"
        val, tags = None, []
        for cand in candidates:
            if isinstance(cand, Derived):
                parts = [facts.get((t, k)) for t in cand.tags]
                if all(p is not None for p in parts):
                    val, tags = cand.fn(*parts), list(cand.tags)
                    break
            elif (cand, k) in facts:
                val, tags = facts[(cand, k)], [cand]
                break
        if val is None:
            val = default if default is not None else math.nan
        values[item] = val
        used[item] = tags
    if math.isnan(values["cash_taxes"]):
        values["cash_taxes"] = values["income_tax"]
    return values, used


def _changed(a: float, b: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return False
    if math.isinf(a) or math.isinf(b) or math.isnan(a) or math.isnan(b):
        return a != b
    return abs(b - a) > CHANGE_TOL * max(abs(a), 1e-12)


def ratio_impact(findings: pd.DataFrame, num: pd.DataFrame, sub: pd.DataFrame) -> pd.DataFrame:
    """One row per (finding that hits a spread input, ratio) with before/after values."""
    meta = sub.set_index("adsh")
    cand = findings[(findings.segments.fillna("") == "") & findings.suggested.notna()]
    rows = []
    for adsh, group in cand.groupby("adsh"):
        m = meta.loc[adsh]
        period = int(m.period)
        nf = num[num.adsh == adsh]
        facts = _facts_for_filing(nf, m.form, period)
        base_vals, used = spread_from_facts(facts)
        if any(math.isnan(base_vals[k]) for k in ("operating_income", "current_assets", "current_liabilities")):
            continue
        base = compute_ratios(base_vals)
        flows_q = 4 if m.form.startswith("10-K") else 1
        for f in group.itertuples():
            if f.ddate != period or f.qtrs not in (0, flows_q):
                continue
            kind = FLOW if f.qtrs else "instant"
            if (f.concept, kind) not in facts or facts[(f.concept, kind)] != f.value * (4.0 if kind == FLOW and flows_q == 1 else 1.0):
                continue
            items = [i for i, tags in used.items() if f.concept in tags]
            if not items:
                continue
            fixed = dict(facts)
            fixed[(f.concept, kind)] = f.suggested * (4.0 if kind == FLOW and flows_q == 1 else 1.0)
            new = compute_ratios(spread_from_facts(fixed)[0])
            for ratio in RATIOS:
                rows.append({"adsh": adsh, "rule": f.rule, "concept": f.concept, "line_items": ",".join(items),
                             "ratio": ratio, "before": base[ratio], "after": new[ratio],
                             "changed": _changed(base[ratio], new[ratio])})
    return pd.DataFrame(rows, columns=["adsh", "rule", "concept", "line_items", "ratio", "before", "after", "changed"])


def summarise_impact(impact: pd.DataFrame) -> pd.DataFrame:
    """Per ratio: findings that change it, and the median / max absolute % move."""
    if impact.empty:
        return pd.DataFrame(columns=["ratio", "findings_hitting_spread", "changed", "median_abs_pct", "max_abs_pct"])
    rows = []
    for ratio, g in impact.groupby("ratio", sort=False):
        ch = g[g.changed]
        fin = ch[ch.before.map(math.isfinite) & ch.after.map(math.isfinite) & (ch.before != 0)]
        pct = ((fin.after - fin.before) / fin.before.abs()).abs() * 100
        rows.append({"ratio": ratio, "findings_hitting_spread": len(g), "changed": int(len(ch)),
                     "median_abs_pct": float(pct.median()) if len(pct) else math.nan,
                     "max_abs_pct": float(pct.max()) if len(pct) else math.nan})
    return pd.DataFrame(rows)
