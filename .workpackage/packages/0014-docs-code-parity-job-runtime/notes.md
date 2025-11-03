# Docs/code parity: job runtime

Owner: jkropp
Status: draft
Created: 2025-11-03T19:59:46.296Z

---

## Context

- Dev docs describe a queued job runner with per-package dependency installs and lifecycle hooks that do not exist (or behave differently) in the current FastAPI/worker implementation.
- Goal: either deliver the missing runtime features or revise the docs, leaning toward implementation so the platform matches the published contract.

## Key disconnects

- Jobs are executed synchronously with `201` responses and no retry endpoint, whereas the docs promise a bounded queue, `202` responses, and HTTP 429 back-pressure (`docs/developers/02-job-orchestration.md:24-156` vs `backend/app/features/jobs/service.py:29-157`, `backend/app/features/jobs/router.py:25-145`).
- Config packages advertise automatic `requirements.txt` installs and artifact logging for third-party deps, but the worker only copies files and never runs `pip` (`docs/developers/01-config-packages.md:353-360` vs `backend/app/features/jobs/orchestrator.py:53-215`, `backend/app/features/jobs/storage.py:34-87`, `backend/app/features/jobs/worker.py:1-236`).
- The glossary claims `on_activate` hooks block activation and that `on_after_extract` fires after transform with success/error metadata, none of which is implemented (`docs/developers/12-glossary.md:45-53` vs `backend/app/features/configs/service.py:664-706`, `backend/app/features/jobs/runtime/pipeline.py:124-193`, `backend/app/features/jobs/runtime/loader.py:32-96`).
- Documentation still references `logs.txt` and omits generated files like `run-request.json` even though storage now writes structured `events.ndjson` (`docs/developers/02-job-orchestration.md:24-38` vs `backend/app/features/jobs/storage.py:34-56`).

## Checklist

- [ ] **[P0] Job queue + retry API parity** — Introduce the async queue/back-pressure behaviour the docs promise (`202` on submit, 429 when saturated), add `/retry` endpoint, and cover concurrency controls + integration tests.
- [ ] **[P0] Per-job dependency install + artifact logging** — Detect `requirements.txt`, install into an isolated vendor dir before pipeline execution, surface install results + versions in the artifact, and harden with unit/worker tests.
- [ ] **[P1] Lifecycle hook alignment** — Execute `on_activate` during activation (failing activation on errors), ensure hook ordering/events match docs, or update docs if behaviour should remain as-is.
- [ ] **[P1] Documentation cleanup** — Once runtime parity lands (or agreed deviations exist), update `docs/developers/01-config-packages.md`, `02-job-orchestration.md`, and the glossary to reflect the real behaviour (queue semantics, hook stages, log paths, dependency handling).
- [ ] **[P2] Telemetry + health tooling** — Expand `events.ndjson` logging (or add human-readable tail helpers) so the doc examples stay accurate after the queue/dependency work.

## Coordination

- Sync with workpackage #12 (“Docs parity for job artifact & hooks”) to avoid duplicative doc edits—hand off hook documentation changes once behaviour is settled.

## Open questions

- Should we implement the documented queue or revise the docs to match the current synchronous approach? Decision needed before execution starts.
- Do we guarantee offline dependency installation (wheelhouse) or constrain installs to network-enabled runs only?

## Working assumptions (2025-11-03)

- Adopt the documentation contract: queue + bounded workers with HTTP 202/429 semantics, persisted job status polling, and `/retry`.
- Perform dependency installs only when `requirements.txt` exists *and* the manifest or admin settings allow network access; otherwise fail with a clear diagnostic.
- Run `on_activate` hooks synchronously during activation and fail the activation when any hook raises.
- 2025-11-03T20:00:18.632Z • jkropp: Documented major doc/code gaps (job queue, requirements install, lifecycle hooks) and added prioritized checklist.
- 2025-11-03T20:08:08.110Z • jkropp: Captured working assumptions: implement documented queue semantics (202/429 + retry), gated requirements installs, and activation hooks.
