"""Shared helpers for the bulk DQC rules: the finding schema and decimal tolerances."""

from __future__ import annotations

import numpy as np
import pandas as pd

FINDING_COLS = ["adsh", "rule", "element_id", "concept", "ddate", "qtrs", "segments", "uom",
                "value", "suggested", "message"]


def make_findings(rows: pd.DataFrame, rule: str, element_id, message, suggested=None,
                  concept_col: str = "tag") -> pd.DataFrame:
    """Turn the offending fact rows into the finding schema.

    ``element_id``, ``message`` and ``suggested`` may be scalars, Series aligned
    with ``rows`` or callables taking ``rows``.
    """
    if rows is None or rows.empty:
        return pd.DataFrame(columns=FINDING_COLS)

    def resolve(x):
        return x(rows) if callable(x) else x

    out = pd.DataFrame({
        "adsh": rows.adsh.astype(str).to_numpy(),
        "rule": rule,
        "element_id": resolve(element_id),
        "concept": rows[concept_col].astype(str).to_numpy(),
        "ddate": rows.ddate.astype(int).to_numpy(),
        "qtrs": rows.qtrs.astype(int).to_numpy(),
        "segments": rows.segments.astype(object).where(rows.segments.notna(), "").to_numpy(),
        "uom": rows.uom.astype(str).to_numpy(),
        "value": rows.value.astype(float).to_numpy(),
        "suggested": resolve(suggested) if suggested is not None else np.nan,
        "message": resolve(message),
    })
    for col in ("element_id", "message", "suggested"):
        v = out[col]
        if isinstance(v, pd.Series) and len(v) == len(rows):
            out[col] = np.asarray(v)
    return out[FINDING_COLS]


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=FINDING_COLS)


def decimal_tolerance(decimals, factor: float = 2.0):
    """DQC ``tolerance_for_decimals``: values agree if |a - b| <= factor * 10**-decimals.

    The data sets carry no ``decimals``; callers pass the estimated precision
    (the minimum over the compared facts, see :mod:`credit_engine.dqc.fsds`).
    """
    return factor * np.power(10.0, -np.asarray(decimals, dtype=float))


def round_to(values, decimals):
    """Round to ``decimals`` places (negative = tens, hundreds, ...), like XULE ``round``."""
    d = np.asarray(decimals, dtype=float)
    scale = np.power(10.0, d)
    return np.round(np.asarray(values, dtype=float) * scale) / scale


def exceeds_tolerance(left, right, decimals, factor: float):
    """DQC ``tolerance_for_decimals``: |round(L, d) - round(R, d)| > factor * 10**-d."""
    return np.abs(round_to(left, decimals) - round_to(right, decimals)) > decimal_tolerance(decimals, factor)


def fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 1000 or float(v).is_integer() else f"{v:,.4g}"


def dimensionless(num: pd.DataFrame) -> pd.DataFrame:
    return num[num.dimensionless]


def pivot_concepts(num: pd.DataFrame, concepts: list[str], keys=("adsh", "ddate", "qtrs", "uom", "segments", "coreg")):
    """One row per context (filing, period, unit, dimensions) with a column per concept."""
    sub = num[num.tag.isin(concepts)].copy()
    if sub.empty:
        return pd.DataFrame(columns=list(keys) + list(concepts))
    sub["tag"] = sub.tag.astype(str)
    k = list(keys)
    for c in k:
        sub[c] = sub[c].astype(object).where(sub[c].notna(), "")
    sub["dec"] = sub.decimals.astype(int)
    wide = sub.pivot_table(index=k, columns="tag", values="value", aggfunc="first")
    dec = sub.pivot_table(index=k, columns="tag", values="dec", aggfunc="min")
    dec.columns = [f"{c}__dec" for c in dec.columns]
    out = wide.join(dec).reset_index()
    for c in concepts:
        if c not in out:
            out[c] = np.nan
            out[f"{c}__dec"] = np.nan
    return out
