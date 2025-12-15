from __future__ import annotations

def register(registry):
    registry.register_row_detector(detect_data_row_by_density, row_kind="data", priority=0)


def detect_data_row_by_density(
    *,
    row_index,
    row_values,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    """Vote for a row being a data row.

    Heuristic:
      - data rows have more non-empty cells
      - data rows often contain numerics/dates mixed in
    """
    values = row_values or []
    if not values:
        return {"data": 0.0}

    non_empty = [v for v in values if v not in (None, "") and not (isinstance(v, str) and not v.strip())]
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
