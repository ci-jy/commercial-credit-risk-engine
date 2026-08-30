"""Command-line interface: ``credit-engine memo`` and ``credit-engine benchmark``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from credit_engine.benchmark import metrics_table, run_benchmark
from credit_engine.edgar import fetch_companyfacts, load_borrowers, load_fixture
from credit_engine.memo import analyze, slugify, write_outputs
from credit_engine.prices import download_prices, load_prices, write_prices
from credit_engine.spreading import spread_companyfacts


def cmd_memo(args) -> int:
    registry = load_borrowers()
    if args.fixture:
        if args.fixture not in registry:
            print(f"unknown fixture {args.fixture!r}; choose from {', '.join(registry)}", file=sys.stderr)
            return 2
        key, info = args.fixture, registry[args.fixture]
        data = load_fixture(args.fixture)
    else:
        match = [(k, v) for k, v in registry.items() if v.get("cik") == int(args.cik)]
        key, info = match[0] if match else (None, {})
        data = fetch_companyfacts(args.cik, cache_dir=Path("data/edgar"))
        key = key or slugify(data.get("entityName", f"cik{args.cik}"))
    spread = spread_companyfacts(data, n_years=args.years)

    covenants = info.get("covenants")
    if args.covenants:
        covenants = json.loads(Path(args.covenants).read_text())
    ticker = args.ticker or info.get("ticker")
    prices = None
    if args.prices:
        prices = load_prices(ticker or "", Path(args.prices))
    elif ticker:
        prices = load_prices(ticker)
        if prices is None and not args.fixture:
            path = Path("data/prices") / f"{ticker}.csv"
            write_prices(download_prices(ticker), path)
            prices = load_prices(ticker, path)
    floating = args.floating_share if args.floating_share is not None else info.get("floating_rate_share", 0.5)

    a = analyze(key, spread, covenants, floating, prices, risk_free=args.risk_free)
    md, xlsx = write_outputs(a, Path(args.out), key, recalc=not args.no_recalc)
    print(f"{spread.company}: grade {a.grade[0]} ({a.grade[1]}), PD {a.final_pd:.2%}")
    print(f"memo  -> {md}\nexcel -> {xlsx}\n{a.excel_check}")
    return 0


def cmd_benchmark(args) -> int:
    res = run_benchmark(offline=args.offline_fixtures, quick=args.quick,
                        out_dir=Path(args.out) if args.out else None)
    meta = res["meta"]
    print(f"{meta['dataset']}: {meta['n_rows']:,} rows, {meta['n_test']:,} held out, {meta['n_boot']} bootstraps "
          f"({meta['elapsed_s']}s)")
    print(metrics_table(res["metrics"]))
    for r in res["metrics"][res["metrics"].metric == "auc_diff"].itertuples():
        print(f"AUC {r.model}: {r.estimate:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]")
    print(f"report -> {res['out_dir'] / 'benchmark.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="credit-engine", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("memo", help="spread a borrower and write a credit memo + Excel spread")
    src = m.add_mutually_exclusive_group(required=True)
    src.add_argument("--cik", help="SEC CIK of a public borrower (fetched live from EDGAR)")
    src.add_argument("--fixture", help="recorded borrower from fixtures/borrowers.json (offline)")
    m.add_argument("--out", default="out", help="output directory")
    m.add_argument("--ticker", help="equity ticker for Merton (default: from the borrower registry)")
    m.add_argument("--prices", help="CSV of daily prices with columns date,adj_close")
    m.add_argument("--covenants", help="JSON list of covenants {name, metric, op, threshold}")
    m.add_argument("--floating-share", type=float, help="share of debt at floating rates for the rate shock")
    m.add_argument("--risk-free", type=float, default=0.04, help="risk-free rate for Merton")
    m.add_argument("--years", type=int, default=4, help="fiscal years to spread")
    m.add_argument("--no-recalc", action="store_true", help="skip LibreOffice recalculation of the Excel spread")
    m.set_defaults(func=cmd_memo)

    b = sub.add_parser("benchmark", help="scorecard vs Altman Z'' vs gradient boosting on UCI Polish data")
    b.add_argument("--offline-fixtures", action="store_true", help="use the committed 8,000-row sample")
    b.add_argument("--quick", action="store_true", help="200 bootstraps and a smaller boosting model")
    b.add_argument("--out", help="output directory (default reports/, or out/benchmark offline)")
    b.set_defaults(func=cmd_benchmark)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
