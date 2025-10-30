# Glossary — Core Terms

**Audience:** All contributors and reviewers  
**Goal:** Use precise, consistent terminology across docs and code

> **At a glance**
>
> - Link the first use of any defined term on a page to this glossary.
> - Prefer single-line definitions; wrap identifiers and keys in code font.
> - Group related terms under the same heading so contributors can skim quickly.

## Core entities

- Workspace — Logical container for configs, jobs, and member access.
- Config — Folder of rules (manifest + scripts); holds no production data.
- Config package — Config folder prepared for transport, tracked by `package_sha256`.
- Manifest — Versioned JSON file (`ade.manifest/v0.5`) describing env, engine defaults, hooks, and canonical columns.
- Job — One run on one uploaded file using the active config; produces mapping, normalized output, and logs.

## Runtime context

- Job context — Dict returned from `on_job_start` hooks; passed to detectors, transforms, validators, and later hooks.
- Paths — Keyword-only argument with resolved directories like `paths["config"]`, `paths["resources"]`, `paths["cache"]`, `paths["job"]`, and `paths["job_input"]`.
- Engine defaults — Limits in `manifest.engine.defaults` (timeouts, memory, `allow_net`).

## Spreadsheet structure

- Sheet — Tab within the spreadsheet.
- Table — Contiguous block of data within a sheet.
- Header row — Row or rows likely containing field names for a table.
- Bounds — Table extent; includes `a1` coordinates such as `B4:G159`.
- Raw column — Source column within a detected table.
- Canonical column — Normalized output column key (for example, `member_id`).

## Pipeline and passes

- Pass 1 — Row analysis that finds tables, header rows, and bounds.
- Pass 2 — Column analysis that runs detectors and aggregates scores.
- Assignment — Greedy step that pairs canonical columns with raw columns when the final score is positive.
- Pass 3 — Transformation that runs column modules over the full dataset.
- Pass 4 — Validation that applies required checks and optional final hooks.

## Scripts and hooks

- Column module — Python module that owns detectors/transform (and optional validator) for one canonical column.
- Detector — Any `detect_*` callable returning score adjustments based on header, samples, or context.
- Transform — Required `transform(**kwargs)` producing normalized values and warnings.
- Validator — Optional callable that inspects normalized values and returns issues without mutating them.
- Lifecycle hook — Script exposing `run(**kwargs)` for events such as activation or job execution.
- `on_activate` — Optional hook that runs when a config switches to `active`; failure aborts the activation.
- `on_job_start` — Hook that runs before detection and builds the `jobContext`.
- `on_after_extract` — Hook that runs after transformation with mapping data and warnings.
- `on_job_end` — Hook that always runs at the end of a job with `success` and `error` details.

## Artifacts

- Mapping — Decision record: raw→canonical assignments with scores and notes (`mapping.v1`).
- Normalized output — Clean spreadsheet with canonical headers in manifest order.
- Validation report — Warnings/errors with locations; blocking errors fail the job.
- Logs — Execution timings, hook output, and detector/transform diagnostics.
- Job input — JSON export of detected tables, used by column modules that need full data.
- Package checksum — Stable ZIP hash stored as `package_sha256` for auditing.

## Filesystem and packaging

- Config directory — Root at `data/configs/<config_id>/` containing the manifest, hooks, scripts, and optional docs.
- Resources directory — Optional `resources/` under the config directory for supporting data files.
- Cache directory — Hook-accessible path (`paths["cache"]`) for temporary artifacts reused during jobs.
- Job directory — Per-run folder referenced by `paths["job"]` that holds transient data and logs.

## Security and lifecycle

- Secrets — Encrypted at rest in the manifest; decrypted only inside sandboxed child processes.
- Status — `draft | active | archived`; only draft configs are editable.
- Active config — Exactly one active config per workspace at a time.
- Sandbox — Restricted subprocess (`python -I -B`) with rlimits and no network unless enabled.

## IDs and addressing

- Raw column id — Stable id like `sheet0.t0.c4` (sheet 0, table 0, column 4).
- Table id — Pair of sheet/table indices such as `sheet1.t2`.
- A1 bounds — Excel-style range string (for example, `B4:G159`).

---

## Minimal example
Tiny detector and transform sketch for a `member_id` column.

```python
def detect_header_keywords(*, header: str, values: list, **_):
    if header and "member" in header.lower() and "id" in header.lower():
        return {"scores": {"self": 1.5}}
    return {"scores": {}}

def transform(*, values: list, **_):
    cleaned = [(str(v).strip().upper() or None) if v is not None else None for v in values]
    return {"values": cleaned, "warnings": []}
```

---

## What’s next

- See structure and scripts in [01-config-packages.md](./01-config-packages.md)
- Read the pass-by-pass flow in [02-job-orchestration.md](./02-job-orchestration.md)

---

Previous: [11-troubleshooting.md](./11-troubleshooting.md)  
Next: [13-design-decisions.md](./13-design-decisions.md)
