"""CSV export utility."""

import csv
import io
from typing import Any


def export_to_csv(data: list[dict[str, Any]], columns: list[str]) -> str:
    """Convert list of dicts to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()
