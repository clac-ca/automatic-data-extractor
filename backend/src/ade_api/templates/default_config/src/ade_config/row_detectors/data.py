"""ADE row detector template: `data`

Row detectors vote on what each row represents (header vs data vs unknown). ADE
uses these votes to pick header rows and detect table regions.

Return value
------------
- Return a score patch (`dict[str, float]`) or `None`.
- Keys are row kinds like `"data"` and `"header"` (scores are additive across detectors).
- Higher total score wins the per-row classification.

Template goals
--------------
- Keep the default heuristic fast (no large scans; operate on the current row only).
- Prefer simple signals: non-empty density and mixed numeric/text content.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ade_engine.extensions.registry import Registry
    from ade_engine.infrastructure.observability.logger import RunLogger
    from ade_engine.infrastructure.settings import Settings


def register(registry: Registry) -> None:
    """Register this config package's data row detector(s)."""
    registry.register_row_detector(detect_data_row_by_density, row_kind="data", priority=0)


def detect_data_row_by_density(
    *,
    row_index: int,  # 1-based row number in the scanned sheet (Excel-style)
    row_values: Sequence[Any],  # Raw cell values for this row (may include None/""/numbers)
    sheet_name: str,  # Worksheet title
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Vote for a row being a data row.

    Heuristic:
      - data rows have more non-empty cells
      - data rows often contain numerics/dates mixed in

    Scoring:
      - Returns a positive `data` score.
      - Also returns a small negative `header` score to help separation (optional pattern).
    """
    values = row_values or []
    if not values:
        return {"data": 0.0}

    non_empty = [
        v for v in values if v not in (None, "") and not (isinstance(v, str) and not v.strip())
    ]
    density = len(non_empty) / max(len(values), 1)

    numericish = 0
    for v in non_empty:
        if isinstance(v, (int, float)):
            numericish += 1
        elif isinstance(v, str):
            s = v.strip()
            # crude: if it contains a digit, count as numeric-ish
            if any(ch.isdigit() for ch in s):
                numericish += 1

    num_ratio = numericish / max(len(non_empty), 1)
    score = min(1.0, density * 0.5 + num_ratio * 0.5)

    return {"data": score, "header": -score * 0.2}
