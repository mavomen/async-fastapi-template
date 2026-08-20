#!/usr/bin/env python3
"""Compare pytest-benchmark JSON output against a stored baseline.

Exit codes:
  0 — no regressions (or baseline created)
  1 — performance regression detected

Usage:
  python scripts/compare_benchmarks.py benchmark.json [--p95-budget 500]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BASELINE = Path("benchmarks/baseline.json")
THRESHOLD_PCT_DEFAULT = 20


def load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "benchmark_file",
        nargs="?",
        default="benchmark.json",
        help="Path to the new benchmark JSON file",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=THRESHOLD_PCT_DEFAULT,
        help=f"Max percentage increase allowed vs baseline (default: {THRESHOLD_PCT_DEFAULT}%%)",
    )
    parser.add_argument(
        "--p95-budget",
        type=float,
        default=None,
        help="Hard p95 latency budget in milliseconds (exit 1 if exceeded)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_path = Path(args.benchmark_file)

    new_data = load(new_path)
    if not new_data:
        print("No new benchmark data, exiting.")
        sys.exit(0)

    baseline = load(BASELINE)
    if not baseline:
        new_path.rename(BASELINE)
        print("Created baseline, exiting.")
        sys.exit(0)

    failed = False

    # --- Per-endpoint regression check ---
    new_tests = {b["name"]: b["stats"]["mean"] for b in new_data["benchmarks"]}
    old_tests = {b["name"]: b["stats"]["mean"] for b in baseline["benchmarks"]}

    for name, new_mean in new_tests.items():
        old_mean = old_tests.get(name)
        if old_mean is None:
            continue
        pct_change = ((new_mean / old_mean) - 1) * 100
        if pct_change > args.threshold:
            print(
                f"WARN: {name} {new_mean:.6f}s vs baseline {old_mean:.6f}s "
                f"(+{pct_change:.1f}% > {args.threshold}%)"
            )
            failed = True
        else:
            print(f"OK: {name} {new_mean:.6f}s vs baseline {old_mean:.6f}s ({pct_change:+.1f}%)")

    # --- Hard p95 budget check ---
    if args.p95_budget is not None:
        for bench in new_data["benchmarks"]:
            p95_ms = bench["stats"].get("percentiles", {}).get("p95", 0) * 1000
            if p95_ms > args.p95_budget:
                print(
                    f"BUDGET VIOLATION: {bench['name']} p95={p95_ms:.1f}ms "
                    f"> budget {args.p95_budget:.1f}ms"
                )
                failed = True
            else:
                print(f"BUDGET OK: {bench['name']} p95={p95_ms:.1f}ms <= {args.p95_budget:.1f}ms")

    if failed:
        print("Performance regression detected.")
        sys.exit(1)

    new_path.replace(BASELINE)
    print("Baseline updated.")
    sys.exit(0)


if __name__ == "__main__":
    main()
