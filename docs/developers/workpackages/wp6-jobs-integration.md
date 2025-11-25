# WP6 — Runs Integration (Always Run in the Assigned venv)

## Goal
Ensure every run records the `build_id` it runs with and launches the worker inside the corresponding virtual environment created by WP5.

## Flow
1. Run submission receives `workspace_id` and optional `config_id`.
2. Server resolves the target config:
   * If `config_id` is omitted, use the workspace’s active config (error `412` if none).
3. Call `ensure_build(workspace, config)`:
   * If a build is ready, reuse it.
   * If no build exists, WP5 logic creates one before returning.
4. Persist the returned `build_id` on the run record.
5. Launch the worker with the ensured venv:
   ```
   ${ADE_VENVS_DIR}/{workspace}/{config}/{build_id}/bin/python \
     -I -B -m ade_engine.worker <run_id>
   ```
6. Runs never install packages at runtime; they rely on the frozen environment.

## Acceptance
* Every run row contains `build_id` (and optionally `venv_path`) used during execution.
* Worker invocations reference the ensured venv path, not a global interpreter.
* Rebuilds do not affect running runs; new runs adopt the new pointer automatically.
* Submissions without an active config fail fast with a clear error.
