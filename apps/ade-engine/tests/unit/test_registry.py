from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.exceptions import ConfigError, PipelineError
from ade_engine.registry import FieldDef, Registry


def test_registry_sorting_priorities_and_names():
    reg = Registry()

    def detector_a(ctx):
        return {"email": 0.0}

    def detector_b(ctx):
        return {"email": 0.0}

    reg.register_field(FieldDef(name="email"))
    reg.register_column_detector(detector_a, field="email", priority=5)
    reg.register_column_detector(detector_b, field="email", priority=10)
    reg.finalize()

    assert [d.fn for d in reg.column_detectors] == [detector_b, detector_a]


def test_validate_detector_scores_requires_dicts_and_known_fields():
    reg = Registry()
    reg.register_field(FieldDef(name="email"))
    reg.register_field(FieldDef(name="name"))

    patch = reg.validate_detector_scores({"email": 1.0, "name": 0.2}, source="test")
    assert patch == {"email": 1.0, "name": 0.2}

    with pytest.raises(PipelineError):
        reg.validate_detector_scores(0.5, source="test")  # type: ignore[arg-type]

    with pytest.raises(PipelineError):
        reg.validate_detector_scores({"unknown": 1.0}, source="test")

    # allow_unknown is only for row detectors
    patch_unknown = reg.validate_detector_scores({"mystery": 1.0}, allow_unknown=True, source="row")
    assert patch_unknown == {"mystery": 1.0}


def test_duplicate_field_registration_raises():
    reg = Registry()
    reg.register_field(FieldDef(name="email"))
    with pytest.raises(ConfigError):
        reg.register_field(FieldDef(name="email"))
