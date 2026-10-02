"""Bulk XBRL data-quality screen: XBRL US DQC rules over SEC Financial Statement Data Sets.

Each rule lives in ``credit_engine.dqc.rules.dqc_XXXX`` and exposes ``RULE_ID``,
``TITLE`` and ``check(q) -> DataFrame`` returning rows in
:data:`credit_engine.dqc.base.FINDING_COLS`.
"""

from __future__ import annotations

import importlib
import time

import pandas as pd

from credit_engine.dqc.base import FINDING_COLS
from credit_engine.dqc.fsds import Quarter

RULE_IDS = ["DQC_0001", "DQC_0004", "DQC_0005", "DQC_0008", "DQC_0009", "DQC_0013", "DQC_0014", "DQC_0015",
            "DQC_0036", "DQC_0091", "DQC_0095", "DQC_0125", "DQC_0194", "DQC_0195"]


def rule_module(rule_id: str):
    return importlib.import_module(f"credit_engine.dqc.rules.{rule_id.lower()}")


def run_screen(q: Quarter, rules: list[str] | None = None, timings: dict | None = None) -> pd.DataFrame:
    """Run every rule over a loaded quarter and return all findings."""
    frames = []
    for rid in rules or RULE_IDS:
        t0 = time.perf_counter()
        f = rule_module(rid).check(q)
        if timings is not None:
            timings[rid] = time.perf_counter() - t0
        if len(f):
            frames.append(f)
    if not frames:
        return pd.DataFrame(columns=FINDING_COLS)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["adsh", "rule", "concept", "ddate"]).reset_index(drop=True)
