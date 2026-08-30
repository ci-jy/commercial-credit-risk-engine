"""Benchmark: WoE scorecard vs Altman Z'' vs gradient boosting on the UCI Polish data.

All three models are fitted on the same stratified 70% training split and
evaluated on the 30% held-out split with AUC, KS, Brier score and expected
calibration error, each with stratified bootstrap 95% CIs. The paired
bootstrap of the AUC difference tests whether the scorecard beats Z''.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split

from credit_engine import MODELS_DIR, REPO_ROOT
from credit_engine.altman import AltmanPD
from credit_engine.metrics import bootstrap, calibration_table
from credit_engine.polish import ATTR_COLS, SPREAD_FEATURES, load_polish
from credit_engine.scorecard import WoEScorecard

MODEL_NAMES = {
    "scorecard": "WoE scorecard",
    "altman_z": "Altman Z''",
    "gbm": "Gradient boosting (64 ratios)",
    "gbm_spread": "Gradient boosting (17 spread ratios)",
}


def save_pd_models(path: Path, sc: WoEScorecard, alt: AltmanPD, meta: dict) -> None:
    payload = {
        "meta": meta,
        "scorecard": sc.to_dict(),
        "altman": {"coef": float(alt.lr.coef_[0, 0]), "intercept": float(alt.lr.intercept_[0]),
                   "lo": float(alt.lo), "hi": float(alt.hi), "fill": alt.fill},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1))


def run_benchmark(offline: bool = False, quick: bool = False, out_dir: Path | None = None,
                  models_path: Path | None = None, seed: int = 42) -> dict:
    t0 = time.time()
    if out_dir is None:
        out_dir = REPO_ROOT / ("out/benchmark" if offline else "reports")
    if models_path is None:
        models_path = (out_dir / "pd_models.json") if offline else (MODELS_DIR / "pd_models.json")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_polish(offline=offline)
    y = df["class"].to_numpy()
    train, test = train_test_split(df, test_size=0.3, stratify=y, random_state=seed)
    y_tr, y_te = train["class"].to_numpy(), test["class"].to_numpy()
    feats = list(SPREAD_FEATURES)

    sc = WoEScorecard().fit(train[feats], y_tr)
    alt = AltmanPD().fit(train, y_tr)
    def make_gbm():
        return HistGradientBoostingClassifier(
            max_iter=150 if quick else 400, learning_rate=0.05, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=seed,
        )

    gbm = make_gbm().fit(train[ATTR_COLS], y_tr)
    gbm_spread = make_gbm().fit(train[feats], y_tr)

    preds = {
        "scorecard": sc.predict_proba(test[feats]),
        "altman_z": alt.predict_proba(test),
        "gbm": gbm.predict_proba(test[ATTR_COLS])[:, 1],
        "gbm_spread": gbm_spread.predict_proba(test[feats])[:, 1],
    }
    n_boot = 200 if quick else 1000
    metrics = bootstrap(y_te, preds, n_boot=n_boot, seed=seed,
                        paired=[("scorecard", "altman_z"), ("gbm_spread", "scorecard"), ("gbm", "scorecard")])
    calib = pd.concat([calibration_table(y_te, p).assign(model=m) for m, p in preds.items()], ignore_index=True)
    iv = sc.iv_table()
    iv["description"] = iv["feature"].map(SPREAD_FEATURES)

    meta = {
        "dataset": "UCI Polish companies bankruptcy (offline sample)" if offline else "UCI Polish companies bankruptcy (all 5 horizons)",
        "n_rows": int(len(df)), "n_train": int(len(train)), "n_test": int(len(test)),
        "bad_rate": float(y.mean()), "test_bads": int(y_te.sum()), "n_boot": n_boot, "seed": seed,
        "scorecard_features": sc.features,
    }
    metrics.to_csv(out_dir / "benchmark_metrics.csv", index=False)
    calib.to_csv(out_dir / "calibration.csv", index=False)
    iv.to_csv(out_dir / "scorecard_iv.csv", index=False)
    (out_dir / "benchmark.md").write_text(render_report(metrics, calib, iv, meta))
    save_pd_models(models_path, sc, alt, meta)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    return {"metrics": metrics, "calibration": calib, "iv": iv, "meta": meta, "out_dir": out_dir}


def _fmt(row) -> str:
    return f"{row.estimate:.3f} [{row.ci_low:.3f}, {row.ci_high:.3f}]"


def metrics_table(metrics: pd.DataFrame) -> str:
    lines = ["| Model | AUC | KS | Brier | ECE |", "|---|---|---|---|---|"]
    for m, label in MODEL_NAMES.items():
        sub = metrics[metrics.model == m].set_index("metric")
        cells = [_fmt(sub.loc[k]) for k in ("auc", "ks", "brier", "ece")]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(metrics: pd.DataFrame, calib: pd.DataFrame, iv: pd.DataFrame, meta: dict) -> str:
    diffs = metrics[metrics.metric == "auc_diff"]
    out = [
        "# PD model benchmark",
        "",
        f"Data: {meta['dataset']}: {meta['n_rows']:,} firm-years, bad rate {meta['bad_rate']:.2%}. "
        f"Stratified 70/30 split (seed {meta['seed']}): {meta['n_train']:,} train, {meta['n_test']:,} held-out "
        f"({meta['test_bads']} bankruptcies). 95% CIs from {meta['n_boot']} stratified bootstrap resamples of the test set.",
        "",
        "Higher is better for AUC and KS; lower is better for Brier and ECE (expected calibration error, 10 equal-count bins).",
        "",
        metrics_table(metrics),
        "",
        "## Paired AUC differences",
        "",
        "| Comparison | ΔAUC [95% CI] |",
        "|---|---|",
    ]
    for r in diffs.itertuples():
        a, b = r.model.split(" - ")
        out.append(f"| {MODEL_NAMES[a]} − {MODEL_NAMES[b]} | {_fmt(r)} |")
    out += ["", "## Calibration (held-out deciles of predicted PD)", ""]
    for m, label in MODEL_NAMES.items():
        sub = calib[calib.model == m]
        out += [f"**{label}**", "", "| Decile | n | Mean PD | Observed rate |", "|---|---|---|---|"]
        out += [f"| {r.bin} | {r.n} | {r.mean_pd:.3%} | {r.observed_rate:.3%} |" for r in sub.itertuples()]
        out.append("")
    out += ["## Scorecard features (information value on the training split)", "",
            "| Feature | Definition | IV | Bins | Selected |", "|---|---|---|---|---|"]
    out += [f"| {r.feature} | {r.description} | {r.iv:.3f} | {r.bins} | {'yes' if r.selected else 'no'} |"
            for r in iv.itertuples()]
    out += ["", "Models: the scorecard selects its features from the 17 ratios that can also be computed from a US GAAP "
            "spread (IV >= 0.02, WoE correlation <= 0.8, coefficient signs checked); "
            "Altman Z'' uses its four published ratios and fixed weights, with a logistic map from Z'' to PD fitted on "
            "the training split; gradient boosting (scikit-learn HistGradientBoostingClassifier) is fitted twice, on all 64 "
            "ratios and on the scorecard's 17, to separate the effect of the model from the effect of the feature set.", ""]
    return "\n".join(out)
