# Build Streaming - Current vs Target Design

This doc captures:

- What we have **today** for build streaming (v1).
- The **target unified design** where build events are part of the run stream.
- How the dedicated build endpoint behaves after the refactor.

---

## 1. Current build streaming (v1)

**Endpoint**

```http
POST /workspaces/{workspace_id}/configurations/{configuration_id}/builds
Content-Type: application/json
Accept: application/x-ndjson
```

* Request body: `BuildCreateRequest` with:

  * `options.force` (bool)
  * `options.wait` (bool)
  * `stream` flag controlled by query param.
* `force`:

  * `true` -> recompute fingerprint; rebuild venv even if active build matches.
  * `false` -> reuse active build if fingerprint matches.

**Streaming mode (`stream=true`)**

* Response `Content-Type: application/x-ndjson`.
* Each line is an `AdeEvent` (old envelope schema) with types:

  * `build.created`
  * `build.started`
  * `build.phase.started`
  * `build.console`
  * `build.completed`
* Logs:

  * `build.console` with `stream`, `level`, `message`, `created (epoch seconds)`.

**Run interaction (v1)**

* Run stream auto-triggers a build when needed:

  * `options.force` passes through.
* During run streaming, we **proxy** the build stream:

  * `BuildsService.stream_build` events are yielded first.
  * After build completes, we inject a console banner:

    * "Configuration build completed; starting ADE run."
* Build and run streams are **not unified**:

  * Build uses `build.*` + `build.console`.
  * Run uses `run.*` + `run.console` and forwarded engine events.

---

## 2. Target design - unified run stream

### 2.1 Intuitive UX

We want:

* **One stream per `run_id`**.
* That stream includes both:

  * Build events (`build.*`, `console.line` with `scope:"build"`).
  * Run events (`run.*`, `console.line` with `scope:"run"`, `run.table.summary`, etc.).
* For almost all clients (UI, CLI), the experience is:

  * "I start a run" -> I see **everything** relevant, in order.

### 2.2 What changes

* **Run streaming becomes primary**:

  * `POST /.../runs?stream=true`:

    * Returns **SSE** stream of AdeEvents.
    * Contains both build and run events.
* **Build streaming is secondary**:

  * `POST /.../builds?stream=true`:

    * Also returns SSE, but only build-related events for that build.
* All event types are standardized:

  * No more `build.console`; logs are `console.line` with `scope:"build"`.
  * Envelope is the new `AdeEvent`.

---

## 3. Target behavior in detail

### 3.1 Run-triggered build

When ade-api handles `POST /.../runs`:

1. Create `run_id` and (if needed) `build_id`.

2. Emit:

   * `run.queued`
   * `build.created`

3. Decide on build reuse vs new build.

4. If a new build is required:

   * Emit `build.started`.

   * For each build phase:

     * `build.phase.started`
     * `build.phase.completed`

   * For pip/venv logs:

     * Emit `console.line` events with `scope:"build"`.

   * At the end:

     * Emit `build.completed`.

5. Emit a banner:

   * `console.line` with `scope:"run"`, message "Configuration build completed; starting ADE run."

6. Start engine run and continue emitting `run.*` events.

Everything above is visible in the **same SSE stream** when `stream=true`.

---

### 3.2 Dedicated build endpoint (after refactor)

`POST /.../builds?stream=true` should:

* Return **SSE** events with the same shapes as build-related events in the run stream.
* Implementation can:

  * Either treat it as a "build-only run" and reuse the run machinery internally.
  * Or key events by `build_id` and manage a separate subscriber registry (with `run_id` set to a synthetic value or the same as `build_id`).
* Main requirement: **same event shape**, same `build.*` and `console.line scope:"build"` payloads.

---

## 4. Implementation notes

* Build orchestration in ade-api should:

  * Use the central event dispatcher for **all** build events, whether coming from:

    * API-managed subprocesses (pip/venv/config install).
    * Engine-managed build scripts (if any).
* For subprocess logs:

  * See `090-CONSOLE-LOGGING.md` for the `read_stream_lines` helper that:

    * Reads stdout/stderr.
    * Emits `console.line` events for each line with `scope:"build"`.

Once this is implemented, you can safely remove:

* v1 NDJSON-specific streaming codepaths for builds.
* `build.console` event type and any code that emits/consumes it.
