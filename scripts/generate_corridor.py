#!/usr/bin/env python3
"""Generate the corridor fixture datasets under fixtures/.

Run from the backend environment:

    cd backend && uv run python ../scripts/generate_corridor.py

Deterministic: regenerating with the same specs produces byte-identical
assets. corridor-b is the held-out evaluation dataset — do not use it for the
demo or for tuning.
"""

import sys
from pathlib import Path

from cateniq.datasets.gen import DatasetSpec, PoleSpec, SpanSpec, generate_dataset

STD_CANDIDATES = (("high", 12.0), ("mid", 10.5), ("low", 8.5))

CORRIDOR_A = DatasetSpec(
    dataset_id="corridor-a",
    seed=20261022,
    role="demo",
    poles=(
        PoleSpec("P1", 0.0, 13.5, STD_CANDIDATES),
        PoleSpec("P2", 50.0, 13.5, STD_CANDIDATES),
        PoleSpec("P3", 95.0, 13.5, STD_CANDIDATES),
        PoleSpec("P4", 150.0, 14.5, (("high", 13.0), ("mid", 11.5), ("low", 9.0))),
        PoleSpec("P5", 205.0, 13.5, STD_CANDIDATES),
    ),
    spans=(
        # Nominal clean span.
        SpanSpec("S1", "P1", "P2", "high", "high", a=800.0, sigma=0.03, n=350),
        # Demo span: predicted endpoint displaced to the mid crossarm (-1.5 m).
        SpanSpec("S2", "P2", "P3", "high", "high", a=900.0, sigma=0.035, n=400,
                 predicted_b="mid"),
        # Unequal support heights inside the supported model.
        SpanSpec("S3", "P3", "P4", "high", "high", a=700.0, sigma=0.04, n=320),
        # High-noise span: fits, but residual quality is borderline/failing.
        SpanSpec("S4", "P4", "P5", "high", "high", a=1400.0, sigma=0.18, n=300),
    ),
)

CORRIDOR_B = DatasetSpec(
    dataset_id="corridor-b",
    seed=777,
    role="evaluation-holdout",
    poles=(
        PoleSpec("Q1", 0.0, 13.0, (("high", 11.5), ("mid", 10.0), ("low", 8.0))),
        PoleSpec("Q2", 48.0, 13.0, (("high", 11.5), ("mid", 10.0), ("low", 8.0))),
        PoleSpec("Q3", 92.0, 14.0, (("high", 12.5), ("mid", 11.0), ("low", 9.0))),
        PoleSpec("Q4", 140.0, 12.5, (("high", 11.0), ("mid", 9.5), ("low", 7.5))),
    ),
    spans=(
        SpanSpec("B1", "Q1", "Q2", "high", "high", a=650.0, sigma=0.03, n=300),
        SpanSpec("B2", "Q2", "Q3", "high", "high", a=950.0, sigma=0.04, n=280),
        SpanSpec("B3", "Q3", "Q4", "high", "high", a=1400.0, sigma=0.05, n=280),
    ),
)

CORRIDOR_ADVERSE = DatasetSpec(
    dataset_id="corridor-adverse",
    seed=31337,
    role="adverse",
    poles=(
        PoleSpec("R1", 0.0, 13.5, STD_CANDIDATES),
        PoleSpec("R2", 50.0, 13.5, STD_CANDIDATES),
        PoleSpec("R3", 100.0, 13.5, STD_CANDIDATES),
    ),
    spans=(
        # Occluded middle: 30% gap exceeds the 25% gate -> insufficient evidence.
        SpanSpec("A1", "R1", "R2", "high", "high", a=800.0, sigma=0.05, n=220,
                 u_windows=((0.0, 0.35), (0.65, 1.0))),
        # Sparse evidence: below the minimum point count -> insufficient.
        SpanSpec("A2", "R2", "R3", "high", "high", a=900.0, sigma=0.04, n=14),
    ),
)

SPECS = (CORRIDOR_A, CORRIDOR_B, CORRIDOR_ADVERSE)


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "fixtures"
    for spec in SPECS:
        root = generate_dataset(out, spec)
        print(f"wrote {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
