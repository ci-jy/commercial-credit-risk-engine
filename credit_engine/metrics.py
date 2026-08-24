"""Discrimination and calibration metrics with bootstrap confidence intervals."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve


def ks_stat(y, p) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def ece(y, p, n_bins: int = 10) -> float:
    """Expected calibration error over equal-count bins of predicted PD."""
    t = calibration_table(y, p, n_bins)
    return float(np.sum(t["n"] * np.abs(t["mean_pd"] - t["observed_rate"])) / t["n"].sum())


METRICS = {
    "auc": lambda y, p: float(roc_auc_score(y, p)),
    "ks": ks_stat,
    "brier": lambda y, p: float(brier_score_loss(y, p)),
    "ece": ece,
}


def calibration_table(y, p, n_bins: int = 10) -> pd.DataFrame:
    y, p = np.asarray(y), np.asarray(p)
    order = np.argsort(p, kind="mergesort")
    groups = np.array_split(order, n_bins)
    rows = []
    for i, g in enumerate(groups):
        rows.append({"bin": i + 1, "n": len(g), "mean_pd": float(p[g].mean()), "observed_rate": float(y[g].mean())})
    return pd.DataFrame(rows)


def bootstrap(y, preds: dict[str, np.ndarray], n_boot: int = 1000, seed: int = 0,
              paired: list[tuple[str, str]] | None = None) -> pd.DataFrame:
    """Point estimates and 95% percentile CIs, resampling the test set with stratification.

    ``paired`` adds AUC differences (a - b) computed on the same resamples.
    """
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
    samples = {(m, k): [] for m in preds for k in METRICS}
    diffs = {pair: [] for pair in (paired or [])}
    for _ in range(n_boot):
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        yb = y[idx]
        aucs = {}
        for m, p in preds.items():
            for k, fn in METRICS.items():
                v = fn(yb, p[idx])
                samples[(m, k)].append(v)
                if k == "auc":
                    aucs[m] = v
        for a, b in diffs:
            diffs[(a, b)].append(aucs[a] - aucs[b])
    rows = []
    for m, p in preds.items():
        for k, fn in METRICS.items():
            s = np.asarray(samples[(m, k)])
            rows.append({"model": m, "metric": k, "estimate": fn(y, p),
                         "ci_low": float(np.percentile(s, 2.5)), "ci_high": float(np.percentile(s, 97.5))})
    for (a, b), s in diffs.items():
        s = np.asarray(s)
        rows.append({"model": f"{a} - {b}", "metric": "auc_diff",
                     "estimate": METRICS["auc"](y, preds[a]) - METRICS["auc"](y, preds[b]),
                     "ci_low": float(np.percentile(s, 2.5)), "ci_high": float(np.percentile(s, 97.5))})
    return pd.DataFrame(rows)
