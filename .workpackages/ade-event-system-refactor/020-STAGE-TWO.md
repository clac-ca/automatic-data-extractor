## Work Package Checklist

* [x] Define and land the **new event namespace spec** (`engine.*` vs `run.*`/`build.*`) + update shared event schemas and type reference docs — engine/api/web docs updated to new prefixes
* [x] Implement **ade-engine engine_emitter** (NDJSON) + refactor all engine emissions to `engine.*` + add `engine.summary`
* [x] Implement **ade-api emitters** (`RunEventEmitter`, `BuildEventEmitter`) using `event_emitter.custom()` + refactor run/build orchestration to use them
* [x] Move **run summary generation into ade-engine** (engine-owned calculation) and have ade-api **persist on `engine.summary`**
* [x] Update **ade-web + ADE docs + config templates** to reflect new event types and recommended logger/event_emitter usage; remove old summary builder wiring

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Define and land the new event namespace spec — commit abc123`

---

# Work Package: Engine/API Scoped Event Emitters + Engine-Owned Run Summary

## 1. Objective

**Goal:**
Introduce a clean, intuitive event-emission architecture with namespace separation:

* **ade-engine emits `engine.*`** telemetry (engine-specific pipeline events + final summary).
* **ade-api emits `run.*` and `build.*`** lifecycle events (orchestration/DB state).
* ade-api forwards engine NDJSON events into the run event stream, and **persists the run summary** when it sees the engine’s final summary event.

You will:

* Add a first-class `engine_emitter` in ade-engine and migrate engine events away from `run.*`.
* Add first-class event emitters to ade-api (run/build) using `event_emitter.custom()` (no more raw `"run.completed"` string scatter).
* Move run summary calculation from ade-api into ade-engine, emitting **`engine.summary`** as the authoritative summary.
* Update docs/templates/UI to reflect the new contract.

The result should:

* Make it obvious “who emitted what” by **event type prefix** (engine vs api), without needing tribal knowledge.
* Remove the current API responsibility of recomputing summary from event logs (which today happens by reading events/manifest and aggregating)  and the “recompute if missing/invalid” behavior in `RunsService.get_run_summary()` .

---

## 2. Context (What you are starting from)

Today, the system already has a unified “ADE event” envelope and NDJSON storage, but it has two architectural problems:

1. **Namespace ambiguity / producer ambiguity**

* The original refactor plan explicitly said the engine should **not emit** public `run.started`/`run.completed`, leaving those to the orchestrator , but reality drifted: the engine runtime tests currently assert `run.completed` is emitted by the engine .
* This makes it harder to reason about ownership and where to add “special” run/build lifecycle behavior.

2. **Run summary calculation is in the wrong layer**

* ade-api currently builds `RunSummaryV1` by **reading event logs + manifest** and aggregating based on `run.started`, `run.completed`, `run.error`, `run.table.summary`, `run.validation.summary` .
* `RunsService.get_run_summary()` even recomputes it if cached invalid/missing .
* The engine docs acknowledge that (today) the engine **does not build the summary** and it’s computed by the API .

**Hard constraints / desired outcomes**

* No backward compatibility required (we can break event type names and delete old behavior).
* We want consistent developer ergonomics: `logger` (diagnostics) + `event_emitter` (structured events) throughout.
* We want explicit namespace separation:

  * `engine.*` = engine pipeline/internal facts
  * `run.*` / `build.*` = API lifecycle/orchestration facts

---

## 3. Target architecture / structure (ideal)

**Summary**

* Engine gets an **NDJSON `engine_emitter`** and uses it for all structured telemetry (`engine.*` + `console.line`).
* API gets emitter classes that wrap dispatchers and expose typed methods + `custom()`.
* Summary becomes an engine product: engine emits `engine.summary` (payload includes a full `RunSummaryV1`), API persists it when received.

```text
automatic-data-extractor/
  apps/
    ade-engine/
      src/ade_engine/
        infra/
          telemetry.py              # (refactor) base NDJSON sink + event construction
          event_emitter.py          # (new) EngineEventEmitter + ConfigEventEmitter
        core/
          engine.py                 # (refactor) emits engine.start/engine.complete + engine.summary
          summary/
            builder.py              # (new) EngineRunSummaryBuilder (engine-owned)
        schemas/
          telemetry.py              # (refactor) add engine.* payload models + update event type literals
          run_summary.py            # existing RunSummaryV1
      docs/
        07-telemetry-events.md      # update for engine.* + run/build ownership
        12-run-summary-and-reporting.md  # update: summary now computed in engine
    ade-api/
      src/ade_api/
        infra/events/
          base.py                   # (new) BaseEventEmitter (custom(), type checks, id context)
        features/
          runs/
            emitters.py             # (new) RunEventEmitter + RunScopedBuildEventEmitter
            service.py              # (refactor) emits run.*; persists engine.summary
            summary_builder.py      # (remove or restrict to validate-only/safe-mode stubs)
          builds/
            emitters.py             # (new) BuildEventEmitter (build-only stream)
            service.py              # (refactor) uses BuildEventEmitter
    ade-web/
      src/
        shared/...                  # update reducer to handle engine.* where it used run.*
  tests/
    apps/ade-engine/tests/...
    apps/ade-api/tests/...
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity:** From the event stream alone, you can tell if an event is engine-produced or API-produced by the prefix.
* **Maintainability:** No more raw string types sprinkled around services; “the thing that emits events” is a typed emitter.
* **Consistency:** `event_emitter.custom()` as the standard escape hatch, everywhere (engine, api, config code).

### 4.2 Key components / modules

* **`EngineEventEmitter` (ade-engine)** — emits structured `engine.*` events to NDJSON (logs/events.ndjson) with `source="engine"`.
* **`RunEventEmitter` (ade-api)** — emits `run.*` lifecycle events using the API dispatcher/storage (allocates event_id/sequence).
* **`BuildEventEmitter` (ade-api)** — emits `build.*` events (either run-scoped build events in the run stream, or build-only stream).
* **`EngineRunSummaryBuilder` (ade-engine)** — computes `RunSummaryV1` from in-memory pipeline facts (table summaries, validation, manifest, timings) and produces the payload for `engine.summary`.
* **`EngineEventForwarder` (ade-api, optional helper)** — forwards engine NDJSON lines into dispatcher while allowing “intercept” hooks (persist summary).

### 4.3 Key flows / pipelines

**Flow A — Run orchestration (API-owned `run.*`):**

1. API creates run/build rows and emits `run.queued`.
2. API emits `build.*` as it prepares the environment (as today).
3. API emits `run.start` (or `run.started`) when it transitions the DB run status to RUNNING.
4. API spawns engine and forwards:

   * non-JSON stdout → `console.line(scope="run")`
   * JSON lines → forwarded as ADE events (now `engine.*`) into the run stream
5. API receives `engine.summary` and persists summary_json to DB.
6. API emits `run.complete` with final status/paths (and a reference to persisted summary).

**Flow B — Engine pipeline telemetry (engine-owned `engine.*`):**

1. Engine emits `engine.start` with metadata (engine_version, mode, etc.).
2. Engine emits `engine.phase.*`, `engine.table.summary`, `engine.validation.*`, and automatic detector score events if enabled.
3. Engine emits `engine.summary` (full `RunSummaryV1`).
4. Engine emits `engine.complete` (status + error info).

### 4.4 Open questions / decisions

* **Decision: event naming**
  Adopt `engine.start`, `engine.summary`, `engine.complete` (present tense) to align with your preference (“engine.start” etc). Similarly: `run.start`, `run.complete`, `build.start`, `build.complete`. (Breaking change, acceptable.)

* **Decision: where summary lives**
  The authoritative run summary is emitted by engine as `engine.summary` and persisted by API on receipt. We stop computing summary from logs in API for engine-backed runs (today’s approach is in `summary_builder.py` ).

* **Decision: what the API does if summary never arrives (engine crash)**
  Since we’re not targeting backwards-compat, we still need resilience. Rule:

  * If no `engine.summary` arrives, persist a minimal summary stub with failure_code `engine_summary_missing`, and include `failure_stage="engine"` in `run.complete`.

---

## 5. Implementation & notes for agents

### 5.1 Event type spec (new canonical taxonomy)

**API (orchestrator) lifecycle events**

* `run.queued`
* `run.start`
* `run.complete`
* `build.created`
* `build.start`
* `build.phase.start` / `build.phase.complete` (optional)
* `build.complete`

**Engine (pipeline telemetry)**

* `engine.start`
* `engine.phase.start` / `engine.phase.complete`
* `engine.table.summary`
* `engine.validation.summary`
* `engine.validation.issue` (optional)
* `engine.detector.column.score` *(auto-emitted by engine wrapper; see below)*
* `engine.detector.row.score` *(auto-emitted by engine wrapper; see below)*
* `engine.summary` *(final run summary payload)*
* `engine.complete`
* `engine.error` (optional; non-terminal error marker)

**Cross-cut**

* `console.line` stays as-is (used by both API and engine). It already carries `scope` (“build”/“run”), stream, level, message.

### 5.2 Engine changes (ade-engine)

#### A) Introduce `EngineEventEmitter` + NDJSON sink in engine

Create `apps/ade-engine/src/ade_engine/infra/event_emitter.py`:

* `class BaseNdjsonEmitter`: handles writing one JSON object per line to a sink.
* `class EngineEventEmitter(BaseNdjsonEmitter)`:

  * `.custom(type_suffix, **payload)` emits `engine.{type_suffix}`
  * typed helpers: `.start(...)`, `.phase_start(phase)`, `.table_summary(...)`, `.summary(run_summary)`, `.complete(...)`
* `class ConfigEventEmitter(BaseNdjsonEmitter)` (passed into ade-config detectors/hooks):

  * `.custom(type_suffix, **payload)` emits `config.{type_suffix}` (or `engine.config.{...}` if you want config to be “engine-produced”; pick one and document it).

> Why separate engine vs config namespaces? Because once we make prefixes meaningful, config authors get a natural “this came from config code” bucket.

#### B) Refactor all engine emissions to `engine.*`

* Update engine runtime and pipeline runner to call `engine_emitter.*` instead of emitting `run.*` events.
* Remove/rename any `RunStartedPayload`/`RunCompletedPayload` emission from engine (which currently shows up in tests as `run.completed` ).

#### C) Engine-owned run summary

Port the core aggregation logic from the API’s `build_run_summary(...)` (which currently aggregates from `run.table.summary` etc ) into engine, but **do it from pipeline facts**, not by re-reading NDJSON.

Implementation approach:

* New `EngineRunSummaryBuilder` that accepts:

  * `manifest: ManifestV1 | None`
  * `started_at`, `completed_at`
  * `status`, `failure info`
  * `table_summaries: list[EngineTableSummaryPayload]`
  * `validation_summary` (if emitted)
  * optional environment fields (engine_version, config_version, env metadata)
* Emit `engine.summary` with payload: `{ "summary": RunSummaryV1(...) }`

**Example skeleton**

```py
# apps/ade-engine/src/ade_engine/core/summary/builder.py
from ade_engine.schemas import ManifestV1, RunSummaryV1

class EngineRunSummaryBuilder:
    def __init__(self, *, manifest: ManifestV1 | None, run_id: str | None, workspace_id: str | None, configuration_id: str | None):
        self.manifest = manifest
        self.table_summaries = []
        self.validation_summary = None
        self.started_at = None
        self.completed_at = None
        self.status = None
        self.failure = None
        self.ids = {"run_id": run_id, "workspace_id": workspace_id, "configuration_id": configuration_id}

    def on_table_summary(self, payload: dict) -> None:
        self.table_summaries.append(payload)

    def on_validation_summary(self, payload: dict) -> None:
        self.validation_summary = payload

    def finalize(self) -> RunSummaryV1:
        # Implement the same arithmetic as ade-api’s build_run_summary core,
        # but driven off captured table_summaries and manifest.
        ...
```

#### D) Automatic detector score events (engine-emitted)

Since you already wanted this: keep it, but now under engine namespace:

* When engine calls a column detector, capture:

  * detector name
  * candidate field name (the thing it’s scoring for)
  * score
  * contextual info: header, sample_size, source_column_index, table identifiers
* Emit as `engine.detector.column.score`
* For row detectors similarly emit `engine.detector.row.score`

This should be emitted by the *engine wrapper around calling detectors*, not by config authors.

### 5.3 API changes (ade-api)

#### A) Add event emitters to ade-api (run/build), with `custom()`

Create:

* `apps/ade-api/src/ade_api/infra/events/base.py`
* `apps/ade-api/src/ade_api/features/runs/emitters.py`
* `apps/ade-api/src/ade_api/features/builds/emitters.py`

**Core principle:** all API emissions become one of:

* `run_events.start(...)`
* `build_events.complete(...)`
* `run_events.custom("whatever", ...)`

No raw type strings outside the emitter modules.

**Example API emitter interface**

```py
# ade_api/features/runs/emitters.py
class RunEventEmitter:
    def __init__(self, dispatcher, *, workspace_id, configuration_id, run_id, build_id=None):
        self._d = dispatcher
        self._ids = ...

    async def queued(self, *, mode: str) -> AdeEvent:
        return await self._d.emit(type="run.queued", payload={"mode": mode}, **self._ids)

    async def start(self, *, mode: str) -> AdeEvent:
        return await self._d.emit(type="run.start", payload={"mode": mode}, **self._ids)

    async def complete(self, *, status: str, exit_code: int | None, failure: dict | None, summary_ref: dict | None) -> AdeEvent:
        return await self._d.emit(type="run.complete", payload={...}, **self._ids)

    async def custom(self, type_suffix: str, *, payload: dict) -> AdeEvent:
        return await self._d.emit(type=f"run.{type_suffix}", payload=payload, **self._ids)
```

#### B) Refactor run orchestration to emit `run.*` only from API

In `RunsService.stream_run`:

* Emit `run.start` for *all* engine-backed runs (today it only emits `run.started` in validate-only/safe-mode short circuits ).
* Stop relying on engine to emit run lifecycle.

#### C) Persist summary on `engine.summary`

In the engine event forwarding loop:

* When you parse an engine NDJSON event:

  * If `event.type == "engine.summary"`:

    * validate payload
    * persist into `runs.summary` immediately
    * store it in-memory for final `run.complete`

Then remove the use of `build_run_summary_from_paths(...)` in engine-backed completion (that function currently reads events/manifest ).

Also update `get_run_summary()`:

* Prefer DB summary only.
* Remove the “recompute from events/manifest” fallback  (unless you explicitly want a backfill tool, but not as runtime behavior).

#### D) Update/remove summary_builder.py + tests

* Either delete `apps/ade-api/src/ade_api/features/runs/summary_builder.py` and its unit tests, or restrict it to:

  * validate-only runs (no engine)
  * safe-mode runs (no engine)
    …but do not use it for the normal engine path.

### 5.4 Web/UI changes (ade-web)

Since event types change:

* Update the reducer to consume:

  * `engine.phase.*` instead of `run.phase.*`
  * `engine.table.summary` instead of `run.table.summary`
  * `engine.validation.*` instead of `run.validation.*`
  * `run.start/run.complete` instead of `run.started/run.completed`

Also update any “summary UI” that expects run.completed to embed summary fields (if it does). The correct path becomes:

* summary is persisted by API (DB) when `engine.summary` arrives
* UI can either:

  * read it from `run.complete` payload if you include it there, OR
  * fetch `/runs/{id}/summary`

### 5.5 Documentation + templates (required final step)

Update:

* `apps/ade-engine/docs/07-telemetry-events.md`
* `apps/ade-engine/docs/12-run-summary-and-reporting.md` (it currently says engine doesn’t build it )
* `apps/ade-api/src/ade_api/templates/config_packages/**` to include:

  * “logger vs event_emitter” guidance
  * examples of `event_emitter.custom("checkpoint", payload={...})`
  * a note that detector score events are auto-emitted (so config authors don’t do it manually)

### 5.6 Testing requirements

**ade-engine**

* Update engine runtime tests that currently assert `run.completed` (engine-emitted)  to assert:

  * `engine.complete` is present
  * `engine.summary` is present and validates into `RunSummaryV1`

**ade-api**

* Add an integration-ish unit test:

  * Simulate engine forwarding stream with an `engine.summary` event
  * Assert `RunsService` persists `runs.summary` and `run.complete` is emitted

**ade-web**

* Update reducer tests or add fixture replay test with new events.

### 5.7 Performance / safety notes

* Summary building should be **O(number_of_tables + number_of_issues)** and avoid storing per-row details.
* Ensure `engine.summary` payload size remains reasonable—include aggregates and per-file/per-field breakdowns (as RunSummaryV1 does), but avoid “all events replay” duplication.
* API persistence should be idempotent: if two `engine.summary` events appear, last-write-wins (and log a warning).
