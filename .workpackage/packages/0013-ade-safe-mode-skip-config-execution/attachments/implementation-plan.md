# Implementation Plan — ADE Safe Mode (Skip Config Execution)

## Intent
Provide an escape hatch (`ADE_SAFE_MODE=true`) that lets the FastAPI backend boot and serve
the UI while **never importing or running user-supplied config code**. Operators can revert or
edit broken configs and then restart without safe mode.

## User Flows
- **Normal startup (default)** — unchanged; jobs execute immediately after submission.
- **Safe mode startup** — ADE boots, surfaces a banner + API health detail, but:
  - job submissions fail fast with a friendly message,
  - workers never spawn, and
  - existing job artifacts remain readable.

## Backend Touchpoints
1. **Configuration (`backend/app/shared/core/config.py`)**
   - Add `safe_mode: bool = False` field (env var `ADE_SAFE_MODE`).
   - Normalize truthy/falsey values using Pydantic coercion.
   - Expose helper property `safe_mode_enabled` (optional syntactic sugar).

2. **App bootstrap (`backend/app/main.py`)**
   - Persist flag on `app.state` so dependencies/routers can reference it.
   - Optionally emit structured log line when safe mode is enabled to aid observability.

3. **Health endpoint (`backend/app/features/health/service.py`)**
   - Include a component detail (`{"name": "safe-mode", "status": "degraded", ...}`) when enabled.
   - Allows the UI to show a passive banner without extra calls.

4. **Jobs service (`backend/app/features/jobs/service.py`)**
   - Inject `settings.safe_mode` into the service.
   - **Before** manifest load / job creation, short-circuit when safe mode is active:
     ```python
     if self._settings.safe_mode:
         raise JobSubmissionError(
             "ADE_SAFE_MODE is enabled. Job execution is temporarily disabled so you can revert config changes."
         )
     ```
   - Ensure attempts still result in committed `JobSubmissionError` -> HTTP 400 via router.

5. **Orchestrator guard (`backend/app/features/jobs/orchestrator.py`)** *(defensive)*
   - Validate `settings.safe_mode` before spawning subprocesses; if triggered outside the main service, log + raise.
   - Protects future callers that might bypass `JobsService`.

6. **Frontend contract**
   - The dashboard already calls `/api/health` (confirm in SPA); surface `safe_mode` flag there.
   - Add typed client helper (`SafeModeStatus`) so UI can render:
     - prominent banner,
     - disable job submission button with tooltip referencing env var.

## Error Messaging
- Single source string defined in `jobs/service.py` for API & logging.
- Copy guidance: “ADE_SAFE_MODE is enabled. Job execution is temporarily disabled so you can revert config changes in your config package and restart without safe mode.”

## Rollout Steps
1. Implement backend changes above.
2. Update developer docs (`docs/developers/02-job-orchestration.md`, `.env.example` if present).
3. Wire frontend banner/button state.
4. Add release note entry describing the recovery workflow.

## Risks & Mitigations
- **Hidden bypass via future code path** → Guard both service and orchestrator.
- **Operators unsure how to exit safe mode** → Include restart instructions in banner + docs.
- **Automated clients treat 400 as fatal** → Encourage them to inspect response message; optionally add error code field if needed later.
