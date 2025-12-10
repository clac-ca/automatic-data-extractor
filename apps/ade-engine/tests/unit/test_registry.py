from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.registry import Registry, FieldDef


def test_registry_sorting_priorities_and_names():
    reg = Registry()

    def detector_a(ctx):
        return 0

    def detector_b(ctx):
        return 0

    reg.register_column_detector(detector_a, field="email", priority=5)
    reg.register_column_detector(detector_b, field="email", priority=10)
    reg.finalize()

    assert [d.fn for d in reg.column_detectors] == [detector_b, detector_a]


def test_normalize_patch_handles_numbers_and_dicts():
    reg = Registry()
    reg.ensure_field("email")
    # float input
    assert reg.normalize_patch("email", 0.5) == {"email": 0.5}
    # dict input with unknown field ignored
    reg.ensure_field("name")
    patch = reg.normalize_patch("email", {"email": 1, "name": 0.2, "unknown": 5})
    assert patch == {"email": 1.0, "name": 0.2}


def test_duplicate_field_registration_raises():
    reg = Registry()
    reg.register_field(FieldDef(name="email"))
    try:
        reg.register_field(FieldDef(name="email"))
    except ValueError:
        pass
    else:  # pragma: no cover
        assert False, "Expected duplicate registration to raise"
