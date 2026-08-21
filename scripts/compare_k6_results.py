#!/usr/bin/env python3
"""Compare k6 JSON summary output against a stored baseline.

Handles the JSON format produced by k6's --out json flag, which emits
one JSON object per line (JSON Lines / NDJSON).

Exit codes:
  0 — no regressions
  1 — performance regression detected

Usage:
  python scripts/compare_k6_results.py results.json --baseline baseline.json --p95-budget 500
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    """Load a JSON Lines file (one JSON object per line)."""
    entries: list[dict[str, Any]] = []
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped:
            with contextlib.suppress(json.JSONDecodeError):
                entries.append(json.loads(stripped))
    return entries


def aggregate_p95(entries: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate p95 latency per metric name from k6 JSON lines output."""
    buckets: dict[str, list[float]] = {}
    for entry in entries:
        if entry.get("type") != "Point":
            continue
        metric = entry.get("metric", "")
        value = entry.get("data", {}).get("value", 0)
        buckets.setdefault(metric, []).append(value)

    result: dict[str, float] = {}
    for metric, values in buckets.items():
        values_sorted = sorted(values)
        idx = int(len(values_sorted) * 0.95)
        result[metric] = values_sorted[min(idx, len(values_sorted) - 1)]
    return result


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_file",
        help="Path to the k6 JSON results file",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("benchmarks/k6/baseline.json"),
        help="Path to the baseline file",
    )
    parser.add_argument(
        "--p95-budget",
        type=float,
        default=500.0,
        help="Hard p95 latency budget in milliseconds (default: 500ms)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="Max percentage increase allowed vs baseline (default: 20%%)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update the baseline file if no regressions detected",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_path = Path(args.results_file)

    entries = load_ndjson(results_path)
    if not entries:
        print("No k6 results found, exiting.")
        sys.exit(0)

    p95s = aggregate_p95(entries)
    if not p95s:
        print("No metric data found in results.")
        sys.exit(0)

    failed = False

    # --- Hard p95 budget check ---
    for metric, p95_value in p95s.items():
        p95_ms = p95_value * 1000
        if p95_ms > args.p95_budget:
            print(f"BUDGET VIOLATION: {metric} p95={p95_ms:.1f}ms > budget {args.p95_budget:.1f}ms")
            failed = True
        else:
            print(f"BUDGET OK: {metric} p95={p95_ms:.1f}ms <= {args.p95_budget:.1f}ms")

    # --- Regression vs baseline ---
    baseline_data = load_json(args.baseline)
    if baseline_data and "metrics" in baseline_data:
        baseline_metrics = baseline_data.get("metrics", {})
        for metric, p95_value in p95s.items():
            if metric not in baseline_metrics:
                continue
            old_p95 = baseline_metrics[metric].get("p95", 0)
            if old_p95 == 0:
                continue
            pct_change = ((p95_value / old_p95) - 1) * 100
            if pct_change > args.threshold:
                print(
                    f"REGRESSION: {metric} p95={p95_value * 1000:.1f}ms vs "
                    f"baseline {old_p95 * 1000:.1f}ms (+{pct_change:.1f}% > {args.threshold}%)"
                )
                failed = True
            else:
                print(
                    f"OK: {metric} p95={p95_value * 1000:.1f}ms vs "
                    f"baseline {old_p95 * 1000:.1f}ms ({pct_change:+.1f}%)"
                )

    if failed:
        print("k6 performance regression detected.")
        sys.exit(1)

    # --- Update baseline if requested ---
    if args.update_baseline:
        baseline_data = {"metrics": {}}
        for metric, p95_value in p95s.items():
            baseline_data["metrics"][metric] = {"p95": p95_value}
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(baseline_data, indent=2))
        print("k6 baseline updated.")

    print("k6 performance check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
