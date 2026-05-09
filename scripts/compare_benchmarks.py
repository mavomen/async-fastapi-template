#!/usr/bin/env python3
"""Compare pytest-benchmark JSON output against a stored baseline."""

import json
import sys
from pathlib import Path

BASELINE = Path("benchmarks/baseline.json")
NEW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("benchmark.json")
THRESHOLD_PCT = 20  # percent


def load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


new_data = load(NEW)
if not new_data:
    print("No new benchmark data, exiting.")
    sys.exit(0)

baseline = load(BASELINE)
if not baseline:
    NEW.rename(BASELINE)
    print("Created baseline, exiting.")
    sys.exit(0)

new_tests = {b["name"]: b["stats"]["mean"] for b in new_data["benchmarks"]}
old_tests = {b["name"]: b["stats"]["mean"] for b in baseline["benchmarks"]}

failed = False
for name, new_mean in new_tests.items():
    old_mean = old_tests.get(name)
    if old_mean is None:
        continue
    pct_change = ((new_mean / old_mean) - 1) * 100
    if pct_change > THRESHOLD_PCT:
        print(
            f"FAIL: {name} {new_mean:.6f}s vs baseline {old_mean:.6f}s "
            f"(+{pct_change:.1f}% > {THRESHOLD_PCT}%)"
        )
        failed = True
    else:
        print(f"OK: {name} {new_mean:.6f}s vs baseline {old_mean:.6f}s ({pct_change:+.1f}%)")

if failed:
    sys.exit(1)
else:
    NEW.replace(BASELINE)
    print("Baseline updated.")
    sys.exit(0)
