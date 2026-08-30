"""Render docs/benchmark.png from the committed benchmark CSVs in reports/."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
NAMES = {
    "scorecard": "WoE scorecard\n(17 spread ratios)",
    "altman_z": "Altman Z''\n(4 ratios)",
    "gbm_spread": "Grad. boosting\n(17 spread ratios)",
    "gbm": "Grad. boosting\n(all 64 ratios)",
}
COLORS = {"scorecard": "#1f3864", "altman_z": "#c55a11", "gbm_spread": "#7f7f7f", "gbm": "#a5a5a5"}


def main() -> None:
    m = pd.read_csv(REPORTS / "benchmark_metrics.csv")
    cal = pd.read_csv(REPORTS / "calibration.csv")
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for ax, metric, title in [(axes[0], "auc", "Held-out AUC (95% bootstrap CI)"),
                              (axes[1], "ks", "Held-out KS (95% bootstrap CI)")]:
        sub = m[m.metric == metric].set_index("model").loc[list(NAMES)]
        x = range(len(sub))
        ax.bar(x, sub.estimate, color=[COLORS[k] for k in sub.index],
               yerr=[sub.estimate - sub.ci_low, sub.ci_high - sub.estimate], capsize=5)
        for i, (v, top) in enumerate(zip(sub.estimate, sub.ci_high)):
            ax.text(i, top + 0.015, f"{v:.3f}", ha="center", fontsize=10)
        ax.set_xticks(list(x), [NAMES[k] for k in sub.index], fontsize=8.5)
        ax.set_ylim(0.5 if metric == "auc" else 0, 1.05 if metric == "auc" else 1.0)
        ax.set_title(title)
    ax = axes[2]
    for k in ("scorecard", "altman_z", "gbm"):
        c = cal[cal.model == k]
        ax.plot(c.mean_pd, c.observed_rate, "o-", color=COLORS[k], label=NAMES[k].replace("\n", " "))
    hi = max(cal.mean_pd.max(), cal.observed_rate.max()) * 1.05
    ax.plot([0, hi], [0, hi], "k--", lw=1, label="perfect calibration")
    ax.set_xlabel("Mean predicted PD (decile)")
    ax.set_ylabel("Observed bankruptcy rate")
    ax.set_title("Calibration on held-out firm-years")
    ax.legend(fontsize=8)
    fig.suptitle("Bankruptcy PD models on the UCI Polish companies data (43,405 firm-years, 30% held out)", fontsize=12)
    fig.tight_layout()
    out = ROOT / "docs" / "benchmark.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
