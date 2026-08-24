"""Altman Z'' (1995) score for non-manufacturing and emerging-market firms.

Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4 where
X1 = working capital / total assets, X2 = retained earnings / total assets,
X3 = EBIT / total assets, X4 = book equity / total liabilities.
Zones: Z'' > 2.60 safe, 1.10-2.60 grey, < 1.10 distress.

Z'' is a score, not a probability. For Brier score and calibration the
benchmark maps it to a PD with a one-feature logistic fit on the training
split (Platt scaling), which leaves its ranking (AUC, KS) unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

WEIGHTS = {"Attr3": 6.56, "Attr6": 3.26, "Attr7": 6.72, "Attr8": 1.05}


def z_double_prime(x1, x2, x3, x4):
    return 6.56 * np.asarray(x1) + 3.26 * np.asarray(x2) + 6.72 * np.asarray(x3) + 1.05 * np.asarray(x4)


def z_from_polish(df: pd.DataFrame) -> np.ndarray:
    return z_double_prime(df["Attr3"], df["Attr6"], df["Attr7"], df["Attr8"])


def zone(z: float) -> str:
    if z > 2.60:
        return "safe"
    if z >= 1.10:
        return "grey"
    return "distress"


class AltmanPD:
    """Z'' with Platt-scaled PD. Missing or extreme Z'' values are clipped to the training range."""

    def fit(self, df: pd.DataFrame, y) -> "AltmanPD":
        z = z_from_polish(df)
        finite = np.isfinite(z)
        self.lo, self.hi = np.nanpercentile(z[finite], [0.5, 99.5])
        self.fill = float(np.nanmedian(z[finite]))
        self.lr = LogisticRegression(max_iter=1000).fit(self._prep(z), np.asarray(y))
        return self

    def _prep(self, z: np.ndarray) -> np.ndarray:
        z = np.where(np.isfinite(z), z, self.fill)
        return np.clip(z, self.lo, self.hi).reshape(-1, 1)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return self.lr.predict_proba(self._prep(z_from_polish(df)))[:, 1]

    def pd_from_z(self, z: float) -> float:
        return float(self.lr.predict_proba(self._prep(np.array([z], dtype=float)))[0, 1])
