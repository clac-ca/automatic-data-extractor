# 02 — Job Orchestration (Deep Dive)

This page explains **how a job runs**—from the very first artifact JSON created at job start to the last row written to the normalized workbook. It does **not** assume prior knowledge. We’ll walk pass‑by‑pass with clear pseudocode showing what each step **reads**, **writes**, and **records** in the artifact.

---

## Why start with the Artifact JSON?

**Artifact JSON** is the backbone of orchestration. It is both:

1. **Audit record** — what ADE saw and decided (tables, mappings, transforms, validations, output).
2. **Shared state** — the *only* structured object that flows between passes.

A job begins by constructing an **initial artifact**, then each pass **reads** it and **appends** new facts. No raw cell data is stored—only coordinates (A1), decisions, contributors, and summaries.

→ Full schema: see **Artifact Reference** (`./14-job_artifact_json.md`)

---

## Job lifecycle at a glance

```
Start
  │
  ├─ Build initial artifact (config, rule registry, metadata)
  │
  ├─ Pass 1: Structure
  │   Find tables & header rows (row detectors) → write tables + A1 ranges
  │
  ├─ Pass 2: Mapping
  │   Sample raw columns → score per target field → choose / leave unmapped
  │
  ├─ Pass 3–5: Generate
  │   For each row: Transform → Validate → Write
  │   Summaries + issues recorded in artifact
  │
  └─ Finish (normalized.xlsx + artifact.json)
```

---

## Pass 0 — Create the initial artifact

**Inputs:** active config, source file, job id, timestamps
**Outputs:** artifact with top‑level metadata, an empty structure for later passes, and a **rule registry** (which exact code is in play).

### Initial shape

```json
{
  "version": "artifact.v1.1",
  "job": {
    "id": "<job_id>",
    "source_file": "input.xlsx",
    "started_at": "2025-10-30T12:34:56Z"
  },
  "config": {
    "workspace_id": "<ws>",
    "config_id": "<active-config-id>",
    "title": "Your Config Title",
    "version": "1.2.0"
  },
  "rules": {},                  // filled below (impl path + content hash)
  "sheets": [],                 // filled in Pass 1
  "output": {},                 // filled in Pass 3–5
  "summary": {},                // filled at end
  "pass_history": []            // appended after each pass completes
}
```

### Build the rule registry

Each callable used during the job gets a stable id and a short content hash for reproducibility.

```python
def build_rule_registry(active_config) -> dict:
    registry = {}
    for rule in _discover_rules(active_config):  # row detectors, column detectors, transforms, validators, hooks
        impl = f"{rule.module_path}:{rule.func_name}"     # "columns/member_id.py:detect_synonyms"
        version = _sha1_of_source(rule.module_path, rule.func_name)[:6]
        registry[rule.rule_id] = {"impl": impl, "version": version}
    return registry

def make_initial_artifact(active_config, source_file, job_id):
    a = {
      "version": "artifact.v1.1",
      "job": {"id": job_id, "source_file": source_file, "started_at": _now()},
      "config": _config_header(active_config),
      "rules": build_rule_registry(active_config),
      "sheets": [],
      "output": {},
      "summary": {},
      "pass_history": []
    }
    return a
```

> **Design note:** The artifact is **append‑only** for the duration of the job. Mutations are “adds,” not destructive rewrites. Persist with atomic writes (temp file → move) to withstand crashes.

---

## Shared conventions used in all passes

* **Detectors** return *score deltas* (`{"scores": {...}}`). ADE sums deltas and chooses the max; ties break by manifest order.
* **Transforms** return `{"values": [...], "warnings": [...]}`.
* **Validators** return `{"issues": [...]}` (no data changes).
* **Hooks** return `None` or `{"notes": "..."}` to annotate the artifact.
* **No raw cell values** enter the artifact; only A1 coordinates, rule ids, and counts.

Utility helpers referenced below:

```python
def mark_pass_done(artifact, n, name):
    artifact["pass_history"].append({"pass": n, "name": name, "completed_at": _now()})

def safe_call(rule_id, fn, **kwargs):
    try:
        out = fn(**kwargs)
        return out or {}
    except Exception as e:
        _append_rule_error(artifact=kwargs.get("artifact"), rule_id=rule_id, message=str(e))
        return {}  # neutral on failure

def choose_best_label(scores: dict, order: list[str]) -> str:
    # Highest score; tie broken by 'order' index
    labels = sorted(scores.items(), key=lambda kv: (kv[1], -order.index(kv[0])), reverse=True)
    return labels[0][0] if labels else order[0]
```

---

## Pass 1 — Structure (find tables & headers)

**Goal:** Walk each sheet **row‑by‑row**, label rows (header/data/separator), and infer **tables with A1 ranges** and **header rows**.

**Reads:** initial artifact, manifest row rules
**Writes:** `artifact.sheets[].row_classification[]`, `artifact.sheets[].tables[]` (with `range`, `data_range`, `header`)

### Pseudocode

```python
def run_pass1_structure(xls_reader, active_config, artifact):
    row_rules = _load_row_rules(active_config)   # [("row.header.text_density", func), ...]

    for sheet in xls_reader.stream_sheets():     # streaming; no full-sheet load
        s_entry = {"id": _id(), "name": sheet.name,
                   "row_classification": [], "tables": []}
        artifact["sheets"].append(s_entry)

        # 1) Label each row
        for row_idx, row_values_sample in sheet.stream_rows():  # sample of this row's cells
            totals, traces = {}, []
            for rule_id, fn in row_rules:
                out = safe_call(rule_id, fn,
                                row_values_sample=row_values_sample,
                                row_index=row_idx, sheet_name=sheet.name,
                                manifest=active_config.manifest,
                                artifact=artifact)
                for label, delta in out.get("scores", {}).items():
                    if delta:
                        totals[label] = totals.get(label, 0.0) + float(delta)
                        traces.append({"rule": rule_id, "delta": float(delta)})

            label = choose_best_label(totals, order=_row_order(active_config))  # e.g., ["header","data","separator"]
            s_entry["row_classification"].append({
                "row_index": row_idx,
                "label": label,
                "scores_by_type": totals,
                "rule_traces": traces,
                "confidence": _confidence_from_totals(totals, label)
            })

        # 2) Infer tables from labeled rows
        for table in _infer_tables(s_entry["row_classification"], sheet):
            # Table includes A1 ranges and the captured header row
            s_entry["tables"].append({
                "id": _id("table"),
                "range": table.a1_total,                 # e.g., "B4:G159"
                "data_range": table.a1_data,             # e.g., "B5:G159"
                "header": table.header_descriptor,       # {kind:"raw|synthetic|promoted", row_index:4, source_header:[...]}
                "columns": _enumerate_source_columns(table.header_descriptor)
            })

    mark_pass_done(artifact, 1, "structure")
```

**Edge cases handled:**

* **No header row found:** synthesize headers `["Column 1", ...]` and record `header.kind = "synthetic"`.
* **Data before header:** “promote” the preceding row if signals strongly indicate a header.
* **Multiple tables per sheet:** `_infer_tables` emits multiple non‑overlapping ranges.

---

## Pass 2 — Mapping (raw columns → target fields)

**Goal:** For each table, map each **raw column** (`col_1...`) to a **target field** (`member_id`, `first_name`, …) using small, cheap detectors. Uncertain columns remain **unmapped**.

**Reads:** artifact tables, manifest column rules & `columns.order/meta`
**Writes:** `artifact.sheets[].tables[].mapping[]` (+ per‑decision contributors)

### Pseudocode

```python
def run_pass2_mapping(xls_reader, active_config, artifact):
    field_modules = _load_field_modules(active_config)  # {"member_id": mod, ...}

    for s in artifact["sheets"]:
        for t in s["tables"]:
            t["mapping"] = []
            table_reader = xls_reader.bind_range(s["name"], t["range"])

            for raw_col in table_reader.iter_columns():    # yields {"column_id":"col_1","header":"Employee ID", "index":1}
                sample = table_reader.sample_values(raw_col, n=_sample_size(active_config))
                scores_for_field, contribs = {}, {}

                for field_name, mod in field_modules.items():
                    total = 0.0
                    for rule_id, fn in mod.detect_rules:   # detect_* in columns/<field>.py
                        out = safe_call(rule_id, fn,
                                        header=raw_col["header"],
                                        values_sample=sample,
                                        column_index=raw_col["index"],
                                        sheet_name=s["name"],
                                        table_id=t["id"],
                                        field_name=field_name,
                                        field_meta=_field_meta(active_config, field_name),
                                        manifest=active_config.manifest,
                                        artifact=artifact)
                        delta = float(out.get("scores", {}).get(field_name, 0.0))
                        if delta:
                            total += delta
                            contribs.setdefault(field_name, []).append({"rule": rule_id, "delta": delta})
                    scores_for_field[field_name] = total

                best_field, best_score = _pick_field(scores_for_field, active_config)
                if best_field is None:
                    _record_unmapped_raw(t, raw_col)  # visible in output plan later (optional 'append_unmapped')
                    continue

                decision = {
                    "raw": {"column": raw_col["column_id"], "header": raw_col["header"]},
                    "target_field": best_field,
                    "score": best_score,
                    "contributors": contribs.get(best_field, [])
                }
                t["mapping"].append(decision)

    mark_pass_done(artifact, 2, "mapping")
```

**Choosing a field (tie/threshold logic):**

```python
def _pick_field(scores: dict[str, float], cfg):
    items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not items: return None, 0.0
    top_field, top = items[0]
    # tie → unmapped
    if len(items) > 1 and items[1][1] == top: return None, top
    # threshold (optional)
    min_score = cfg.manifest.get("mapping", {}).get("min_score")
    if min_score is not None and top < float(min_score): return None, top
    return top_field, top
```

> **Design note:** Detectors are tiny and composable. Header clues (synonyms/tokens) and value clues (shapes/patterns) *add up*. Negatives are allowed to push away from a field.

---

## Pass 3–5 — Generate (Transform → Validate → Write)

These steps run together while ADE writes the normalized workbook with a **row‑streaming writer**.

**Goal:** Produce the final sheet in the order defined by `manifest.columns.order`. For each row in the source table, read the mapped cell → transform → validate → write.

**Reads:** mapping, manifest (order/labels/flags), field modules
**Writes:** `output` (path, plan), `sheets[].tables[].transforms[]`, `sheets[].tables[].validation.*`, and final `summary`

### Output plan

```python
def _build_output_plan(active_config, t):
    order = active_config.manifest["columns"]["order"]   # target field order
    plan = []
    for i, field in enumerate(order, start=1):
        mapped = next((m for m in t["mapping"] if m["target_field"] == field), None)
        plan.append({
            "order": i,
            "field": field,
            "output_header": _label_for_field(active_config, field),
            "source": mapped["raw"] if mapped else None
        })
    return plan
```

### Pseudocode (simple, readable version)

> This version materializes per‑column arrays for clarity. Real implementations may **chunk** or **iterator‑ize** to reduce memory while preserving the same contract.

```python
def run_pass3_to_5_generate(xls_reader, writer, active_config, artifact):
    artifact["output"] = {
      "format": "xlsx",
      "sheet": "Normalized",
      "path": f"jobs/{artifact['job']['id']}/normalized.xlsx",
      "column_plan": {}
    }

    for s in artifact["sheets"]:
        for t in s["tables"]:
            plan = _build_output_plan(active_config, t)
            artifact["output"]["column_plan"]["target"] = [
              {"field": p["field"], "output_header": p["output_header"], "order": p["order"]}
              for p in plan
            ]

            # 1) Fetch raw columns and prepare processors per field
            processors = {}   # field -> iterator of transformed values
            for p in plan:
                field, src = p["field"], p["source"]
                mod = _load_field_module(active_config, field)
                values = []
                if src:   # mapped
                    values = xls_reader.fetch_column(s["name"], t["range"], src["column"])

                # Transform
                if hasattr(mod, "transform"):
                    tout = safe_call(f"transform.{field}", mod.transform,
                                     values=values, header=(src or {}).get("header"),
                                     column_index=_col_index(src),
                                     sheet_name=s["name"], table_id=t["id"],
                                     field_name=field, field_meta=_field_meta(active_config, field),
                                     manifest=active_config.manifest, artifact=artifact)
                    values2 = tout.get("values", values)
                    _record_transform_summary(artifact, t, field, changed=_count_changes(values, values2), total=len(values2))
                    values = values2

                # Validate
                if hasattr(mod, "validate") and values:
                    vout = safe_call(f"validate.{field}", mod.validate,
                                     values=values, header=(src or {}).get("header"),
                                     column_index=_col_index(src),
                                     sheet_name=s["name"], table_id=t["id"],
                                     field_name=field, field_meta=_field_meta(active_config, field),
                                     manifest=active_config.manifest, artifact=artifact)
                    _record_issues_with_a1(artifact, s, t, field, vout.get("issues", []))  # adds A1 coords

                processors[field] = iter(values) if values else _repeat_none(_row_count(t))

            # 2) Write rows in order, appending unmapped if configured
            writer.start_sheet("Normalized", headers=[p["output_header"] for p in plan] + _maybe_unmapped_headers(active_config, t))
            for _row_idx in range(_row_count(t)):
                out_row = [next(processors[p["field"]], None) for p in plan]
                if _append_unmapped(active_config):
                    out_row += _unmapped_values_at_row(xls_reader, s["name"], t, _row_idx)
                writer.write_row(out_row)

    writer.close()

    # Final summaries
    artifact["summary"] = {
      "rows_written": writer.rows_written,
      "columns_written": writer.columns_written,
      "issues_found": _count_all_issues(artifact)
    }
    mark_pass_done(artifact, 3, "transform")
    mark_pass_done(artifact, 4, "validate")
    mark_pass_done(artifact, 5, "generate")
```

### How A1 coordinates are attached to issues

```python
def _record_issues_with_a1(artifact, s, t, field, issues):
    # Each issue contains row_index (1-based within table) → convert to A1 using table.data_range and mapped column
    for issue in issues:
        a1 = _a1_for(t["data_range"], issue["row_index"], _output_col_of_field(field, artifact))
        artifact_issue = {
          "a1": a1,
          "row_index": issue["row_index"],
          "target_field": field,
          "code": issue["code"],
          "severity": issue["severity"],
          "message": issue["message"],
          "rule": f"validate.{field}"
        }
        _append_issue(artifact, s, t, artifact_issue)
```

> **Design note:** Even though transforms/validators are *specified* as column‑wise, the writer keeps overall execution **row‑streaming**. Engines commonly implement this by chunking columns or precomputing lightweight iterators so memory stays bounded.

---

## Hooks — where they run in the timeline

Hooks are **optional**; they see the same structured context and may return `{"notes": "..."}` to annotate the artifact.

```python
def run_job(source_file, active_config):
    artifact = make_initial_artifact(active_config, source_file, job_id=_new_job_id())
    _run_hook("on_job_start", active_config, artifact)

    run_pass1_structure(xls_reader=_open(source_file), active_config=active_config, artifact=artifact)

    run_pass2_mapping(xls_reader=_open(source_file), active_config=active_config, artifact=artifact)
    _maybe_run_analyze = active_config.manifest.get("analyze", {}).get("enabled", False)
    if _maybe_run_analyze: run_pass2_5_analyze(_open(source_file), active_config, artifact)
    _run_hook("after_mapping", active_config, artifact)

    writer = _open_writer(path=f"jobs/{artifact['job']['id']}/normalized.xlsx")
    run_pass3_to_5_generate(xls_reader=_open(source_file), writer=writer, active_config=active_config, artifact=artifact)
    _run_hook("after_transform", active_config, artifact)
    _run_hook("after_validate", active_config, artifact)

    _finalize_artifact(artifact)
    return artifact
```

---

## What each pass **reads** and **writes** (cheat‑sheet)

| Pass                   | Reads from artifact                      | Writes to artifact                                                                        |
| ---------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| 0 — Init               | (none)                                   | `rules`, `job`, empty `sheets`, empty `output`, `pass_history[]`                          |
| 1 — Structure          | `rules`, `config`                        | `sheets[].row_classification[]`, `sheets[].tables[]` with A1 ranges & headers             |
| 2 — Mapping            | `sheets[].tables[]`                      | `tables[].mapping[]` (raw→target decisions, scores, contributors)                         |
| 3–5 — Generate         | `mapping`, manifest `columns.order/meta` | `output` (path, column plan), `tables[].transforms[]`, `tables[].validation.*`, `summary` |

---

## Determinism, safety, and errors

* **Determinism:** Detectors, transforms, validators must be **pure** and **bounded**. Avoid global state and nondeterministic inputs.
* **Safety:** Network is **off** by default (`allow_net: false`). Artifact stores **locations and decisions**, **not** raw values.
* **Error containment:** If a rule throws, ADE records a neutral result and logs a rule‑level error trace in the artifact. The job continues.

```python
def _append_rule_error(artifact, rule_id, message):
    artifact.setdefault("rule_errors", []).append({
       "rule": rule_id, "message": message, "at": _now()
    })
```

---

## Practical debugging with the artifact

**Why did a column map that way?**

```python
def explain(artifact, table_id, raw_col):
    for s in artifact["sheets"]:
        for t in s["tables"]:
            if t["id"] != table_id: continue
            for m in t.get("mapping", []):
                if m["raw"]["column"] == raw_col:
                    return {"target_field": m["target_field"], "score": m["score"], "contributors": m.get("contributors", [])}
```

**Where are the validation errors?**

```python
def list_issues(artifact):
    out = []
    for s in artifact["sheets"]:
        for t in s["tables"]:
            for issue in t.get("validation", {}).get("issues", []):
                out.append((s.get("name"), t["id"], issue["a1"], issue["message"]))
    return out
```

---

## Appendix A — Minimal detector/transform/validator contracts (for reference)

```python
# Row detector (Pass 1)
def detect_*(*,
    row_values_sample: list, row_index: int, sheet_name: str,
    table_hint: dict | None = None, manifest: dict = {}, artifact: dict = {}, **_
) -> dict:
    # return {"scores": {"header": float, "data": float, "separator": float}}

# Column detector (Pass 2)
def detect_*(*,
    header: str | None, values_sample: list, column_index: int,
    sheet_name: str, table_id: str, field_name: str, field_meta: dict,
    manifest: dict = {}, artifact: dict = {}, **_
) -> dict:
    # return {"scores": {field_name: float}}

# Transform (Pass 3)
def transform(*,
    values: list, header: str | None, column_index: int,
    sheet_name: str, table_id: str, field_name: str, field_meta: dict,
    manifest: dict = {}, artifact: dict = {}, **_
) -> dict:
    # return {"values": list, "warnings": list[str]}

# Validate (Pass 4)
def validate(*,
    values: list, header: str | None, column_index: int,
    sheet_name: str, table_id: str, field_name: str, field_meta: dict,
    manifest: dict = {}, artifact: dict = {}, **_
) -> dict:
    # return {"issues": [{"row_index": int, "code": str, "severity": "error"|"warning"|"info", "message": str}]}
```

---

## Appendix B — Design choices summarized

* **Artifact‑first:** Every decision is recorded as data.
* **Streaming:** Sheets are processed without full in‑memory loads.
* **Small, testable rules:** Behavior is code; each rule is easy to unit‑test.
* **Explainable scoring:** Multiple small deltas beat one opaque classifier.
* **Unmapped is OK:** Ties and low‑confidence results remain unmapped (visible in artifact and, optionally, appended to output as `raw_*`).

With this map, you can follow a job from the first byte read to the last cell written—and you’ll know exactly **what** each pass does, **when** it runs, **what** it reads and writes, and **where** to look in the artifact to explain the outcome.