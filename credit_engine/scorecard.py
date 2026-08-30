"""Weight-of-evidence binned logistic regression scorecard.

For each feature:
1. Start from up to ``max_bins`` quantile bins on the training data; missing
   values get their own bin.
2. Merge adjacent bins until every bin holds at least ``min_bin_frac`` of the
   rows and the event rate is monotonic in the direction suggested by the
   Spearman correlation with the target. Monotonic WoE keeps each feature's
   effect explainable ("higher leverage, higher risk").
3. WoE = ln(%goods / %bads) per bin, with 0.5 Laplace smoothing; information
   value (IV) is summed over bins.

Features with IV below ``min_iv`` are dropped. Then, in order of IV, a feature
is skipped if its WoE correlates above ``max_corr`` with one already kept
(e.g. equity/assets vs liabilities/assets). A logistic regression is fitted on
the WoE features, and any feature whose coefficient has the wrong sign (higher
WoE must mean lower risk) is removed and the model refitted, so every
feature's points move in the intuitive direction. Points use the usual scaling:
600 points at 50:1 good:bad odds, 20 points to double the odds.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression

BASE_SCORE, BASE_ODDS, PDO = 600.0, 50.0, 20.0


@dataclass
class BinnedFeature:
    name: str
    edges: list[float]  # interior cut points; bins are (-inf, e0], (e0, e1], ..., (ek, inf)
    woe: list[float]  # one per bin
    woe_missing: float
    iv: float
    counts: list[int] = field(default_factory=list)
    bad_rates: list[float] = field(default_factory=list)

    def transform(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        idx = np.searchsorted(np.asarray(self.edges), x, side="left")
        out = np.asarray(self.woe)[np.clip(idx, 0, len(self.woe) - 1)]
        return np.where(np.isnan(x), self.woe_missing, out)


def _woe_iv(goods: np.ndarray, bads: np.ndarray, tot_g: float, tot_b: float) -> tuple[np.ndarray, float]:
    pg = (goods + 0.5) / (tot_g + 0.5 * len(goods))
    pb = (bads + 0.5) / (tot_b + 0.5 * len(bads))
    woe = np.log(pg / pb)
    return woe, float(np.sum((pg - pb) * woe))


def bin_feature(x: np.ndarray, y: np.ndarray, name: str = "x", max_bins: int = 10,
                min_bin_frac: float = 0.05) -> BinnedFeature:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int)
    tot_g, tot_b = float((y == 0).sum()), float((y == 1).sum())
    ok = ~np.isnan(x)
    xv, yv = x[ok], y[ok]
    edges = list(np.unique(np.quantile(xv, np.linspace(0, 1, max_bins + 1)[1:-1]))) if len(xv) else []
    rho = spearmanr(xv, yv).statistic if len(np.unique(xv)) > 1 else 0.0
    increasing = not (rho < 0)  # bad rate increasing in x

    def stats(edges):
        idx = np.searchsorted(np.asarray(edges), xv, side="left")
        k = len(edges) + 1
        n = np.bincount(idx, minlength=k)
        b = np.bincount(idx, weights=yv, minlength=k)
        return n, b

    min_n = max(1, int(min_bin_frac * len(x)))
    while edges:
        n, b = stats(edges)
        rate = b / np.maximum(n, 1)
        diffs = np.diff(rate) if increasing else -np.diff(rate)
        small = np.where(n < min_n)[0]
        if len(small):
            i = int(small[0])
            # merge with the smaller neighbour: drop the edge between them
            if i == 0:
                drop = 0
            elif i == len(n) - 1:
                drop = i - 1
            else:
                drop = i - 1 if n[i - 1] <= n[i + 1] else i
        elif np.any(diffs < 0):
            drop = int(np.argmin(diffs))  # worst monotonicity violation
        else:
            break
        edges.pop(drop)

    n, b = stats(edges)
    g = n - b
    woe, iv = _woe_iv(g.astype(float), b.astype(float), tot_g, tot_b)
    n_miss, b_miss = int((~ok).sum()), float(y[~ok].sum())
    if n_miss:
        w_miss, iv_miss = _woe_iv(np.array([n_miss - b_miss]), np.array([b_miss]), tot_g, tot_b)
        woe_missing, iv = float(w_miss[0]), iv + iv_miss
    else:
        woe_missing = 0.0
    return BinnedFeature(name, [float(e) for e in edges], [float(w) for w in woe], woe_missing, iv,
                         [int(c) for c in n], [float(r) for r in b / np.maximum(n, 1)])


class WoEScorecard:
    def __init__(self, max_bins: int = 10, min_bin_frac: float = 0.05, min_iv: float = 0.02,
                 max_corr: float = 0.8, C: float = 1.0):
        self.max_bins, self.min_bin_frac, self.min_iv, self.C = max_bins, min_bin_frac, min_iv, C
        self.max_corr = max_corr
        self.bins: dict[str, BinnedFeature] = {}
        self.features: list[str] = []
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0

    def fit(self, X: pd.DataFrame, y) -> "WoEScorecard":
        y = np.asarray(y, dtype=int)
        self.bins = {c: bin_feature(X[c].to_numpy(), y, c, self.max_bins, self.min_bin_frac) for c in X.columns}
        ranked = sorted((c for c in X.columns if self.bins[c].iv >= self.min_iv),
                        key=lambda c: self.bins[c].iv, reverse=True)
        woe = {c: self.bins[c].transform(X[c].to_numpy()) for c in ranked}
        kept: list[str] = []
        for c in ranked:
            if all(abs(np.corrcoef(woe[c], woe[k])[0, 1]) <= self.max_corr for k in kept):
                kept.append(c)
        while kept:
            self.features = kept
            lr = LogisticRegression(C=self.C, max_iter=2000).fit(self._woe(X), y)
            coef = lr.coef_[0]
            if np.all(coef < 0):
                break
            kept = [c for c, b in zip(kept, coef) if c != kept[int(np.argmax(coef))]]
        self.coef_, self.intercept_ = coef, float(lr.intercept_[0])
        return self

    def _woe(self, X: pd.DataFrame) -> np.ndarray:
        return np.column_stack([self.bins[c].transform(X[c].to_numpy()) for c in self.features])

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        z = self.intercept_ + self._woe(X) @ self.coef_
        return 1.0 / (1.0 + np.exp(-z))

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Scorecard points: higher is safer."""
        p = np.clip(self.predict_proba(X), 1e-12, 1 - 1e-12)
        factor = PDO / math.log(2)
        offset = BASE_SCORE - factor * math.log(BASE_ODDS)
        return offset + factor * np.log((1 - p) / p)

    def iv_table(self) -> pd.DataFrame:
        rows = [{"feature": c, "iv": b.iv, "bins": len(b.woe), "selected": c in self.features}
                for c, b in self.bins.items()]
        return pd.DataFrame(rows).sort_values("iv", ascending=False).reset_index(drop=True)

    def to_dict(self) -> dict:
        return {
            "features": self.features,
            "intercept": self.intercept_,
            "coef": [float(c) for c in self.coef_],
            "bins": {c: self.bins[c].__dict__ for c in self.features},
            "scaling": {"base_score": BASE_SCORE, "base_odds": BASE_ODDS, "pdo": PDO},
        }

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=1))

    @classmethod
    def load(cls, path: Path) -> "WoEScorecard":
        d = json.loads(Path(path).read_text())
        sc = cls()
        sc.features = d["features"]
        sc.intercept_ = d["intercept"]
        sc.coef_ = np.asarray(d["coef"])
        sc.bins = {c: BinnedFeature(**b) for c, b in d["bins"].items()}
        return sc
