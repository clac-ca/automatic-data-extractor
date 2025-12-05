## Work Package Checklist

* [ ] **Write + land the ADE Event Spec v1** (envelope fields, naming conventions, versioning rules, payload rules).
* [ ] **Add `schemas/events/*` in BOTH ade-engine + ade-api** (vendored/duplicated code) with:

  * base envelope (shared core)
  * engine catalog (engine-emitted event payloads)
  * api catalog (api-emitted event payloads)
  * registry + validators
* [ ] **Refactor ADE-ENGINE emission** to write **BaseEvent v1** (strict) NDJSON with `event_id` UUID + `type_version`, using typed payload helpers only.
* [ ] **Refactor ADE-API ingestion + dispatcher** to:

  * accept engine BaseEvent v1 (and legacy forms during migration),
  * upgrade/enrich to **ApiEvent v1** (adds sequence + context + source),
  * validate again before persisting/streaming.
* [ ] **Refactor ADE-API lifecycle emitters** (`run.*`, `build.*`) to only emit **ApiEvent v1** via helpers—no ad-hoc dict payloads.
* [ ] **Update SSE/Frontend contracts + docs** to treat **ApiEvent v1** as canonical (and document which fields are always present).
* [ ] **Add conformance + regression tests** (golden NDJSON, schema strictness, legacy-compat parsing, stream end conditions).

---

# Revamp ADE Event System: Vendored Schemas + Engine BaseEvent → API ApiEvent (v1)

## 1. Objective

**Goal:**
Make ADE events **strict, versioned, and consistent** across the ADE engine and ADE API—without creating build-time or runtime coupling between the repos/packages.

You will:

* Introduce a **duplicated (vendored)** `schemas/events/*` tree in **both** `ade-engine` and `ade-api`.
* Define a **shared “base” envelope** that both sides implement identically.
* Define an **engine BaseEvent v1** (lightweight) and an **API ApiEvent v1** (enriched) that the frontend consumes.
* Refactor emitters and ingestors so **every emitted event conforms to the spec** and every event is **validated** at the boundary (engine write, API ingest/persist).

The result should:

* Prevent schema drift via `extra="forbid"` + a registry for `(type, type_version)` validation.
* Keep the console UX intact: **one run stream** containing lifecycle + console lines + engine telemetry (single subscription for ADE console).

---

## 2. Context (What you are starting from)

### Existing structure

* ADE has an event system today where:

  * engine emits NDJSON events,
  * API ingests and re-emits/stamps/streams via SSE,
  * frontend consumes SSE.
* Event payloads are currently permissive in several places (dict payloads, “allow” extras), which makes it easy to drift.

### Current behavior / expectations

* **Single run stream** is the desired UX contract: a user subscribes once and sees build/run phases, console output, summaries, completion.
* API currently stamps ordering (`sequence`) and uses that as SSE `id`.
* Engine produces events high-frequency (`console.line`, detector scores, summaries) which must remain streamable.

### Known issues / pain points

* Schema drift is too easy (ad-hoc dicts, inconsistent payload shapes).
* Confusion about “what is the canonical event spec”: engine and API evolve separately and can diverge.
* Completion events and artifacts have historically drifted in shape (`artifacts` blocks, different “execution” structures, etc).

### Hard constraints

* **No shared artifact generation** (no shared package, no codegen required).
* **OK with code duplication** across ade-api and ade-engine (base changes are rare).
* Must retain the ability to stream **console lines + diagnostic telemetry** to the ADE console.
* Events need to carry a **version stamp**, and API and engine should be able to evolve independently (per-type versioning).

---

## 3. Target architecture / structure (ideal)

**High-level:**

* Engine writes **BaseEvent v1** (minimal envelope + typed payload + versions).
* API reads BaseEvent (and legacy), validates, upgrades to **ApiEvent v1** with context + ordering + source, persists + streams.
* Frontend treats **ApiEvent v1** as canonical.

> “Two streams?”
> No. We keep **one stream**. Logs are “events” (`console.line`). High-volume events remain as event types; consumers filter by `type` / `payload.scope` / etc.

### File tree (duplicated in BOTH ade-engine and ade-api)

```text
automatic-data-extractor/
  apps/
    ade-engine/
      src/ade_engine/
        schemas/
          events/
            __init__.py
            base/
              __init__.py
              envelope.py          # BaseEvent v1 (core envelope)
              primitives.py        # enums/common types (levels, streams, ids)
              payloads.py          # events shared by both (console.line)
            engine/
              __init__.py
              payloads.py          # engine.* payload models
              catalog.py           # registry registrations (engine)
            registry.py            # (type, type_version) -> payload model
            factory.py             # build/validate BaseEvent
    ade-api/
      src/ade_api/
        schemas/
          events/
            __init__.py
            base/                  # identical to ade-engine base/
              __init__.py
              envelope.py
              primitives.py
              payloads.py
            engine/                # identical structure; validates engine events
              __init__.py
              payloads.py
              catalog.py
            api/
              __init__.py
              envelope.py          # ApiEvent v1 extends BaseEvent
              payloads.py          # run.* + build.* payload models
              catalog.py           # registry registrations (api)
            registry.py
            factory.py             # build/validate ApiEvent
        infra/events/
          dispatcher.py            # validate + stamp seq + persist + publish
        features/
          runs/emitters.py
          builds/emitters.py
  tests/
    test_events_spec_conformance.py
    test_events_ingest_upgrade_legacy.py
    test_run_stream_sse_end.py
    fixtures/
      golden_engine_events.ndjson
      golden_api_events.ndjson
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity:** One obvious envelope for engine (“BaseEvent”) and one for frontend (“ApiEvent”).
* **Maintainability:** Event types + payloads live in catalogs with strict registries; adding a new event is “add payload model + register”.
* **Scalability:** Single stream supports both UX console and structured telemetry; per-type versioning avoids breaking consumers.

### 4.2 Key components / modules

* **`schemas/events/base/envelope.py`** — BaseEvent v1: minimal required fields (`schema`, `schema_version`, `type`, `type_version`, `event_id`, `created_at`, `payload`)
* **`schemas/events/api/envelope.py`** — ApiEvent v1: BaseEvent + `sequence`, `source`, and context IDs (`workspace_id`, `run_id`, etc.)
* **`schemas/events/registry.py`** — maps `(type, type_version)` to payload models; validates payload; rejects unknown keys (`extra="forbid"`)
* **`factory.py`** — helpers for emitting & validating events (engine + api each have their own copy, same structure)

### 4.3 Key flows / pipelines

#### Flow 1 — Engine emits → API enriches → Frontend consumes (single stream)

1. **Engine** constructs `BaseEvent` with:

   * `schema="ade.event"`, `schema_version=1`
   * `type="console.line"` etc
   * `type_version=1`
   * `event_id=str(uuid4())`
   * `created_at=utcnow()`
   * `payload` validated from registry
2. Engine writes to NDJSON (`events.ndjson`) line-delimited JSON.
3. **API** tails NDJSON, parses `BaseEvent`:

   * validates `(type, type_version)` payload
   * upgrades to `ApiEvent` by adding:

     * `source="engine"`
     * context IDs (workspace_id/run_id/config/build) from run context already in scope
     * `sequence` (monotonic per run stream)
4. API persists ApiEvent to run’s canonical events log and streams via SSE.
5. **Frontend** consumes only ApiEvent fields; uses `sequence` for ordering/resume and `type` to route UI behavior.

#### Flow 2 — API lifecycle emission (run/build events)

1. API constructs `ApiEvent` directly (not via BaseEvent):

   * event_id uuid
   * created_at utcnow
   * type/type_version
   * source="api"
   * sequence assigned by dispatcher
   * payload validated
2. Same persistence + SSE.

### 4.4 Open questions / decisions

* **Decision: one stream; no mandatory dual subscription.**
  We keep a single run event stream. Logs are `console.line` events, and verbose engine telemetry remains as event types. Consumers can filter by `type` and/or payload fields.

* **Decision: event_id is producer-generated UUID everywhere.**
  Engine-generated events and API-generated events both use UUID strings for `event_id`. API does not rewrite `event_id`; it only adds `sequence`.

* **Decision: envelope versioning + per-type versioning.**

  * `schema_version` changes only when envelope changes (rare).
  * `type_version` changes when a payload changes (more common; type-by-type).

* **Decision: tolerate legacy engine NDJSON during migration.**
  API ingest path supports:

  * BaseEvent v1 (new format)
  * Legacy lines (best-effort parsing/upgrading) for a transition period (bounded by a config flag + tests).
    New engine emissions MUST be BaseEvent v1.

---

## 5. Implementation & notes for agents

### 5.1 Event spec: canonical fields + naming rules (write first)

**Envelope: BaseEvent v1 (Engine → API boundary)**
Required fields:

* `schema`: `"ade.event"`
* `schema_version`: `1`
* `type`: string, lower snake/dot (`run.complete`, `console.line`, `engine.phase.start`)
* `type_version`: int (default 1)
* `event_id`: UUID string
* `created_at`: RFC3339 UTC datetime
* `payload`: object (typed per registry; may be `{}` for payload-less events)

**Envelope: ApiEvent v1 (API → Frontend)**
BaseEvent + required:

* `sequence`: int (monotonic within run stream; used as SSE `id`)
* `source`: `"api" | "engine" | "web"`
* Context IDs (required when in scope; typically always by the time it hits frontend):

  * `workspace_id`, `configuration_id`, `run_id`, `build_id` (nullable allowed, but API should populate wherever possible)

**Naming conventions**

* Event type namespace:

  * `run.*` — API-owned run lifecycle
  * `build.*` — API-owned build lifecycle
  * `engine.*` — engine telemetry/progress
  * `console.line` — console output/log line
* All keys in envelope + payload are `snake_case`.

**Versioning conventions**

* Bump `type_version` when:

  * required/optional fields change, type changes, semantics change
* Never change the meaning of an existing `(type, type_version)`—introduce a new version.

---

### 5.2 Step-by-step implementation plan (incremental commits)

#### Commit A — Add duplicated `schemas/events/*` scaffolding in both packages

* Create directories + `__init__.py`
* Add base envelope models (identical in both)
* Add `console.line` payload model (base payload shared)
* Add registry mechanism with strict validation (`extra="forbid"`)

Acceptance

* Unit tests proving unknown envelope keys fail
* Unit tests proving `console.line` unknown payload keys fail

#### Commit B — Define engine event payload catalog (engine side + api copy)

Engine catalog includes payload models for the current engine emitted types (at minimum):

* `engine.start`
* `engine.phase.start`
* `engine.complete`
* `engine.detector.row.score`
* `engine.detector.column.score`
* `engine.(file|sheet|table|run).summary` (or whatever set is currently emitted)
* `console.line` (already base)

Implementation

* Create `schemas/events/engine/payloads.py` (strict models)
* Register them in `schemas/events/engine/catalog.py` for both engine and api copies

Acceptance

* Registry validates every engine event type under test fixtures

#### Commit C — Refactor ADE-ENGINE to emit BaseEvent v1 everywhere

* Introduce a local `EventFactory` in engine:

  * generates event_id UUID
  * validates payload via registry
  * writes NDJSON line of BaseEvent
* Replace ad-hoc dict writes with typed payload helper usage

Acceptance

* Engine produces NDJSON that validates line-by-line as BaseEvent v1
* No absolute FS paths leak in payloads unless explicitly allowed (use run-relative where possible)

#### Commit D — Refactor ADE-API ingestion to parse BaseEvent v1 and upgrade to ApiEvent v1

* Add `ApiEvent` envelope model in `schemas/events/api/envelope.py`
* Add upgrade function:

  * take BaseEvent + run context → produce ApiEvent
  * assign `sequence`
  * set `source="engine"`
  * attach IDs (workspace_id, run_id, etc.)
* Add legacy parser:

  * if `schema` missing, attempt to map legacy keys into BaseEvent then upgrade
  * gate behind config flag `ADE_EVENTS_ACCEPT_LEGACY=true` (default true for one release, then false)

Acceptance

* API can ingest both new engine events and legacy events (with tests)
* Persisted/streamed events are always ApiEvent v1

#### Commit E — Refactor ADE-API lifecycle emitters to emit ApiEvent v1 only

* Create `schemas/events/api/payloads.py` for:

  * `run.queued`, `run.start`, `run.complete`
  * `build.created`, `build.started`, `build.phase.start`, `build.completed`
* Force all emitters to construct typed payloads and dispatch `ApiEvent`
* Remove bespoke top-level fields; no ad-hoc dict payloads

Acceptance

* `run.complete` payload shape is stable and spec-conformant
* API-only events validate via registry

#### Commit F — Update SSE rules + frontend + docs

* Ensure SSE continues:

  * `id: sequence`
  * `event: type`
  * `data: <ApiEvent json>`
* Update frontend type definitions to match ApiEvent v1
* Replace/remove legacy schema doc that doesn’t match reality; document new spec

Acceptance

* Frontend compiles against new types
* A full run streams without UI regressions

#### Commit G — Conformance + regression tests

Add tests:

* `test_events_spec_conformance.py`

  * unknown envelope keys rejected
  * unknown payload keys rejected
  * registry rejects unknown `(type, type_version)`
* `test_events_ingest_upgrade_legacy.py`

  * legacy → BaseEvent → ApiEvent upgrade
* `test_run_stream_sse_end.py`

  * stream terminates on API `run.complete` and contains ordered `sequence`

Acceptance

* CI green
* Golden fixtures validate against schemas

---

### 5.3 Implementation details (how to keep complexity low)

#### No interdependence

* Duplicate the same modules in both packages.
* No imports across package boundaries.
* Base changes are manual in both places (rare), optionally protected by a “base files identical” test.

#### Strictness defaults

* Envelope: `extra="forbid"`
* Payload models: `extra="forbid"`
  Exception only for intentionally “open” payloads (must be explicit and documented).

#### Payload size / console streaming

* Keep one stream.
* If some payloads are huge (e.g. a full column list), that’s allowed *if it’s required for console UX*, but it must still be typed and versioned.
* If payloads become too large, add an API policy later (soft limit + truncation markers), but do NOT introduce a second stream as part of this work package.

---

### 5.4 Coding standards / style

* Prefer Pydantic v2 (`model_validate`, `model_dump(mode="json")`)
* Always `exclude_none=True` when writing NDJSON
* Use `uuid4()` for `event_id`
* Always UTC timestamps

### 5.5 Testing requirements

* Golden NDJSON fixtures for both engine output and API output
* Ensure both event trees validate those fixtures
* Integration test that runs a minimal pipeline and validates the resulting run stream

### 5.6 Security / performance notes

* Do not emit absolute filesystem paths in any payload fields unless explicitly required and approved; prefer run-relative paths or API links.
* API ingest should be resilient:

  * if legacy parsing fails, log + drop the line (or emit a `console.line` warning) rather than crashing the run.