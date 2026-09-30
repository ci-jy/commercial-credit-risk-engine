"""Render docs/dqc_agreement.png from reports/dqc_agreement.csv and reports/dqc_summary.json."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
COLORS = {"matched": "#1f3864", "bulk_only": "#c55a11", "arelle_only": "#a5a5a5"}


def main() -> None:
    agree = pd.read_csv(REPORTS / "dqc_agreement.csv")
    meta = json.loads((REPORTS / "dqc_summary.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(15, 4.8), gridspec_kw={"width_ratios": [2.2, 1]})

    ax = axes[0]
    x = range(len(agree))
    bottom = pd.Series(0, index=agree.index)
    for col, label in [("matched", "found by both"), ("bulk_only", "bulk screen only"),
                       ("arelle_only", "Arelle only")]:
        ax.bar(x, agree[col], bottom=bottom, color=COLORS[col], label=label)
        bottom = bottom + agree[col]
    for i, r in agree.iterrows():
        ax.text(i, bottom[i] + 0.3, f"{100 * r.filing_agreement:.0f}%", ha="center", fontsize=8.5)
    ax.set_xticks(list(x), [r.replace("DQC_", "") for r in agree.rule], fontsize=9)
    ax.set_xlabel("DQC rule")
    ax.set_ylabel("findings on the sample filings")
    ax.set_title(f"Bulk screen vs Arelle + XULE on {meta['n_sample']} filings "
                 f"(labels: filing-level agreement)")
    ax.legend(frameon=False)

    ax = axes[1]
    per_quarter_bulk = meta["load_s"] + meta["screen_s"]
    per_quarter_arelle = meta["arelle_median_s"] * meta["n_screened"]
    bars = ax.barh([0, 1], [per_quarter_arelle / 3600, per_quarter_bulk / 3600], color=["#a5a5a5", "#1f3864"])
    ax.set_xscale("log")
    ax.set_yticks([0, 1], ["Arelle, one filing\nat a time (median)", "Bulk screen,\nwhole quarter"])
    for b, label in zip(bars, [f"{per_quarter_arelle / 3600:,.0f} h", f"{per_quarter_bulk:,.0f} s"]):
        ax.text(b.get_width() * 1.15, b.get_y() + b.get_height() / 2, label, va="center")
    ax.set_xlim(per_quarter_bulk / 3600 / 3, per_quarter_arelle / 3600 * 20)
    ax.set_xlabel("hours to screen one quarter (log scale)")
    ax.set_title(f"{meta['quarter']}: {meta['n_screened']:,} US GAAP filings")
    fig.tight_layout()
    out = ROOT / "docs" / "dqc_agreement.png"
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
