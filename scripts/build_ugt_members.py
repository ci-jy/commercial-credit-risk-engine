"""Extract axis -> allowed members from the US GAAP 2025 taxonomy, for DQC_0001.

Reads the taxonomy definition linkbases (``dimension-domain`` and ``domain-member``
arcs) from Arelle's cache, as filled by ``scripts/dqc_arelle_harness.py run``, and
writes ``credit_engine/dqc/resources/ugt_2025_axis_members.json`` with:

* ``axes``: data-set axis name -> sorted member names (all domain-member
  descendants of the axis across every network, plus the domain itself)
* ``base_members``: every us-gaap/srt element whose name ends in ``Member``
* ``calc``: every US GAAP calculation relationship ``[parent, child, weight]``
  from the ``*-cal-2025.xml`` linkbases (used by DQC_0008)

Names use the data-set form (no prefix, no ``Axis``/``Member`` suffix).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "data" / "arelle" / "config" / "arelle" / "cache" / "https" / "xbrl.fasb.org"
OUT = REPO / "credit_engine" / "dqc" / "resources" / "ugt_2025_axis_members.json"
XLINK = "{http://www.w3.org/1999/xlink}"
AXES = ["StatementEquityComponentsAxis", "ConsolidationItemsAxis", "StatementBusinessSegmentsAxis",
        "SubsequentEventTypeAxis", "RangeAxis", "FairValueByFairValueHierarchyLevelAxis", "MajorCustomersAxis",
        "StatementScenarioAxis"]


def short(name: str, suffix: str) -> str:
    return name[: -len(suffix)] if name.endswith(suffix) else name


def fsds_axis(axis: str) -> str:
    a = short(axis, "Axis")
    return a[len("Statement"):] if a.startswith("Statement") else a


def main() -> None:
    children: dict[str, set[str]] = defaultdict(set)
    for path in CACHE.glob("us-gaap/2025/**/*-def-2025.xml"):
        root = ET.parse(path).getroot()
        for link in root.iter("{http://www.xbrl.org/2003/linkbase}definitionLink"):
            locs = {}
            for loc in link.iter("{http://www.xbrl.org/2003/linkbase}loc"):
                href = loc.get(f"{XLINK}href", "")
                locs[loc.get(f"{XLINK}label")] = re.sub(r"^[a-z-]+_", "", href.split("#")[-1])
            for arc in link.iter("{http://www.xbrl.org/2003/linkbase}definitionArc"):
                role = arc.get(f"{XLINK}arcrole", "")
                if role.endswith("/dimension-domain") or role.endswith("/domain-member"):
                    children[locs[arc.get(f"{XLINK}from")]].add(locs[arc.get(f"{XLINK}to")])
    axes = {}
    for axis in AXES:
        seen, stack = set(), list(children.get(axis, ()))
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(children.get(n, ()))
        axes[fsds_axis(axis)] = sorted(short(m, "Member") for m in seen)
    base = set()
    for xsd in (CACHE / "us-gaap/2025/elts/us-gaap-2025.xsd", CACHE / "srt/2025/elts/srt-2025.xsd"):
        for el in ET.parse(xsd).getroot().iter("{http://www.w3.org/2001/XMLSchema}element"):
            name = el.get("name", "")
            if name.endswith("Member"):
                base.add(short(name, "Member"))
    calc = set()
    for path in CACHE.glob("us-gaap/2025/**/*-cal-2025.xml"):
        root = ET.parse(path).getroot()
        for link in root.iter("{http://www.xbrl.org/2003/linkbase}calculationLink"):
            locs = {}
            for loc in link.iter("{http://www.xbrl.org/2003/linkbase}loc"):
                href = loc.get(f"{XLINK}href", "")
                locs[loc.get(f"{XLINK}label")] = re.sub(r"^[a-z-]+_", "", href.split("#")[-1])
            for arc in link.iter("{http://www.xbrl.org/2003/linkbase}calculationArc"):
                calc.add((locs[arc.get(f"{XLINK}from")], locs[arc.get(f"{XLINK}to")], float(arc.get("weight"))))
    OUT.write_text(json.dumps({"taxonomy": "us-gaap 2025", "axes": axes, "base_members": sorted(base),
                               "calc": sorted(list(c) for c in calc)}, indent=0))
    print({k: len(v) for k, v in axes.items()}, len(base), len(calc))


if __name__ == "__main__":
    main()
