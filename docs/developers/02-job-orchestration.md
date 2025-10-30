# 02 — Job Orchestration (Deep Dive)

## 0) Start with the Artifact JSON (the backbone)

**Artifact JSON** is both:

1. **Audit record** — a full narrative of the run (what ADE saw, decided, and wrote).
2. **Shared state** — the *only* object passed between passes (append‑only during the run).

**Design guarantees**

* **Append-only during execution:** passes add facts; they don’t rewrite history.
* **No raw cell values:** the artifact records *locations* (A1), *decisions*, *contributors*, and *summaries*—never the underlying data.
* **Reproducibility:** a **rule registry** logs the exact code identifiers + content hashes for all callables.

### Initial artifact shape (created before Pass 1)

```json
{
  "version": "artifact.v1.1",
  "job":     { "id": "<job_id>", "source_file": "input.xlsx", "started_at": "2025-10-30T12:34:56Z" },
  "config":  { "workspace_id": "<ws>", "config_id": "<active-config-id>", "title": "Membership Rules", "version": "1.2.0" },
  "rules":   {},          // rule registry (filled immediately after init)
  "sheets":  [],          // filled by Pass 1 (structure)
  "output":  {},          // filled by Pass 3–5 (generate)
  "summary": {},          // filled at end
  "pass_history": []      // appended after each pass completes
}
```

### Building the rule registry (what code ran?)

```python
def build_rule_registry(config_pkg) -> dict:
    registry = {}
    for rule in discover_rules(config_pkg):  # row detectors, column detectors, transforms, validators, hooks
        impl = f"{rule.module}:{rule.func}"  # e.g., "columns/member_id.py:detect_synonyms"
        src  = read_source(rule.module, rule.func)
        ver  = sha1(src)[:6]                 # short content hash
        registry[rule.rule_id] = {"impl": impl, "version": ver}
    return registry
```

> See **Artifact Reference** (`./14-job_artifact_json.md`) for the full schema.

---

## 1) Orchestration at a glance

```
Start
  │
  ├─ Build initial artifact
  │   └─ attach rule registry (impl + hash)
  │
  ├─ Pass 1: Structure
  │   └─ stream rows → label (header/data/separator) → infer tables + A1 ranges
  │
  ├─ Pass 2: Mapping
  │   └─ sample raw columns → score per target field → pick / leave unmapped
  │
  ├─ Pass 3–5: Generate
  │   └─ for each row: Transform → Validate → Write → record summaries/issues
  │
  └─ Finish
      ├─ normalized.xlsx
      └─ artifact.json (full narrative)
```

**Streaming I/O:** ADE never requires full‑sheet loads. Row scanning and writing are streaming; column work can use samples or chunked scans.

---

## 2) Contracts your code must follow (tiny shapes)

* **Row/column detectors:** return **score deltas** (additive hints).
  `{"scores": {"header": +0.6}}` or `{"scores": {field_name: +0.4}}`
* **Transforms:** return new values for the column + optional warnings.
  `{"values": [...], "warnings": [...]}`
* **Validators:** return issues (no data changes).
  `{"issues": [{"row_index": 12, "code": "required_missing", ...}]}`
* **Hooks:** may return `{"notes": "..."}` to annotate history.

All public functions are **keyword‑only** and must tolerate extra kwargs via `**_`.

---

## 3) Pseudocode — the orchestrator

> The following pseudocode is faithful to ADE’s control flow but simplified for clarity.

```python
def run_job(source_file, active_config):
    artifact = make_initial_artifact(source_file, active_config)
    artifact["rules"] = build_rule_registry(active_config)
    save_artifact_atomic(artifact)

    # Pass 1: Structure (find tables & headers)
    pass1_structure(source_file, active_config, artifact)
    save_artifact_atomic(artifact)

    # Pass 2: Mapping (raw columns → target fields)
    pass2_mapping(source_file, active_config, artifact)
    save_artifact_atomic(artifact)

    # Optional tiny stats
    if analyze_enabled(active_config):
        pass2_5_analyze(source_file, active_config, artifact)
        save_artifact_atomic(artifact)

    # Pass 3–5: Generate (transform → validate → write)
    pass3_to_5_generate(source_file, active_config, artifact)
    save_artifact_atomic(artifact, finalize=True)

    return artifact
```

`save_artifact_atomic` writes to a temp file and renames, so crashes don’t corrupt the narrative.

---

## 4) Pass 1 — Structure (find tables & headers)

**Goal:** Identify table regions and header rows by **streaming** each sheet and labeling each row.

**Reads:** initial artifact, row detector functions, manifest ordering for ties
**Writes:** `sheets[].row_classification[]`, `sheets[].tables[]` (with `range`, `data_range`, `header`, `columns[]`)

```python
def pass1_structure(source_file, config, artifact):
    row_rules = load_row_rules(config)  # [("row.header.text_density", func), ...]
    for sheet in stream_sheets(source_file):
        s_entry = {"id": gen_id(), "name": sheet.name, "row_classification": [], "tables": []}
        artifact["sheets"].append(s_entry)

        # 1) Label rows
        for row_idx, row_sample in sheet.stream_rows():  # row_sample is a small list of cell values
            totals, traces = {}, []
            for rule_id, fn in row_rules:
                out = safe_call(rule_id, fn,
                                row_values_sample=row_sample,
                                row_index=row_idx, sheet_name=sheet.name,
                                manifest=config.manifest, artifact=artifact)
                for label, delta in out.get("scores", {}).items():
                    if delta:
                        totals[label] = totals.get(label, 0.0) + float(delta)
                        traces.append({"rule": rule_id, "delta": float(delta)})

            label = choose_best_label(totals, order=row_label_order(config))  # e.g., ["header","data","separator"]
            s_entry["row_classification"].append({
                "row_index": row_idx,
                "label": label,
                "scores_by_type": totals,
                "rule_traces": traces,
                "confidence": softmax_confidence(totals, label)
            })

        # 2) Infer tables from labeled rows
        for tbl in infer_tables(s_entry["row_classification"], sheet):
            s_entry["tables"].append({
                "id": gen_id("table"),
                "range": tbl.a1_total,            # e.g., "B4:G159"
                "data_range": tbl.a1_data,        # e.g., "B5:G159"
                "header": tbl.header_descriptor,  # {kind:"raw|synthetic|promoted", row_index, source_header:[...]}
                "columns": enumerate_source_columns(tbl.header_descriptor)  # [{column_id, source_header}, ...]
            })

    mark_pass_done(artifact, 1, "structure")
```

**Edge behavior**

* **No usable header found:** synthesize headers (`"Column 1", ...`) and mark `header.kind="synthetic"`.
* **Data appears before header:** “promote” the best candidate row just above the data; record `header.kind="promoted"`.

---

## 5) Pass 2 — Mapping (raw columns → target fields)

**Goal:** For each table, decide which raw column becomes which **target field** using additive scores from small detectors. Uncertain cases remain **unmapped**.

**Reads:** tables from Pass 1, column detectors in `columns/<field>.py`, manifest (`columns.order`, `columns.meta`, thresholds)
**Writes:** `tables[].mapping[]` with score + contributors

```python
def pass2_mapping(source_file, config, artifact):
    fields = load_field_modules(config)  # {"member_id": module, ...}

    for s in artifact["sheets"]:
        for t in s["tables"]:
            t["mapping"] = []
            reader = bind_range(source_file, sheet=s["name"], a1=t["range"])

            for raw in reader.iter_columns():  # {"column_id":"col_1","header":"Employee ID","index":1}
                sample = reader.sample_values(raw, n=sample_size(config))
                scores, contrib = {}, {}

                for field, mod in fields.items():
                    total = 0.0
                    for rule_id, fn in mod.detect_rules:  # detect_* inside columns/<field>.py
                        out = safe_call(rule_id, fn,
                                        header=raw["header"],
                                        values_sample=sample,
                                        column_index=raw["index"],
                                        sheet_name=s["name"], table_id=t["id"],
                                        field_name=field, field_meta=field_meta(config, field),
                                        manifest=config.manifest, artifact=artifact)
                        delta = float(out.get("scores", {}).get(field, 0.0))
                        if delta:
                            total += delta
                            contrib.setdefault(field, []).append({"rule": rule_id, "delta": delta})
                    scores[field] = total

                field, score = pick_field(scores, min_score=config.manifest.get("mapping", {}).get("min_score"))
                if field is None:
                    record_unmapped(t, raw)  # visible later; may be appended as raw_* if enabled
                    continue

                t["mapping"].append({
                    "raw": {"column": raw["column_id"], "header": raw["header"]},
                    "target_field": field,
                    "score": score,
                    "contributors": contrib.get(field, [])
                })

    mark_pass_done(artifact, 2, "mapping")
```

**Picking a field (tie & threshold)**

```python
def pick_field(scores: dict[str, float], min_score: float | None):
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not top: return None, 0.0
    best_field, best = top[0]
    # tie → unmapped
    if len(top) > 1 and top[1][1] == best: return None, best
    # low confidence → unmapped
    if min_score is not None and best < float(min_score): return None, best
    return best_field, best
```

> **Detector style:** Prefer several small, cheap, deterministic hints (header synonyms, value shape, locale nudges) over a single heavyweight detector. Negatives are allowed to push *away* from a field.

---

## 6) (Optional) Pass 2.5 — Analyze

**Goal:** Compute small, cheap stats for sanity checks (e.g., distinct counts, empties).
**Writes:** `artifact.analyze[table_id][field] = { "distinct": n, "empty": m }`

```python
def pass2_5_analyze(source_file, config, artifact):
    if not analyze_enabled(config): return
    artifact.setdefault("analyze", {})
    for s in artifact["sheets"]:
        for t in s["tables"]:
            slot = artifact["analyze"].setdefault(t["id"], {})
            for m in t.get("mapping", []):
                vals = fetch_column(source_file, sheet=s["name"], a1=t["range"], column_id=m["raw"]["column"])
                slot[m["target_field"]] = {"distinct": distinct_count(vals), "empty": count_empty(vals)}
```

---

## 7) Pass 3–5 — Generate (Transform → Validate → Write)

**Goal:** Produce the normalized workbook by streaming rows. For each target field (ordered by `manifest.columns.order`), ADE reads the mapped source cell, **transforms** it (optional), **validates** it (optional), and **writes** it.

**Reads:** mapping, manifest (order/labels/flags), field modules
**Writes:**

* `output`: format, sheet, path, and an output **column plan**
* `tables[].transforms[]`: per-field change counts
* `tables[].validation.*`: per-cell issues with A1 coordinates + summaries
* `summary`: rows/columns written, issues found

```python
def pass3_to_5_generate(source_file, config, artifact):
    writer = open_writer(path=f"jobs/{artifact['job']['id']}/normalized.xlsx", sheet="Normalized")
    manifest = config.manifest
    fields = load_field_modules(config)

    for s in artifact["sheets"]:
        for t in s["tables"]:
            plan = build_output_plan(manifest, t)  # [{field, output_header, order, source:{column,header}|None}, ...]

            # headers
            writer.set_headers([p["output_header"] for p in plan] + maybe_unmapped_headers(manifest, t))

            # prepare per-field iterators (keeps writing row-streaming)
            processors = {}
            for p in plan:
                field, src = p["field"], p["source"]
                values = fetch_column(source_file, sheet=s["name"], a1=t["range"], column_id=src["column"]) if src else repeat_none(row_count(t))

                # transform
                if has_transform(fields[field]):
                    out = call_transform(fields[field],
                                         values=values,
                                         header=src["header"] if src else None,
                                         column_index=src_index(src), sheet_name=s["name"], table_id=t["id"],
                                         field_name=field, field_meta=field_meta(config, field),
                                         manifest=manifest, artifact=artifact)
                    new_vals = out.get("values", values)
                    record_transform_summary(artifact, table=t, field=field,
                                             changed=count_changes(values, new_vals), total=len(new_vals))
                    values = new_vals

                # validate
                if has_validate(fields[field]):
                    vout = call_validate(fields[field],
                                         values=values,
                                         header=src["header"] if src else None,
                                         column_index=src_index(src), sheet_name=s["name"], table_id=t["id"],
                                         field_name=field, field_meta=field_meta(config, field),
                                         manifest=manifest, artifact=artifact)
                    attach_issues_with_a1(artifact, sheet=s, table=t, field=field, issues=vout.get("issues", []))

                processors[field] = iter(values)

            # stream rows
            for r in range(row_count(t)):
                out_row = [next(processors[p["field"]], None) for p in plan]
                if append_unmapped(manifest): out_row += unmapped_values_at_row(source_file, s["name"], t, r)
                writer.write_row(out_row)

    writer.close()

    artifact["output"] = {
      "format": "xlsx", "sheet": "Normalized",
      "path": f"jobs/{artifact['job']['id']}/normalized.xlsx",
      "column_plan": {
        "target": [{"field": p["field"], "output_header": p["output_header"], "order": p["order"]} for p in plan]
      }
    }
    artifact["summary"] = {
      "rows_written": writer.rows_written,
      "columns_written": writer.columns_written,
      "issues_found": count_all_issues(artifact)
    }
    mark_pass_done(artifact, 3, "transform")
    mark_pass_done(artifact, 4, "validate")
    mark_pass_done(artifact, 5, "generate")
```

**Attaching A1 coordinates to issues**

```python
def attach_issues_with_a1(artifact, sheet, table, field, issues):
    # Each issue has row_index (1-based within the table's data_range)
    col_a1 = a1_for_mapped_target(table, field)   # derive column letter(s) from mapping/plan
    for issue in issues:
        a1 = a1_from_row_col(table["data_range"], issue["row_index"], col_a1)
        record_issue(artifact, sheet, table, {
          "a1": a1, "row_index": issue["row_index"], "target_field": field,
          "code": issue["code"], "severity": issue["severity"], "message": issue["message"],
          "rule": f"validate.{field}"
        })
```

> **Implementation note:** The column contracts (transform/validate) are expressed over *vectors* (`values: list`), but engines can realize them with buffers/iterators so overall execution stays **row‑streaming**.

---

## 8) Hooks — when and why

Hooks are optional; they receive the same structured context and may annotate the artifact with `{"notes": "..."}`. Typical placements:

| Hook file            | When it runs  | Good for…                        |
| -------------------- | ------------- | -------------------------------- |
| `on_job_start.py`    | Before Pass 1 | Logging metadata, warming caches |
| `after_mapping.py`   | After Pass 2  | Alerting on unmapped columns     |
| `after_transform.py` | After Pass 3  | Summaries/metrics                |
| `after_validate.py`  | After Pass 4  | Aggregating issues, dashboards   |

```python
def run_hook(name, config, artifact):
    mod = load_hook_module(config, name)          # if present
    if not mod: return
    out = safe_call(f"hook.{name}", mod.run, artifact=artifact, manifest=config.manifest, env=config.env, job_id=artifact["job"]["id"], source_file=artifact["job"]["source_file"])
    if out: artifact.setdefault("hooks", {}).setdefault(name, []).append(out)
```

---

## 9) Error handling & determinism

* **Rule failures are contained:** If a detector/transform/validator raises, ADE records a neutral result and appends a rule‑error entry to the artifact, then continues.

```python
def safe_call(rule_id, fn, **kwargs):
    try:
        return fn(**kwargs) or {}
    except Exception as e:
        artifact = kwargs.get("artifact")
        if artifact is not None:
            artifact.setdefault("rule_errors", []).append({"rule": rule_id, "message": str(e), "at": now_iso()})
        return {}  # neutral
```

* **Determinism:** Keep rules pure and bounded (no global state, no unseeded randomness).
* **Security:** Runtime is sandboxed with time/memory limits; **network is off** by default (`allow_net: false`).

---

## 10) Resumability & atomic writes

Because the artifact is saved atomically **after each pass**, jobs can resume safely:

```python
def resume_if_needed(artifact):
    done = {p["pass"] for p in artifact.get("pass_history", [])}
    if 1 not in done: pass1_structure(...)
    if 2 not in done: pass2_mapping(...)
    if 3 not in done or 4 not in done or 5 not in done:
        pass3_to_5_generate(...)
```

---

## 11) Practical debugging (reading the artifact)

**Explain a mapping decision**

```python
def explain_mapping(artifact, table_id, raw_column_id):
    for s in artifact["sheets"]:
        for t in s["tables"]:
            if t["id"] == table_id:
                for m in t.get("mapping", []):
                    if m["raw"]["column"] == raw_column_id:
                        return {"target_field": m["target_field"], "score": m["score"], "contributors": m.get("contributors", [])}
```

**List validation errors with coordinates**

```python
def list_errors(artifact):
    items = []
    for s in artifact["sheets"]:
        for t in s["tables"]:
            for issue in t.get("validation", {}).get("issues", []):
                items.append((s.get("name"), t["id"], issue["a1"], issue["message"]))
    return items
```

---

## 12) Reference: helper utilities used above

```python
def mark_pass_done(artifact, n, name):
    artifact["pass_history"].append({"pass": n, "name": name, "completed_at": now_iso()})

def choose_best_label(totals: dict, order: list[str]) -> str:
    # highest score; tie broken by manifest-defined order
    if not totals: return order[0]
    top = max(order, key=lambda k: (totals.get(k, 0.0), -order.index(k)))
    return top
```

---

## 13) What to read next

* **Artifact spec & schema** → `./14-job_artifact_json.md`
* **Pass‑specific deep dives** →
  `./03-pass-find-tables-and-headers.md` (row detection)
  `./04-pass-map-columns-to-target-fields.md` (mapping)
  `./05-pass-transform-values.md` (transform)
  `./06-pass-validate-values.md` (validate)
  `./07-pass-generate-normalized-workbook.md` (writer)

---

### Appendix A — Minimal detector, transform, validator signatures

```python
# Row detector (Pass 1)
def detect_*(*, row_values_sample: list, row_index: int, sheet_name: str,
             table_hint: dict | None = None, manifest: dict = {}, artifact: dict = {}, **_) -> dict:
    # -> {"scores": {"header": float, "data": float, "separator": float}}

# Column detector (Pass 2)
def detect_*(*, header: str | None, values_sample: list, column_index: int,
             sheet_name: str, table_id: str, field_name: str, field_meta: dict,
             manifest: dict = {}, artifact: dict = {}, **_) -> dict:
    # -> {"scores": {field_name: float}}

# Transform (Pass 3)
def transform(*, values: list, header: str | None, column_index: int,
              sheet_name: str, table_id: str, field_name: str, field_meta: dict,
              manifest: dict = {}, artifact: dict = {}, **_) -> dict:
    # -> {"values": list, "warnings": list[str]}

# Validate (Pass 4)
def validate(*, values: list, header: str | None, column_index: int,
             sheet_name: str, table_id: str, field_name: str, field_meta: dict,
             manifest: dict = {}, artifact: dict = {}, **_) -> dict:
    # -> {"issues": [{"row_index": int, "code": str, "severity": "error"|"warning"|"info", "message": str}]}
```

---

By putting the **artifact** at the center and keeping passes narrowly scoped, ADE achieves explainable, resumable, and safe processing. The pseudocode above is the roadmap: create the initial artifact, stream rows to **structure**, sample columns to **map**, then **generate** the normalized workbook while recording everything you—and your auditors—need to understand the run.
