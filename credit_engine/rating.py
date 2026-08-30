"""Illustrative 10-grade PD master scale (not any agency's or bank's methodology).

Upper PD bounds per grade, with the broad agency-style letter band each grade
roughly corresponds to, for orientation only.
"""

from __future__ import annotations

MASTER_SCALE = [
    (1, 0.0003, "Minimal risk (AAA/AA)"),
    (2, 0.0010, "Very low risk (A)"),
    (3, 0.0025, "Low risk (BBB+)"),
    (4, 0.0050, "Moderate risk (BBB/BBB-)"),
    (5, 0.0100, "Acceptable risk (BB+)"),
    (6, 0.0200, "Elevated risk (BB)"),
    (7, 0.0500, "Watch (B+/B)"),
    (8, 0.1000, "Special mention (B-)"),
    (9, 0.2000, "Substandard (CCC)"),
    (10, 1.0000, "Doubtful (CC/C)"),
]


def rating_bucket(pd_value: float) -> tuple[int, str]:
    for grade, upper, label in MASTER_SCALE:
        if pd_value < upper:
            return grade, label
    return MASTER_SCALE[-1][0], MASTER_SCALE[-1][2]
