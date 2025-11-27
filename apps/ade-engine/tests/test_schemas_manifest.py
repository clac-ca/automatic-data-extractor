import pytest
from pydantic import ValidationError

from ade_engine.schemas.manifest import ManifestV1


@pytest.fixture()
def sample_manifest() -> dict:
    return {
        "schema": "ade.manifest/v1",
        "version": "1.2.3",
        "name": "Sample Config",
        "description": "Optional description",
        "script_api_version": 2,
        "columns": {
            "order": ["member_id", "email"],
            "fields": {
                "member_id": {
                    "label": "Member ID",
                    "module": "column_detectors.member_id",
                    "required": True,
                    "synonyms": ["member id", "member#"],
                    "type": "string",
                },
                "email": {
                    "label": "Email",
                    "module": "column_detectors.email",
                    "required": True,
                    "type": "string",
                },
            },
        },
        "hooks": {
            "on_run_start": ["hooks.on_run_start"],
            "on_after_extract": ["hooks.on_after_extract"],
            "on_after_mapping": ["hooks.on_after_mapping"],
            "on_before_save": ["hooks.on_before_save"],
            "on_run_end": ["hooks.on_run_end"],
        },
        "writer": {
            "append_unmapped_columns": True,
            "unmapped_prefix": "raw_",
            "output_sheet": "Normalized",
        },
    }


def test_manifest_models_validate(sample_manifest: dict):
    manifest = ManifestV1.model_validate(sample_manifest)

    assert manifest.schema == "ade.manifest/v1"
    assert manifest.columns.order == ["member_id", "email"]
    assert manifest.columns.fields["member_id"].module == "column_detectors.member_id"
    assert manifest.hooks.on_after_mapping == ["hooks.on_after_mapping"]
    assert manifest.writer.unmapped_prefix == "raw_"


def test_manifest_schema_contains_required_fields(sample_manifest: dict):
    manifest = ManifestV1.model_validate(sample_manifest)
    schema = manifest.model_json_schema()

    required_fields = set(schema.get("required", []))
    assert {"schema", "version", "script_api_version", "columns", "hooks", "writer"}.issubset(required_fields)


@pytest.mark.parametrize("bad_field", ["unexpected", "columns__typo"])
def test_manifest_rejects_extra_fields(sample_manifest: dict, bad_field: str):
    sample_manifest[bad_field] = "oops"
    with pytest.raises(ValidationError):
        ManifestV1.model_validate(sample_manifest)
    sample_manifest.pop(bad_field)
