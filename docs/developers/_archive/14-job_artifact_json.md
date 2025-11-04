# Job Artifact JSON — What It Is and Why It Matters

**The artifact is the job’s living record.**
ADE creates one artifact JSON at job start, then **passes and enriches it across every pass**:

1. **Find tables & headers** → structure traces
2. **Map columns to target fields** → mapping with scores & rule contributors
3. **Transform values (opt.)** → per‑field transform summaries
4. **Validate values (opt.)** → cell‑level issues + per‑field counts
5. **Generate workbook** → output plan, file path, job summary

**After the job**, the artifact is your single source of truth for **audit, debugging, and explainability**: it tells you *what ADE did, how it decided, and where issues are*.
**During the job**, every rule script receives a **read‑only view** of the artifact so detection/validation logic can **consult prior decisions** without mutating state.

> **What the artifact is not:** it does **not** store raw cell data. It stores decisions, references, ranges (A1), rule IDs, and issue locations.

---

## 1) Example artifact JSON

A compact, realistic snapshot of an end‑to‑end run:

```json
{
  "schema": "ade.artifact/v1",
  "artifact_version": "1.1",
  "job": {
    "job_id": "job_2025-10-29T12-45-00Z_001",
    "source_file": "employees.xlsx",
    "status": "succeeded",
    "started_at": "2025-10-29T12:45:00Z",
    "completed_at": "2025-10-29T12:45:32Z",
    "config_version_id": "cfg_acme_v13",
    "trace_id": "req-2f6fb96a"
  },
  "config": {
    "config_version_id": "cfg_acme_v13",
    "manifest_version": "1.0.0"
  },
  "engine": {
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_",
      "output_sheet": "Employees"
    },
    "defaults": {
      "timeout_ms": 60000,
      "memory_mb": 512,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.65
    }
  },
  "rules": {
    "row_types": {
      "row_types.header.detect_text_density": { "impl": "row_types.header:detect_text_density" }
    },
    "column_detect": {
      "columns.member_id.detect_pattern": {
        "impl": "columns.member_id:detect_pattern",
        "field": "member_id"
      },
      "columns.department.detect_synonyms": {
        "impl": "columns.department:detect_synonyms",
        "field": "department"
      }
    },
    "transform": {
      "columns.member_id.transform": {
        "impl": "columns.member_id:transform",
        "field": "member_id"
      }
    },
    "validate": {
      "columns.member_id.validate": {
        "impl": "columns.member_id:validate",
        "field": "member_id"
      }
    }
  },
  "sheets": [
    {
      "id": "sheet_1",
      "name": "Employees",
      "row_classification": [
        {
          "row_index": 4,
          "label": "header",
          "confidence": 0.91,
          "scores_by_type": { "header": 1.24, "data": 0.11 },
          "rule_traces": [
            { "rule": "row_types.header:detect_text_density", "delta": 0.62 }
          ]
        }
      ],
      "tables": [
        {
          "id": "Employees-table-1",
          "range": "B4:G159",
          "data_range": "B5:G159",
          "header": {
            "kind": "raw",
            "row_index": 4,
            "source_header": ["Employee ID", "Name", "Department", "Start Date"]
          },
          "columns": [
            {
              "column_id": "Employees-table-1.col.1",
              "source_header": "Employee ID"
            },
            {
              "column_id": "Employees-table-1.col.2",
              "source_header": "Name"
            },
            {
              "column_id": "Employees-table-1.col.3",
              "source_header": "Department"
            }
          ],
          "mapping": [
            {
              "raw": {
                "column": "Employees-table-1.col.1",
                "header": "Employee ID"
              },
              "target_field": "member_id",
              "score": 1.8,
              "contributors": [
                { "rule": "columns.member_id:detect_pattern", "delta": 0.9 }
              ]
            },
            {
              "raw": {
                "column": "Employees-table-1.col.2",
                "header": "Name"
              },
              "target_field": "first_name",
              "score": 1.2
            },
            {
              "raw": {
                "column": "Employees-table-1.col.3",
                "header": "Department"
              },
              "target_field": "department",
              "score": 0.9,
              "contributors": [
                { "rule": "columns.department:detect_synonyms", "delta": 0.6 }
              ]
            }
          ],
          "transforms": [
            {
              "target_field": "member_id",
              "transform": "columns.member_id:transform",
              "changed": 120,
              "total": 155,
              "notes": "uppercased + stripped non-alnum"
            }
          ],
          "validation": {
            "issues": [
              {
                "a1": "B20",
                "row_index": 20,
                "target_field": "member_id",
                "column": "Employees-table-1.col.1",
                "code": "pattern_mismatch",
                "severity": "error",
                "message": "Does not match expected pattern",
                "rule": "columns.member_id:validate"
              }
            ],
            "summary_by_field": {
              "member_id": { "errors": 3, "warnings": 1, "missing": 0 }
            }
          }
        }
      ]
    }
  ],
  "output": {
    "format": "xlsx",
    "sheet": "Normalized",
    "path": "jobs/2025-10-29/normalized.xlsx",
    "column_plan": {
      "target": [
        { "field": "member_id", "output_header": "Member ID", "order": 1 },
        { "field": "first_name", "output_header": "First Name", "order": 2 },
        { "field": "department", "output_header": "Department", "order": 3 }
      ],
      "appended_unmapped": [
        {
          "source_header": "Start Date",
          "output_header": "raw_Start_Date",
          "order": 4,
          "column": "Employees-table-1.col.4"
        }
      ]
    }
  },
  "summary": {
    "rows_written": 155,
    "columns_written": 4,
    "issues_found": 4
  },
  "pass_history": [
    {
      "pass": 1,
      "name": "structure",
      "completed_at": "2025-10-29T12:45:07Z",
      "stats": { "tables": 1, "rows": 155, "columns": 4 }
    },
    {
      "pass": 2,
      "name": "mapping",
      "completed_at": "2025-10-29T12:45:12Z",
      "stats": { "mapped": 3, "unmapped": 1 }
    },
    {
      "pass": 3,
      "name": "transform",
      "completed_at": "2025-10-29T12:45:22Z",
      "stats": { "changed_cells": 12, "fields_with_warnings": 1 }
    },
    {
      "pass": 4,
      "name": "validate",
      "completed_at": "2025-10-29T12:45:24Z",
      "stats": { "errors": 3, "warnings": 1 }
    },
    {
      "pass": 5,
      "name": "generate",
      "completed_at": "2025-10-29T12:45:29Z",
      "stats": { "rows_written": 155, "columns_written": 4 }
    }
  ],
  "annotations": [
    {
      "stage": "after_mapping",
      "hook": "hooks/audit.py",
      "annotated_at": "2025-10-29T12:45:24Z",
      "notes": "Mapping completed"
    }
  ]
}
```

---

## 3) Python models (Pydantic v2)

These mirror the schema and are suitable for validation, serialization, and generating JSON Schema via `.model_json_schema()`.

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, constr


# --- Common enums & constrained types ---

A1Range = constr(pattern=r"^[A-Z]+[1-9]\d*(?::[A-Z]+[1-9]\d*)?$")


class HeaderKind(str, Enum):
    raw = "raw"
    synthetic = "synthetic"


class IssueSeverity(str, Enum):
    error = "error"
    warning = "warning"


class PassName(str, Enum):
    structure = "structure"
    mapping = "mapping"
    transform = "transform"
    validate = "validate"
    generate = "generate"


# --- Top-level models ---

class Job(BaseModel):
    job_id: str
    source_file: str
    status: Literal["succeeded", "failed"] = "succeeded"
    started_at: str  # ISO 8601
    completed_at: str  # ISO 8601
    config_version_id: Optional[str] = None
    trace_id: Optional[str] = None


class ConfigSnapshot(BaseModel):
    config_version_id: Optional[str] = None
    manifest_version: Optional[str] = None


class WriterSettings(BaseModel):
    mode: Literal["row_streaming", "in_memory"] = "row_streaming"
    append_unmapped_columns: bool = True
    unmapped_prefix: str = "raw_"
    output_sheet: Optional[str] = None


class EngineDefaults(BaseModel):
    timeout_ms: Optional[int] = None
    memory_mb: Optional[int] = None
    runtime_network_access: Optional[bool] = None
    mapping_score_threshold: Optional[float] = None


class Engine(BaseModel):
    writer: WriterSettings
    defaults: Optional[EngineDefaults] = None


class RuleRef(BaseModel):
    impl: str
    field: Optional[str] = None


RuleRegistry = Dict[str, RuleRef]


class Rules(BaseModel):
    row_types: RuleRegistry = Field(default_factory=dict)
    column_detect: RuleRegistry = Field(default_factory=dict)
    transform: RuleRegistry = Field(default_factory=dict)
    validate: RuleRegistry = Field(default_factory=dict)


class RuleTrace(BaseModel):
    rule: str
    delta: float


class RowClassification(BaseModel):
    row_index: int
    label: Literal["header", "data", "other"] = "other"
    confidence: float
    scores_by_type: Dict[str, float]
    rule_traces: List[RuleTrace] = Field(default_factory=list)


class HeaderDescriptor(BaseModel):
    kind: HeaderKind
    row_index: int
    source_header: List[Optional[str]]


class TableColumn(BaseModel):
    column_id: str
    source_header: Optional[str] = None
    order: int


class RawColumnRef(BaseModel):
    column: str
    header: Optional[str] = None


class ScoreContributor(BaseModel):
    rule: str
    delta: float


class MappingEntry(BaseModel):
    raw: RawColumnRef
    target_field: Optional[str] = None
    score: float
    contributors: List[ScoreContributor] = Field(default_factory=list)


class TransformSummary(BaseModel):
    target_field: str
    transform: str
    changed: int
    total: int
    warnings: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class Issue(BaseModel):
    a1: Optional[A1Range] = None
    row_index: Optional[int] = None
    target_field: Optional[str] = None
    code: str
    severity: IssueSeverity
    message: str
    column: Optional[str] = None
    rule: Optional[str] = None


class FieldIssueSummary(BaseModel):
    errors: int = 0
    warnings: int = 0
    missing: int = 0


class ValidationBlock(BaseModel):
    issues: List[Issue] = Field(default_factory=list)
    summary_by_field: Dict[str, FieldIssueSummary] = Field(default_factory=dict)


class ColumnPlanTargetItem(BaseModel):
    field: str
    output_header: str
    order: int


class ColumnPlanUnmappedItem(BaseModel):
    source_header: Optional[str] = None
    output_header: str
    order: int
    column: str


class ColumnPlan(BaseModel):
    target: List[ColumnPlanTargetItem]
    appended_unmapped: List[ColumnPlanUnmappedItem] = Field(default_factory=list)


class Output(BaseModel):
    format: Literal["xlsx", "csv"] = "xlsx"
    sheet: str
    path: str
    column_plan: ColumnPlan


class Summary(BaseModel):
    rows_written: int = 0
    columns_written: int = 0
    issues_found: int = 0


class Table(BaseModel):
    id: str
    range: A1Range
    data_range: Optional[A1Range] = None
    header: HeaderDescriptor
    columns: List[TableColumn]
    mapping: List[MappingEntry] = Field(default_factory=list)
    transforms: List[TransformSummary] = Field(default_factory=list)
    validation: Optional[ValidationBlock] = None


class Sheet(BaseModel):
    id: str
    name: str
    row_classification: List[RowClassification] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)


class PassHistoryItem(BaseModel):
    pass_: int = Field(..., alias="pass")
    name: PassName
    completed_at: str  # ISO 8601
    stats: Optional[Dict[str, int]] = None


class Artifact(BaseModel):
    schema: Literal["ade.artifact/v1"] = "ade.artifact/v1"
    artifact_version: constr(pattern=r"^\d+\.\d+$") = "1.1"
    job: Job
    config: ConfigSnapshot
    engine: Engine
    rules: Rules
    sheets: List[Sheet] = Field(default_factory=list)
    output: Optional[Output] = None
    summary: Optional[Summary] = None
    pass_history: List[PassHistoryItem] = Field(default_factory=list)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        populate_by_name = True


# --- (Optional) helpers ---

if __name__ == "__main__":
    # Print JSON Schema generated from the models
    import json
    print(json.dumps(Artifact.model_json_schema(), indent=2))

    # Example: validate/load an artifact from a dict
    # data = json.loads(Path("artifact.json").read_text())
    # artifact = Artifact.model_validate(data)
    # print(artifact.model_dump_json(indent=2))
```

---

## Practical tips

* **Stable IDs**: `sheet_1 / Employees-table-1 / Employees-table-1.col.1` and A1 ranges make it easy to cross-reference logs, screenshots, and code.
* **Explainability**: For any decision (“Why did this map to `member_id`?”), look at `mapping[].contributors[]` and the `rules` registry.
* **Rule identifiers**: Rule strings follow `<module_id>:<callable>` (for example, `columns.member_id:validate`) for cross-platform stability.
* **Privacy by design**: No raw cell payloads are stored—only locations and decision traces.
* **Canonical codes**: The worker normalizes common validation aliases (for example, `missing` → `required_missing`) before persisting issues. Stick to the documented codes for dashboards and alerts.
* **Per-pass stats**: `pass_history[].stats` captures quick totals (mapped vs. unmapped, changed cells, warning counts) without reprocessing the full artifact.
* **Hook annotations**: When a hook returns a dict, ADE appends it to `annotations[]` alongside the hook path and stage so audits surface inline notes.
* **Extensibility**: Add fields under the defined objects as your engine evolves. If you tighten validation, update both the schema and models.
