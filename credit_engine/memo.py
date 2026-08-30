"""Assemble a borrower analysis and render it as a markdown credit memo plus an Excel spread."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from credit_engine import MODELS_DIR
from credit_engine.altman import z_double_prime, zone
from credit_engine.excel import build_workbook, compare_with_python, recalculate, soffice_path
from credit_engine.merton import MertonResult, default_point, equity_volatility, solve_merton
from credit_engine.polish import SPREAD_FEATURES, spread_to_polish_ratios
from credit_engine.rating import rating_bucket
from credit_engine.ratios import AMOUNT_RATIOS, DEFAULT_COVENANTS, RATIO_LABELS, compute_ratios, test_covenants
from credit_engine.scorecard import PDO, WoEScorecard
from credit_engine.spreading import LINE_ITEMS, Spread
from credit_engine.stress import SCENARIOS, run_stress

LINE_LABELS = {
    "revenue": "Revenue", "cogs": "Cost of goods sold", "operating_income": "Operating income (EBIT)",
    "depreciation_amortization": "Depreciation & amortization", "impairments": "Non-cash impairments",
    "interest_expense": "Interest expense", "pretax_income": "Pretax income", "income_tax": "Income tax expense",
    "net_income": "Net income", "operating_lease_cost": "Operating lease cost", "cash": "Cash & equivalents",
    "receivables": "Receivables", "inventory": "Inventory", "current_assets": "Current assets",
    "total_assets": "Total assets", "current_liabilities": "Current liabilities",
    "short_term_borrowings": "Short-term borrowings", "current_portion_ltd": "Current portion of LTD",
    "long_term_debt": "Long-term debt", "total_liabilities": "Total liabilities", "total_equity": "Total equity",
    "retained_earnings": "Retained earnings", "cfo": "Cash from operations", "capex": "Capital expenditures",
    "cash_taxes": "Cash taxes paid", "dividends": "Dividends paid",
}


def load_pd_models(path: Path | None = None) -> tuple[WoEScorecard, dict, dict]:
    """Load the scorecard and Altman PD map; train on the offline sample if no saved model exists."""
    path = Path(path) if path else MODELS_DIR / "pd_models.json"
    if not path.exists():
        from credit_engine.benchmark import run_benchmark

        res = run_benchmark(offline=True, quick=True)
        path = res["out_dir"] / "pd_models.json"
    d = json.loads(path.read_text())
    tmp = WoEScorecard()
    sc = d["scorecard"]
    tmp.features, tmp.intercept_, tmp.coef_ = sc["features"], sc["intercept"], np.asarray(sc["coef"])
    from credit_engine.scorecard import BinnedFeature

    tmp.bins = {c: BinnedFeature(**b) for c, b in sc["bins"].items()}
    return tmp, d["altman"], d["meta"]


def altman_pd(z: float, params: dict) -> float:
    zc = min(max(z if math.isfinite(z) else params["fill"], params["lo"]), params["hi"])
    return 1.0 / (1.0 + math.exp(-(params["intercept"] + params["coef"] * zc)))


@dataclass
class Analysis:
    name: str
    spread: Spread
    ratios: dict[int, dict]
    covenants: list
    covenant_spec: list[dict]
    stress: list
    floating_share: float
    scorecard_pd: float
    scorecard_points: float
    drivers: list[tuple[str, float, float]]
    altman_z: float
    altman_pd: float
    merton: MertonResult | None
    merton_inputs: dict = field(default_factory=dict)
    model_meta: dict = field(default_factory=dict)
    final_pd: float = math.nan
    grade: tuple[int, str] = (0, "")
    pd_basis: str = ""
    excel_path: Path | None = None
    excel_check: str = ""


def analyze(name: str, spread: Spread, covenants: list[dict] | None = None, floating_share: float = 0.5,
            prices: pd.DataFrame | None = None, risk_free: float = 0.04, models_path: Path | None = None) -> Analysis:
    covenants = covenants or DEFAULT_COVENANTS
    ratios = {fy: compute_ratios(spread.year(fy)) for fy in spread.years}
    y = spread.year()
    cov = test_covenants(ratios[spread.latest_year], covenants)
    stress = run_stress(y, covenants, floating_share)

    sc, alt_params, meta = load_pd_models(models_path)
    feats = spread_to_polish_ratios(y)
    X = pd.DataFrame([feats])[list(SPREAD_FEATURES)]
    sc_pd = float(sc.predict_proba(X)[0])
    points = float(sc.score(X)[0])
    factor = PDO / math.log(2)
    drivers = []
    for c, coef in zip(sc.features, sc.coef_):
        woe = float(sc.bins[c].transform(np.array([feats[c]]))[0])
        drivers.append((c, feats[c], -factor * coef * woe))
    drivers.sort(key=lambda t: t[2])

    z = float(z_double_prime(feats["Attr3"], feats["Attr6"], feats["Attr7"], feats["Attr8"]))
    a_pd = altman_pd(z, alt_params)

    merton, m_in = None, {}
    if prices is not None and len(prices) > 60 and spread.shares_outstanding:
        last = prices.iloc[-1]
        E = float(last["adj_close"]) * spread.shares_outstanding
        sigma_E = equity_volatility(prices["adj_close"].to_numpy())
        D = default_point(y["short_term_borrowings"] + y["current_portion_ltd"], y["long_term_debt"])
        if D > 0:
            merton = solve_merton(E, sigma_E, D, r=risk_free, T=1.0)
            m_in = {"price_date": str(last["date"].date()), "price": float(last["adj_close"]),
                    "shares": spread.shares_outstanding, "E": E, "sigma_E": sigma_E, "D": D, "r": risk_free}

    a = Analysis(name, spread, ratios, cov, covenants, stress, floating_share, sc_pd, points, drivers, z, a_pd,
                 merton, m_in, meta)
    candidates = [("scorecard", sc_pd)] + ([("Merton", merton.pd)] if merton else [])
    basis, final = max(candidates, key=lambda t: t[1])
    a.final_pd, a.grade = final, rating_bucket(final)
    a.pd_basis = basis
    return a


def _m(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v / 1e6:,.1f}"


def _ratio(key: str, v: float) -> str:
    if isinstance(v, float) and math.isinf(v):
        return "n/m"
    if key in AMOUNT_RATIOS:
        return _m(v)
    if key == "ebitda_margin":
        return f"{v:.1%}"
    return f"{v:.2f}x"


def _headroom(h: float) -> str:
    if math.isinf(h):
        return "n/m"
    return f"{h:+.1%}"


def write_outputs(a: Analysis, out_dir: Path, slug: str, recalc: bool = True) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = build_workbook(a.spread, a.ratios, a.covenants, a.stress, out_dir / f"{slug}_spread.xlsx")
    a.excel_path = xlsx
    if recalc and soffice_path():
        recalced = recalculate(xlsx)
        problems = compare_with_python(recalced, a.ratios)
        n = sum(len(r) for r in a.ratios.values())
        a.excel_check = (f"{n} ratio formula cells recalculated in headless LibreOffice; "
                         + ("all match the Python values (relative tolerance 1e-9)." if not problems
                            else f"{len(problems)} mismatches: " + "; ".join(problems[:5])))
        recalced.replace(xlsx)  # keep the recalculated workbook so cached values show in any viewer
        recalced.parent.rmdir() if not any(recalced.parent.iterdir()) else None
    else:
        a.excel_check = "Formulas not recalculated (LibreOffice not installed); open in Excel to calculate."
    md = out_dir / f"{slug}_memo.md"
    md.write_text(render_memo(a, xlsx.name))
    return md, xlsx


def render_memo(a: Analysis, xlsx_name: str) -> str:
    s = a.spread
    years = s.years
    fy = s.latest_year
    r = a.ratios[fy]
    n_breach = sum(not c.passed for c in a.covenants)
    first_breaks = [x for x in a.stress if x.breaking_shock not in (None, 0.0)]
    tightest = {}
    for x in first_breaks:
        if x.scenario not in tightest or x.breaking_shock < tightest[x.scenario].breaking_shock:
            tightest[x.scenario] = x
    L = [f"# Credit memo: {a.spread.company}", ""]
    L += [f"Borrower key: `{a.name}`" + (f" · CIK {s.cik}" if s.cik else "") +
          f" · latest fiscal year FY{fy} (period end {s.period_ends[fy]}) · amounts in $ millions", ""]
    L += ["## 1. Summary", ""]
    L += [f"- **Risk grade: {a.grade[0]} – {a.grade[1]}** on PD {a.final_pd:.2%} "
          f"(the more conservative of the scorecard and Merton PDs; basis: {a.pd_basis}).",
          f"- Leverage {_ratio('debt_to_ebitda', r['debt_to_ebitda'])} Debt/EBITDA, "
          f"{_ratio('net_leverage', r['net_leverage'])} net; interest coverage {_ratio('interest_coverage', r['interest_coverage'])}; "
          f"FCCR {_ratio('fccr', r['fccr'])}; free cash flow ${_m(r['free_cash_flow'])}M.",
          f"- Covenants: {len(a.covenants) - n_breach} of {len(a.covenants)} pass at FY{fy}"
          + (f"; **{n_breach} breached**." if n_breach else ".")]
    for scen, x in tightest.items():
        L.append(f"- Stress, {SCENARIOS[scen]['label'].lower()}: first covenant to break is *{x.covenant}* {x.status.replace('breaks ', '')}.")
    L.append(f"- Altman Z'' = {a.altman_z:.2f} ({zone(a.altman_z)} zone); scorecard PD {a.scorecard_pd:.2%}"
             + (f"; Merton PD {a.merton.pd:.2%} (distance-to-default {a.merton.distance_to_default:.2f})." if a.merton
                else "; no traded equity, so no Merton estimate."))
    L += ["", "## 2. Financial spread", "",
          "| Line item | " + " | ".join(f"FY{y}" for y in years) + " |",
          "|---|" + "---:|" * len(years)]
    for item in LINE_ITEMS:
        L.append(f"| {LINE_LABELS[item]} | " + " | ".join(_m(s.values.at[item, y]) for y in years) + " |")
    L += ["", "## 3. Credit ratios", "",
          "| Ratio | " + " | ".join(f"FY{y}" for y in years) + " |", "|---|" + "---:|" * len(years)]
    for key, label in RATIO_LABELS.items():
        L.append(f"| {label} | " + " | ".join(_ratio(key, a.ratios[y][key]) for y in years) + " |")
    L += ["", "EBITDA and EBIT coverage add back non-cash impairments. n/m = not meaningful (EBITDA or denominator ≤ 0).", ""]
    L += [f"## 4. Covenant compliance (FY{fy})", "",
          "| Covenant | Test | Threshold | Actual | Headroom | Status |", "|---|---|---:|---:|---:|---|"]
    for c in a.covenants:
        L.append(f"| {c.name} | {RATIO_LABELS[c.metric]} {c.op} | {c.threshold:.2f}x | {_ratio(c.metric, c.value)} | "
                 f"{_headroom(c.headroom)} | {'PASS' if c.passed else '**BREACH**'} |")
    L += ["", "Headroom is the distance to the threshold as a share of the threshold.", ""]
    L += ["## 5. Stress tests", "",
          f"Shock size at which each covenant first breaks, found by root-finding (Brent's method). "
          f"Rate shock applies to the floating share of debt ({a.floating_share:.0%}); revenue decline flexes "
          f"cost of goods only, so EBITDA falls by the gross margin on lost revenue.", "",
          "| Covenant | " + " | ".join(m["label"] for m in SCENARIOS.values()) + " |", "|---|" + "---|" * len(SCENARIOS)]
    for c in a.covenant_spec:
        cells = [next(x.status for x in a.stress if x.scenario == sc and x.covenant == c["name"]) for sc in SCENARIOS]
        L.append(f"| {c['name']} | " + " | ".join(cells) + " |")
    L += ["", "## 6. Probability of default", "",
          f"**Scorecard** (WoE logistic regression trained on {a.model_meta.get('dataset', 'UCI Polish data')}, "
          f"{a.model_meta.get('n_train', '?'):,} firm-years): PD **{a.scorecard_pd:.2%}**, {a.scorecard_points:.0f} points "
          f"(600 points = 50:1 odds, 20 points to double the odds).", "",
          "| Ratio | Definition | Value | Points vs neutral |", "|---|---|---:|---:|"]
    for c, v, pts in a.drivers:
        L.append(f"| {c} | {SPREAD_FEATURES[c]} | {v:.3f} | {pts:+.1f} |")
    L += ["", f"**Altman Z''**: {a.altman_z:.2f} → {zone(a.altman_z)} zone (safe > 2.60, distress < 1.10); "
          f"PD via logistic map fitted on the same training data: {a.altman_pd:.2%}.", ""]
    if a.merton:
        m, mi = a.merton, a.merton_inputs
        L += [f"**Merton distance-to-default** (market data to {mi['price_date']}):", "",
              "| Input / output | Value |", "|---|---:|",
              f"| Equity value E (price {mi['price']:.2f} × {mi['shares'] / 1e6:,.1f}M shares) | {_m(mi['E'])} |",
              f"| Equity volatility σE (252-day, annualized) | {mi['sigma_E']:.1%} |",
              f"| Default point D (short-term debt + ½ long-term debt) | {_m(mi['D'])} |",
              f"| Risk-free rate r, horizon T | {mi['r']:.1%}, 1 year |",
              f"| Asset value V | {_m(m.asset_value)} |",
              f"| Asset volatility σV | {m.asset_vol:.1%} |",
              f"| Distance-to-default | {m.distance_to_default:.2f} |",
              f"| Implied 1-year PD N(−DD) | {m.pd:.3%} |", ""]
    else:
        L += ["**Merton**: not applicable – no traded equity price series for this borrower.", ""]
    L += [f"**Risk grade {a.grade[0]}** ({a.grade[1]}) on an illustrative 10-grade master scale; the grade uses the higher "
          "of the scorecard and Merton PDs.", ""]
    L += ["## 7. Data sources and checks", "",
          f"- Excel spread: `{xlsx_name}` (Spread inputs in blue; Ratios and Covenants are live formulas). {a.excel_check}",
          "- XBRL tags behind the latest-year spread:", ""]
    L += ["| Line item | Source |", "|---|---|"]
    L += [f"| {LINE_LABELS[i]} | `{s.sources[(i, fy)]}` |" for i in LINE_ITEMS]
    if s.notes:
        L += ["", "Notes: " + "; ".join(s.notes)]
    L += ["", "Caveats: the scorecard was trained on Polish manufacturing firms, so its PD level is a relative-risk "
          "signal for US borrowers rather than a calibrated 1-year PD; EBITDA is reported, with only impairment add-backs; "
          "stress tests hold taxes, capex and the balance sheet at base values.", ""]
    return "\n".join(L)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
