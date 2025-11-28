from ade_api.features.builds.fingerprint import compute_build_fingerprint


def test_fingerprint_stable_for_same_inputs() -> None:
    base = dict(
        config_digest="abc123",
        engine_spec="apps/ade-engine",
        engine_version="1.0.0",
        python_version="3.12.1",
        python_bin="/usr/bin/python3",
        extra={"flag": True},
    )

    first = compute_build_fingerprint(**base)
    second = compute_build_fingerprint(**base)
    assert first == second


def test_fingerprint_changes_when_inputs_change() -> None:
    base = dict(
        config_digest="abc123",
        engine_spec="apps/ade-engine",
        engine_version="1.0.0",
        python_version="3.12.1",
        python_bin="/usr/bin/python3",
        extra={"flag": True},
    )

    original = compute_build_fingerprint(**base)
    mutated = compute_build_fingerprint(**{**base, "config_digest": "zzz"})
    assert original != mutated
