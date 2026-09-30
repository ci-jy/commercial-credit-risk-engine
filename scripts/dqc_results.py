"""Build the DQC screen results: agreement with Arelle, runtime, ratio impact and the Excel report.

    python scripts/dqc_results.py              # full quarter in data/fsds/2026q2.zip + sample comparison
    python scripts/dqc_results.py --offline    # sample comparison only, from committed fixtures

Writes ``reports/dqc_results.md`` and the CSVs it summarises, the exceptions
workbook ``reports/dqc_exceptions_2026q2.xlsx`` (full mode) and the figure
``docs/dqc_agreement.png``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_engine.dqc import RULE_IDS, rule_module, run_screen  # noqa: E402
from credit_engine.dqc.compare import DQC_FIXTURES, agreement_by_rule, align, explain, load_arelle  # noqa: E402
from credit_engine.dqc.excel_report import build_exceptions_workbook  # noqa: E402
from credit_engine.dqc.fsds import load_quarter, quarter_path  # noqa: E402
from credit_engine.dqc.impact import ratio_impact, summarise_impact  # noqa: E402

REPORTS = ROOT / "reports"


def sample_comparison() -> dict:
    sample = pd.read_csv(DQC_FIXTURES / "sample_filings.csv", dtype=str)
    arelle, runs = load_arelle(list(sample.adsh))
    done = set(runs.adsh)
    q = load_quarter(DQC_FIXTURES / "fsds_sample", adsh=done)
    t0 = time.perf_counter()
    bulk = run_screen(q)
    t_sample = time.perf_counter() - t0
    explained = explain(align(bulk, arelle))
    agree = agreement_by_rule(explained, n_filings=len(done))
    return {"sample": sample[sample.adsh.isin(done)], "runs": runs, "explained": explained, "agree": agree,
            "bulk_sample_s": t_sample}


def full_quarter(quarter: str) -> dict:
    t0 = time.perf_counter()
    q = load_quarter(quarter_path(quarter))
    t_load = time.perf_counter() - t0
    timings: dict[str, float] = {}
    findings = run_screen(q, timings=timings)
    t_screen = sum(timings.values())
    impact = ratio_impact(findings, q.num, q.sub)
    xlsx = build_exceptions_workbook(findings, q.sub, REPORTS / f"dqc_exceptions_{quarter}.xlsx",
                                     f"DQC exceptions - SEC Financial Statement Data Set {quarter}", pre=q.pre)
    counts = pd.DataFrame([{"rule": r, "title": rule_module(r).TITLE,
                            "findings": int((findings.rule == r).sum()),
                            "filings_flagged": int(findings[findings.rule == r].adsh.nunique()),
                            "screen_s": round(timings[r], 3)} for r in RULE_IDS])
    return {"q": q, "findings": findings, "t_load": t_load, "t_screen": t_screen, "impact": impact,
            "counts": counts, "xlsx": xlsx, "n_filings": len(q.sub), "n_facts": len(q.num),
            "n_screened": int(q.num.adsh.nunique())}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def write_report(cmp: dict, full: dict | None, quarter: str) -> None:
    REPORTS.mkdir(exist_ok=True)
    agree, explained, runs = cmp["agree"], cmp["explained"], cmp["runs"]
    agree.to_csv(REPORTS / "dqc_agreement.csv", index=False, float_format="%.4f")
    dis = explained[explained.side != "both"][["adsh", "rule", "element_id", "arelle_element_id", "concept", "ddate",
                                                "segments", "side", "category", "root_cause"]]
    dis.to_csv(REPORTS / "dqc_disagreements.csv", index=False)
    runs.to_csv(REPORTS / "dqc_arelle_runtime.csv", index=False)

    n = len(runs)
    matched = int((explained.side == "both").sum())
    total = len(explained)
    lines = [f"# Bulk DQC screen vs Arelle + XULE: results ({quarter})", ""]
    lines += [f"Sample: **{n} 10-K/10-Q filings** from the SEC Financial Statement Data Set {quarter} "
              f"({len(cmp['sample'][cmp['sample'].form == '10-K'])} 10-K, "
              f"{len(cmp['sample'][cmp['sample'].form == '10-Q'])} 10-Q). Most were drawn at random (seed 7); "
              "the rest were added because the bulk screen flagged them, so that every rule that fires has "
              "real cases to compare. Reference: Arelle "
              "(`arelle-release`) with the XULE plugin and the official DQC v30 compiled ruleset for each filing's "
              "US GAAP year. Findings are aligned on (filing, rule, concept, period end, dimensions).", ""]
    lines += [f"**Overall: {matched} of {total} findings matched ({pct(matched / total if total else 1)}); "
              f"{int((explained.category == 'unexplained').sum())} unexplained disagreements.**", ""]
    lines += ["## Agreement per rule", "",
              "| Rule | Title | Matched | Bulk only | Arelle only | Finding agreement | Filing agreement |",
              "|---|---|---|---|---|---|---|"]
    for r in agree.itertuples():
        lines.append(f"| {r.rule} | {rule_module(r.rule).TITLE} | {r.matched} | {r.bulk_only} | {r.arelle_only} | "
                     f"{pct(r.finding_agreement)} | {pct(r.filing_agreement)} |")
    lines += ["", "*Finding agreement* = matched / (matched + bulk only + Arelle only); 100% when neither side "
              "reports anything. *Filing agreement* = share of sample filings where both tools agree on whether "
              "the rule fires.", ""]
    lines += ["## Disagreements and root causes", ""]
    if dis.empty:
        lines += ["None.", ""]
    else:
        grp = dis.groupby(["rule", "side", "category", "root_cause"], dropna=False).size().reset_index(name="n")
        lines += ["| Rule | Reported by | Count | Category | Root cause |", "|---|---|---|---|---|"]
        for r in grp.itertuples():
            lines.append(f"| {r.rule} | {'bulk only' if r.side == 'bulk' else 'Arelle only'} | {r.n} | "
                         f"{r.category} | {r.root_cause} |")
        lines += ["", f"Every disagreement, with filing and concept: [dqc_disagreements.csv](dqc_disagreements.csv).", ""]
    lines += ["## Runtime", ""]
    rt = runs.runtime_s
    lines += [f"- Arelle + XULE + DQC ruleset: **median {rt.median():.1f} s per filing** "
              f"(mean {rt.mean():.1f} s, min {rt.min():.1f} s, max {rt.max():.1f} s, {n} filings, one process, "
              "warm taxonomy cache). This runs all ~200 DQC rules on the full XBRL instance."]
    if full:
        per = full["t_screen"] + full["t_load"]
        lines += [f"- Bulk screen, whole quarter: **{full['t_load']:.1f} s to load + {full['t_screen']:.1f} s to "
                  f"screen = {per:.1f} s for {full['n_screened']:,} US GAAP filings** "
                  f"({full['n_facts']:,} facts), i.e. {1000 * per / full['n_screened']:.1f} ms per filing.",
                  f"- At Arelle's median, the same quarter would take about "
                  f"**{rt.median() * full['n_screened'] / 3600:.0f} CPU-hours** "
                  f"({rt.median() * full['n_screened'] / per:,.0f}x the bulk time). The bulk screen only runs "
                  f"{len(RULE_IDS)} rules, so this compares workflows, not rule-for-rule speed."]
    lines += [""]
    if full:
        lines += [f"## Whole-quarter findings ({quarter})", "",
                  "| Rule | Findings | Filings flagged | Screen time (s) |", "|---|---|---|---|"]
        for r in full["counts"].itertuples():
            lines.append(f"| {r.rule} | {r.findings:,} | {r.filings_flagged:,} | {r.screen_s:.2f} |")
        lines += ["", f"Excel exceptions workbook: [{full['xlsx'].name}]({full['xlsx'].name}) "
                  "(summary sheet linking to one sheet per rule; each accession number links to the filing on EDGAR).", ""]
        imp = full["impact"]
        summ = summarise_impact(imp)
        summ.to_csv(REPORTS / "dqc_ratio_impact.csv", index=False, float_format="%.4f")
        imp.to_csv(REPORTS / "dqc_ratio_impact_detail.csv", index=False, float_format="%.6g")
        hits = imp.drop_duplicates(["adsh", "rule", "concept"]) if len(imp) else imp
        changed = imp[imp.changed].drop_duplicates(["adsh", "rule", "concept"]) if len(imp) else imp
        lev_cov = imp[imp.changed & imp.ratio.isin(["debt_to_ebitda", "net_leverage", "interest_coverage", "dscr",
                                                     "fccr"])].drop_duplicates(["adsh", "rule", "concept"]) \
            if len(imp) else imp
        lines += ["## Impact on the engine's credit ratios", "",
                  f"Of {len(full['findings']):,} findings, **{len(hits)} flag a value the engine's spread actually "
                  f"uses** (dimensionless, current period, with a suggested correction) in "
                  f"{hits.adsh.nunique() if len(hits) else 0} filings. Applying the suggested correction "
                  f"changes at least one ratio by more than 0.5% for **{len(changed)}** of them, and a leverage or "
                  f"coverage ratio for **{len(lev_cov)}**.", "",
                  "| Ratio | Findings hitting the spread | Ratio changed | Median abs. change | Max abs. change |",
                  "|---|---|---|---|---|"]
        for r in summ.itertuples():
            med = "n/a" if math.isnan(r.median_abs_pct) else f"{r.median_abs_pct:.1f}%"
            mx = "n/a" if math.isnan(r.max_abs_pct) else f"{r.max_abs_pct:.1f}%"
            lines.append(f"| {r.ratio} | {r.findings_hitting_spread} | {r.changed} | {med} | {mx} |")
        lines += ["", "Changes between a finite ratio and n/m (e.g. EBITDA turning positive) count as changed but are "
                  "left out of the % columns. Detail: [dqc_ratio_impact_detail.csv](dqc_ratio_impact_detail.csv).", ""]
        meta = {"quarter": quarter, "n_filings": full["n_filings"], "n_screened": full["n_screened"],
                "n_facts": full["n_facts"], "load_s": round(full["t_load"], 2), "screen_s": round(full["t_screen"], 2),
                "arelle_median_s": round(float(rt.median()), 2), "n_sample": n, "matched": matched, "total": total,
                "findings": int(len(full["findings"])), "ratio_hits": int(len(hits)), "ratio_changed": int(len(changed)),
                "lev_cov_changed": int(len(lev_cov))}
        (REPORTS / "dqc_summary.json").write_text(json.dumps(meta, indent=1))
    (REPORTS / "dqc_results.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quarter", default="2026q2")
    ap.add_argument("--offline", action="store_true", help="skip the full-quarter parts")
    args = ap.parse_args()
    cmp = sample_comparison()
    full = None if args.offline else full_quarter(args.quarter)
    write_report(cmp, full, args.quarter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
