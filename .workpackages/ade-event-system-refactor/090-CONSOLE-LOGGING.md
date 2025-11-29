# Console Logging and Subprocess Streaming

This doc defines:

- The canonical `console.line` event.
- How ade-api captures stdout/stderr from child processes (build subprocesses and the engine) and turns them into events.
- How this interacts with engine-emitted structured events.

---

## 1. `console.line` event

**Type**: `console.line`  
**Payload**:

```jsonc
{
  "scope": "run",                    // "build" | "run"
  "stream": "stdout",                // "stdout" | "stderr"
  "level": "info",                   // "debug" | "info" | "warn" | "error"
  "phase": "extracting",             // optional
  "message": "Successfully installed ade-engine-0.2.0",
  "logger": "ade.engine.extract",    // optional
  "engine_timestamp": 1764384774     // optional numeric or ISO ts
}
```

**General rules:**

* One event type for all logs: build and run, API and engine.
* `scope`:

  * `"build"` - logs from build subprocesses.
  * `"run"` - logs from engine run subprocess.
* `stream`:

  * `"stdout"` - text read from stdout.
  * `"stderr"` - text read from stderr.
* `level`:

  * Default mapping:

    * `stdout` -> `info`
    * `stderr` -> `error`
  * Engine-emitted structured events can override this.
* `phase`:

  * Optional convenience; can come from:

    * Current active `build.phase.started`/`run.phase.started` in ade-api.
    * Or from engine itself when emitting `console.line` as structured events.

---

## 2. Streaming subprocess logs - high-level

Both build and run are implemented as child processes:

* **Build subprocesses**:

  * Pip/venv/config install commands.
  * Owned entirely by ade-api.
* **Run subprocess (engine)**:

  * Python process inside the venv that runs the ADE pipeline.
  * Outputs both:

    * Raw prints/logs.
    * Structured JSON events (NDJSON) with `type` fields.

We want a **single mechanism**:

> child stdout/stderr -> `read_stream_lines` helper -> `emit_event("console.line" or structured)` -> NDJSON + SSE

---

## 3. Hybrid structured/unstructured approach

We use a **hybrid** model for stdout/stderr:

1. Read a line from the child's stdout/stderr.
2. Try to parse it as JSON:

   * If it parses and has a `type` field:

     * Treat it as a **structured engine event**.
   * Otherwise:

     * Treat it as **raw console text** and wrap it in a `console.line` event.

This allows:

* Engine to emit structured events by printing JSON like:

  ```jsonc
  {"type":"run.phase.started","payload":{"phase":"extracting","message":"Starting extract"}}
  ```

* But any stray `print()` or library log still shows up as a `console.line` event.

---

## 4. Implementation sketch

### 4.1 `emit_console_line` helper (ade-api)

```python
def emit_console_line(
    *,
    run_id: str,
    build_id: str | None,
    scope: str,              # "build" | "run"
    stream: str,             # "stdout" | "stderr"
    message: str,
    level: str | None = None,
    phase: str | None = None,
    logger_name: str | None = None,
    engine_ts: str | None = None,
) -> None:
    if level is None:
        level = "info" if stream == "stdout" else "error"

    payload = {
        "scope": scope,
        "stream": stream,
        "level": level,
        "phase": phase,
        "message": message,
        "logger": logger_name,
        "engine_timestamp": engine_ts,
    }

    emit_event(
        type="console.line",
        source="engine",  # or "api" for build-created logs
        run_id=run_id,
        build_id=build_id,
        payload=payload,
    )
```

---

### 4.2 `read_stream_lines` helper (ade-api)

```python
async def read_stream_lines(
    stream,
    stream_name: str,           # "stdout" | "stderr"
    *,
    run_id: str,
    build_id: str | None,
    scope: str,                 # "build" | "run"
) -> None:
    while True:
        raw = await stream.readline()
        if not raw:
            break

        text = raw.decode("utf-8", errors="replace").rstrip("\n")

        # Try structured JSON first
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None

        if isinstance(obj, dict) and "type" in obj:
            # Structured engine event
            event_type = obj["type"]
            payload = obj.get("payload", {})

            if event_type == "console.line":
                # Engine already provided logging payload; normalize minimal fields
                payload.setdefault("scope", scope)
                payload.setdefault("stream", stream_name)
                payload.setdefault("level", "info" if stream_name == "stdout" else "error")

            emit_event(
                type=event_type,
                source="engine",
                run_id=run_id,
                build_id=build_id,
                payload=payload,
            )
        else:
            # Plain console line -> wrap as console.line
            emit_console_line(
                run_id=run_id,
                build_id=build_id,
                scope=scope,
                stream=stream_name,
                message=text,
            )
```

---

## 5. Build vs run usage

### 5.1 Build subprocesses (pip, venv, etc.)

* ade-api is fully in control of these subprocesses.

* For each build step that runs a child process:

  ```python
  process = await asyncio.create_subprocess_exec(..., stdout=PIPE, stderr=PIPE)

  await asyncio.gather(
      read_stream_lines(process.stdout, "stdout", run_id=run_id, build_id=build_id, scope="build"),
      read_stream_lines(process.stderr, "stderr", run_id=run_id, build_id=build_id, scope="build"),
  )
  ```

* This produces:

  * `console.line` events with `scope:"build"` for all output.
  * No need for engine involvement.

### 5.2 Engine subprocess (run)

* In the run worker, after build is ready:

  ```python
  process = await asyncio.create_subprocess_exec(
      sys.executable,
      "-m",
      "ade_engine.main",
      env=env_with_venv,
      stdout=PIPE,
      stderr=PIPE,
  )

  await asyncio.gather(
      read_stream_lines(process.stdout, "stdout", run_id=run_id, build_id=build_id, scope="run"),
      read_stream_lines(process.stderr, "stderr", run_id=run_id, build_id=build_id, scope="run"),
  )
  ```

* The engine itself:

  * Emits structured events by printing JSON with a `type` field.
  * Any raw prints go through as `console.line`.

---

## 6. Engine responsibilities

Inside ade-engine:

* Provide an `emit_event(type, payload)` helper that:

  * Constructs `{"type": type, "payload": payload, ...context...}`.
  * Writes JSON lines to stdout.
* Use `emit_event` for:

  * `run.phase.started`, `run.phase.completed`.
  * `run.table.summary`, `run.validation.summary`, `run.validation.issue`.
  * `run.error` when appropriate.
  * Optionally, structured `console.line` if you want to embed extra metadata.

Engine **does not** need to know about:

* `event_id`, `sequence`, or SSE.
* It only needs to output **NDJSON lines**; ade-api does the rest.

---

## 7. Why this design is simple and robust

* One log event type: `console.line`.
* One helper in ade-api handles **all** stdout/stderr for both build and run.
* Engine can be as structured or as messy as needed:

  * Structured JSON events become first-class AdeEvents.
  * Plain text becomes `console.line`.
* UI does not care where logs came from:

  * It just filters `type === "console.line"` and uses `scope` + `phase` for labeling.
