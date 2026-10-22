#!/usr/bin/env python3
"""Generate the ~100k-point performance workload used by the e2e perf spec.

Not committed — generated on demand so the repo stays small:

    cd backend && uv run python ../scripts/generate_perf_corridor.py .perf-fixtures
"""

import sys
from pathlib import Path

from generate_corridor import SPECS

from cateniq.datasets.gen import DatasetSpec, PoleSpec, SpanSpec, generate_dataset

STD = (("high", 12.0), ("mid", 10.5), ("low", 8.5))

# 10 poles, 9 spans x 11k conductor points = ~99k + ~1.2k context = ~100k.
CORRIDOR_PERF = DatasetSpec(
    dataset_id="corridor-perf",
    seed=99,
    role="perf-workload",
    poles=tuple(
        PoleSpec(f"K{i}", 45.0 * i, 13.5, STD) for i in range(10)
    ),
    spans=tuple(
        SpanSpec(
            f"K{i}-{i+1}", f"K{i}", f"K{i+1}", "high", "high",
            a=800.0 + 50 * i, sigma=0.04, n=11000,
        )
        for i in range(9)
    ),
)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".perf-fixtures")
    for spec in (*SPECS, CORRIDOR_PERF):
        root = generate_dataset(out, spec)
        print(f"wrote {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
