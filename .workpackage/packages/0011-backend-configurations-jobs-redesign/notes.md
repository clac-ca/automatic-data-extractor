# Backend config engine v0.4 rollout

Focus: move from the legacy draft/publish DB snapshots to workspace-scoped file packages (`manifest.json`, hooks, `columns/*.py`) that implement detector/transform scripts, run through the new validation pipeline, and power job extraction via the subprocess runner.

Owner: jkropp
Status: active
Created: 2025-10-27T18:44:08.305Z

---
- 2025-10-27T18:53:18.918Z • jkropp: Activated package and added kickoff design at attachments/design.md covering version-snapshot core, schema, APIs, and runner outline.
- 2025-10-27T18:55:07.134Z • jkropp: Iterated design doc with clearer scope, schema sketch, guardrails, and prioritized implementation steps.
- 2025-10-27T18:59:15.086Z • jkropp: Added attachments/tasks.md with phased implementation checklist covering schema, services, API, jobs, frontend, cutover, and follow-ups.
- 2025-10-27T19:00:23.358Z • jkropp: Refined tasks checklist with feature-flag prep, migration phases, and explicit cutover steps.
- 2025-10-27T19:02:18.152Z • jkropp: Updated design and tasks to reflect direct schema rewrite (replace initial migration, drop legacy configuration paths).
- 2025-10-28T23:42:57.970Z • jkropp: Added config-engine-spec-v0.4.md summarizing new column script API, hook kwargs, validation, and runner flow so we can start replacing legacy config service.
- 2025-10-28T23:45:25.023Z • jkropp: Replaced design.md and tasks.md with v0.4 file-backed config engine plan aligning to detector/transform spec. Ready to start ripping out legacy config_version flow.
- 2025-10-28T23:49:19.466Z • jkropp: Reworked design.md and tasks.md with backend-only plan: archive legacy feature, add configs table + active pointer, rebuild file-backed router/services, and align tasks to new phase breakdown.
- 2025-10-28T23:54:56.583Z • jkropp: Refreshed design.md with SPEC-grade backend blueprint and synced workpackage summary/tags/criteria to backend-only scope.
- 2025-10-28T23:58:51.161Z • jkropp: Dropped resources/ from default template and updated design/tasks/workpackage so configs focus purely on storage + validation while jobs owns sandbox execution.
