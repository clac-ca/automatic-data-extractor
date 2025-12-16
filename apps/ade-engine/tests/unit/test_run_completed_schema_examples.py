from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.models.events import RunCompletedPayloadV1


@pytest.mark.parametrize(
    "example",
    [
        "run_completed.v1.success.example.json",
        "run_completed.v1.failed_partial.example.json",
    ],
)
def test_run_completed_examples_validate_strict(example: str) -> None:
    repo_root = ROOT.parent.parent  # automatic-data-extractor/
    path = (
        repo_root
        / ".workpackages"
        / "ade-summary-reporting-implementation"
        / "examples"
        / example
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    # Contract: strict validation, extra fields forbidden, stable invariants.
    model = RunCompletedPayloadV1.model_validate(payload, strict=True)
    dumped = model.model_dump(mode="python", exclude_none=True)
    assert dumped.get("schema_version") == 1
    assert dumped.get("scope") == "run"
