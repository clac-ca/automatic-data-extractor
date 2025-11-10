"""Example after_mapping hook."""

from __future__ import annotations

from typing import Any, Mapping


def run(*, table: Mapping[str, Any], **_: Any) -> Mapping[str, Any]:
    """Ensure headers are title-cased for readability."""

    headers = table.get("headers")
    if isinstance(headers, list):
        table["headers"] = [str(header).strip().title() for header in headers]
    return table
