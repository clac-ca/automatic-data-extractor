# Developer Docs

**Audience:** Contributors and developers working in this repo  
**Goal:** Provide a consistent, fast‑to‑scan index and authoring order.

> **At a glance**
>
> - Use `00-style-guide.md` and `00-templates/` to write pages.
> - Schemas live in `01-schemas/`; design decisions in `02-design-decisions/`.
> - Pages are numbered to control order (01…11). Keep numbers stable.

## Before you begin

- Read `00-style-guide.md` (voice, tone, structure) and `AGENTS.md` (authoring rules).
- Prefer one idea per page; link to adjacent topics under “What’s next”.

## Top‑level layout

```
docs/
└─ developers/
   ├─ 00-style-guide.md
   ├─ 00-templates/
   │  ├─ page-template.md
   │  └─ snippet-conventions.md
   ├─ 01-schemas/
   │  ├─ manifest.v0.5.schema.json
   │  └─ mapping.v1.schema.json
   ├─ 02-design-decisions/
   │  ├─ dd-0001-file-backed-configs.md
   │  ├─ dd-0002-single-active-config.md
   │  ├─ dd-0003-multi-pass-jobs.md
   │  └─ dd-0004-manifest-secrets-model.md
   ├─ 01-overview.md
   ├─ 02-glossary.md
   ├─ 03-config-packages.md
   ├─ 04-jobs-pipeline.md
   ├─ 05-mapping-format.md
   ├─ 06-runtime-model.md
   ├─ 07-backend-api.md
   ├─ 08-validation-and-diagnostics.md
   ├─ 09-examples-and-recipes.md
   ├─ 10-scaling-and-performance.md
   ├─ 11-security-and-secrets.md

```
We use Design Decisions (DD) instead of ADR to avoid confusion with ADE. DDs are short, numbered, and permanent.

## Authoring order

1. 00‑style‑guide.md and 00‑templates/ (sets tone and structure)
2. 01‑overview.md (anchor page with “pipeline at a glance”)
3. 03‑config‑packages.md (rules live in files; manifest & modules)
4. 04‑jobs‑pipeline.md (multi‑pass flow; artifacts)
5. 05‑mapping‑format.md and 01‑schemas/ (reference + examples)
6. 06‑runtime‑model.md and 07‑backend‑api.md (how it runs; how to call it)
7. 08‑validation‑and‑diagnostics.md and 09‑examples‑and‑recipes.md (practical use)
8. 10‑scaling‑and‑performance.md and 11‑security‑and‑secrets.md (operational depth)
9. 02‑design‑decisions/ (capture the big decisions as you lock them)

## Emphasis (repeat across pages)

- Config is a folder; manifest is configuration—not data.
- One active config per workspace keeps behavior deterministic.
- Multi‑pass jobs: decide with small samples (detection), act on the whole (column‑wise transform), then validate.
- Scripts are simple functions (`detect_*`, `transform`, `run`) with explicit kwargs; environment already injected.
- Filesystem is the source of truth; DB is the index; export/import = zip.
- Security by design: secrets encrypted at rest; decrypted only inside isolated execution.

## What’s next

- Start with `00-style-guide.md` and `00-templates/page-template.md`.
- Then draft `01-overview.md` followed by `03-config-packages.md`.
