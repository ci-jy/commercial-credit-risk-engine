"""Run Arelle + XULE with the official DQC ruleset on sample filings and record the findings.

Steps (each is idempotent, so an interrupted run can be resumed):

    python scripts/dqc_arelle_harness.py select --quarter 2026q2 --n 30 --seed 7
    python scripts/dqc_arelle_harness.py run --workers 3
    python scripts/dqc_arelle_harness.py fixtures --quarter 2026q2
    python scripts/dqc_arelle_harness.py cal

``select`` samples 10-K/10-Q filings from a downloaded Financial Statement Data
Set quarter (``--add`` appends specific accession numbers). ``run`` downloads
each filing's XBRL zip from EDGAR and validates it with
``arelleCmdLine --plugins "validate/DQC|EDGAR/transform"``, writing one compact
JSON per filing to ``fixtures/dqc/arelle/``. ``fixtures`` writes the sample
filings' rows of sub/num/pre to ``fixtures/dqc/fsds_sample/`` so the
differential tests run offline.

Arelle is expected in ``.venv`` (``pip install arelle-release``) with the XULE
plugin and ``validate/DQC.py`` from github.com/xbrlus/xule and the EDGAR plugin
from github.com/Arelle/EDGAR copied into ``arelle/plugin``; the compiled
rulesets come from github.com/DataQualityCommittee/dqc_us_rules (v30).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from credit_engine.dqc.fsds import load_quarter, quarter_path, write_sample  # noqa: E402
from credit_engine.edgar import user_agent  # noqa: E402

ARELLE = REPO / ".venv" / "bin" / "arelleCmdLine"
RULESETS = REPO / "data" / "dqc_us_rules" / "dqc_us_rules"
FILINGS = REPO / "data" / "filings"
OUT = REPO / "fixtures" / "dqc" / "arelle"
SAMPLE = REPO / "fixtures" / "dqc" / "sample_filings.csv"
ZIP_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{adsh}-xbrl.zip"


def cmd_select(args) -> None:
    q = load_quarter(quarter_path(args.quarter), tables=("sub",))
    sub = q.sub
    pool = sub[sub.form.isin(["10-K", "10-Q"]) & sub.instance.notna()]
    rows = []
    if SAMPLE.exists():
        rows.append(pd.read_csv(SAMPLE, dtype=str))
    if args.n:
        rows.append(pool.groupby("form", group_keys=False)
                    .apply(lambda g: g.sample(min(len(g), args.n // 2), random_state=args.seed)))
    if args.add:
        rows.append(pool[pool.adsh.isin(args.add)])
    out = pd.concat(rows)[["adsh", "cik", "name", "form", "period", "afs"]].astype(str)
    out = out.drop_duplicates("adsh")
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SAMPLE, index=False)
    print(f"{len(out)} filings -> {SAMPLE}")


def _flatten(props) -> dict:
    out = {}
    for p in props or []:
        out[p[0]] = (p[1], _flatten(p[2]) if len(p) > 2 else {})
    return out


def parse_log(log: list[dict]) -> list[dict]:
    """Compact DQC findings: rule, concept, period, dimensions, value and message."""
    findings = []
    for e in log:
        code = e.get("code", "")
        m = re.match(r"DQC\.US\.(\d{4})\.(\d+)", code)
        if not m:
            continue
        ref = next((r for r in e.get("refs", []) if r.get("properties")), {})
        p = _flatten(ref.get("properties"))
        ctx = p.get("contextRef", ("", {}))[1]
        dims = {k: v[0] for k, v in ctx.get("dimensions", ("", {}))[1].items()}
        findings.append({
            "code": code,
            "rule": f"DQC_{m.group(1)}",
            "element_id": m.group(2),
            "concept": p.get("name", ("", {}))[0],
            "start": ctx.get("startDate", ("", {}))[0],
            "end": ctx.get("endDate", ctx.get("instant", ("", {})))[0],
            "dims": dims,
            "value": p.get("value", ("", {}))[0],
            "decimals": p.get("decimals", ("", {}))[0],
            "message": e.get("message", {}).get("text", "")[:600],
        })
    return findings


def _ruleset_for(version: str) -> Path:
    year = (version or "us-gaap/2025").split("/")[-1]
    path = RULESETS / f"dqc-us-{year}-V30-ruleset.zip"
    return path if path.exists() else RULESETS / "dqc-us-2025-V30-ruleset.zip"


def run_one(row: dict) -> str:
    adsh, cik = row["adsh"], int(row["cik"])
    dest = OUT / f"{adsh}.json"
    if dest.exists():
        return f"{adsh} cached"
    zpath = _download(adsh, cik)
    ruleset = _ruleset_for(row.get("gaap_version", ""))
    log_path = REPO / "data" / "arelle" / f"{adsh}.log.json"
    env = dict(os.environ, XDG_CONFIG_HOME=str(REPO / "data" / "arelle" / "config"))
    for _attempt in range(2):
        log_path.unlink(missing_ok=True)  # Arelle appends to an existing log file
        t0 = time.perf_counter()
        proc = subprocess.run([str(ARELLE), "--plugins", "validate/DQC|EDGAR/transform", "-f", str(zpath), "-v",
                               "--xule-rule-set", str(ruleset), "--logFile", str(log_path)],
                              env=env, capture_output=True, text=True, timeout=1800)
        elapsed = time.perf_counter() - t0
        if log_path.exists():
            break
    else:
        return f"{adsh} FAILED: {(proc.stderr or proc.stdout)[-300:]}"
    log = json.loads(log_path.read_text())["log"]
    load_s = sum(float(m.group(1)) for e in log
                 if (m := re.search(r"loaded in ([\d.]+) secs", e.get("message", {}).get("text", ""))))
    dest.write_text(json.dumps({
        "adsh": adsh, "ruleset": ruleset.name, "runtime_s": round(elapsed, 2), "load_s": round(load_s, 2),
        "findings": parse_log(log),
    }, indent=1))
    return f"{adsh} {elapsed:.0f}s"


def cmd_run(args) -> None:
    sample = pd.read_csv(SAMPLE, dtype=str)
    versions = {}
    vpath = REPO / "fixtures" / "dqc" / "gaap_versions.json"
    if vpath.exists():
        versions = json.loads(vpath.read_text())
    rows = [dict(r, gaap_version=versions.get(r["adsh"], "")) for r in sample.to_dict("records")]
    OUT.mkdir(parents=True, exist_ok=True)
    def safe(row):
        try:
            return run_one(row)
        except Exception as err:  # keep going; the filing is retried on the next run
            return f"{row['adsh']} FAILED: {err!r}"

    with ThreadPoolExecutor(args.workers) as ex:
        for msg in ex.map(safe, rows):
            print(msg, flush=True)


def _download(adsh: str, cik: int) -> Path:
    FILINGS.mkdir(parents=True, exist_ok=True)
    zpath = FILINGS / f"{adsh}.zip"
    if not zpath.exists():
        url = ZIP_URL.format(cik=cik, nodash=adsh.replace("-", ""), adsh=adsh)
        req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
        with urllib.request.urlopen(req, timeout=120) as resp:
            zpath.write_bytes(resp.read())
        time.sleep(0.2)
    return zpath


def cmd_inspect(args) -> None:
    """Print every fact of a concept in a filing's inline XBRL with its exact context (for root-causing)."""
    import zipfile

    sample = pd.read_csv(SAMPLE, dtype=str).set_index("adsh")
    z = zipfile.ZipFile(_download(args.adsh, int(sample.loc[args.adsh, "cik"])))
    for name in z.namelist():
        if not name.endswith(".htm"):
            continue
        text = z.read(name).decode("utf-8", "replace")
        contexts = {m.group(1): m.group(2) for m in
                    re.finditer(r'<xbrli:context id="([^"]*)">(.*?)</xbrli:context>', text, re.S)}
        for m in re.finditer(r"<ix:nonFraction[^>]*>", text):
            tag = m.group(0)
            if f':{args.concept}"' not in tag:
                continue
            ref = re.search(r'contextRef="([^"]*)"', tag).group(1)
            ctx = contexts.get(ref, "")
            dates = re.findall(r"<xbrli:(startDate|endDate|instant)>([^<]*)<", ctx)
            dims = re.findall(r'dimension="([^"]*)">([^<]*)<', ctx)
            sign = "-" if 'sign="-"' in tag else ""
            value = text[m.end(): text.find("<", m.end())]
            print(name, ref, dates, dims, sign + value)


def cmd_cal(args) -> None:
    """Write fixtures/dqc/fsds_sample/cal.txt.gz from each sample filing's calculation linkbase.

    Same layout as the cal table of the SEC "Financial Statement and Notes" data sets:
    one row per calculation arc; ``negative`` = 1 for weight -1; ``*version`` is
    ``us-gaap/YYYY`` for base concepts and the accession number for extensions.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    lb, xl = "{http://www.xbrl.org/2003/linkbase}", "{http://www.w3.org/1999/xlink}"
    sample = pd.read_csv(SAMPLE, dtype=str)
    versions = json.loads((REPO / "fixtures" / "dqc" / "gaap_versions.json").read_text())
    rows = []
    for r in sample.itertuples():
        z = zipfile.ZipFile(_download(r.adsh, int(r.cik)))
        for name in [n for n in z.namelist() if n.endswith("_cal.xml")]:
            root = ET.fromstring(z.read(name))
            for grp, link in enumerate(root.iter(f"{lb}calculationLink"), start=1):
                locs = {}
                for loc in link.iter(f"{lb}loc"):
                    frag = loc.get(f"{xl}href", "").split("#")[-1]
                    prefix, _, local = frag.partition("_")
                    ver = versions.get(r.adsh, "us-gaap/2025") if prefix == "us-gaap" else (
                        f"{prefix}/" if prefix in ("srt", "dei") else r.adsh)
                    locs[loc.get(f"{xl}label")] = (local, ver)
                for arc_no, arc in enumerate(link.iter(f"{lb}calculationArc"), start=1):
                    (pt, pv), (ct, cv) = locs[arc.get(f"{xl}from")], locs[arc.get(f"{xl}to")]
                    rows.append((r.adsh, grp, arc_no, int(float(arc.get("weight")) < 0), pt, pv, ct, cv))
    out = REPO / "fixtures" / "dqc" / "fsds_sample" / "cal.txt.gz"
    pd.DataFrame(rows, columns=["adsh", "grp", "arc", "negative", "ptag", "pversion", "ctag", "cversion"]) \
        .to_csv(out, sep="\t", index=False)
    print(f"{len(rows)} calculation arcs -> {out}")


def cmd_reparse(args) -> None:
    """Rebuild the compact fixtures from the raw Arelle logs in data/arelle/ (keeps runtimes)."""
    for path in sorted(OUT.glob("*.json")):
        d = json.loads(path.read_text())
        log_path = REPO / "data" / "arelle" / f"{d['adsh']}.log.json"
        if log_path.exists():
            d["findings"] = parse_log(json.loads(log_path.read_text())["log"])
            path.write_text(json.dumps(d, indent=1))
    print("reparsed")


def cmd_fixtures(args) -> None:
    sample = pd.read_csv(SAMPLE, dtype=str)
    q = load_quarter(quarter_path(args.quarter), adsh=set(sample.adsh))
    write_sample(q, set(sample.adsh), REPO / "fixtures" / "dqc" / "fsds_sample")
    num = q.num[q.num.adsh.isin(set(sample.adsh)) & q.num.version.astype(str).str.startswith("us-gaap/")]
    versions = num.groupby("adsh", observed=True).version.agg(lambda s: s.astype(str).mode().iat[0])
    (REPO / "fixtures" / "dqc" / "gaap_versions.json").write_text(json.dumps(versions.to_dict(), indent=1))
    print(f"wrote fixtures for {len(sample)} filings")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--quarter", default="2026q2")
    s.add_argument("--n", type=int, default=0)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--add", nargs="*", default=[])
    s.set_defaults(func=cmd_select)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=3)
    r.set_defaults(func=cmd_run)
    sub.add_parser("reparse").set_defaults(func=cmd_reparse)
    sub.add_parser("cal").set_defaults(func=cmd_cal)
    i = sub.add_parser("inspect")
    i.add_argument("adsh")
    i.add_argument("concept")
    i.set_defaults(func=cmd_inspect)
    f = sub.add_parser("fixtures")
    f.add_argument("--quarter", default="2026q2")
    f.set_defaults(func=cmd_fixtures)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
