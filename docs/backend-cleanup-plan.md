# Backend Cleanup Plan

This plan enumerates every backend package so we can methodically review the
codebase for obsolete worker-era code and other dead modules. Each entry
captures the review status and any follow-up actions.

| Area | Scope | Status | Notes |
| ---- | ----- | ------ | ----- |
| Core entrypoints | `app/main.py`, `app/api/` | ✅ reviewed | Worker hooks previously removed. |
| Shared core | `app/shared/core/` | ✅ reviewed | Confirmed no worker-era helpers remain; responses/middleware still used. |
| Shared adapters | `app/shared/adapters/` | ✅ reviewed | Removed unused queue adapters; filesystem storage retained. |
| Shared db | `app/shared/db/` | ✅ reviewed | Confirmed engine/session helpers have no worker toggles or unused paths. |
| Features – auth | `app/features/auth/` | ✅ reviewed | Dependencies/services all exercised; no worker triggers or dead modules remain. |
| Features – configurations | `app/features/configurations/` | ✅ reviewed | Validation runs in-process via multiprocessing; no queue hooks or unused helpers found. |
| Features – documents | `app/features/documents/` | ✅ reviewed | Storage/service layers rely solely on synchronous flows; no legacy hooks detected. |
| Features – health | `app/features/health/` | ✅ reviewed | Health endpoints minimal. |
| Features – jobs | `app/features/jobs/` | ✅ reviewed | Ensured services/repositories run inline without queue dependencies. |
| Features – pagination | `app/features/pagination/` | ✅ reviewed | Shared dependency still used by list endpoints; no extra helpers to drop. |
| Features – roles | `app/features/roles/` | ✅ reviewed | Authorization/service layers consistent with inline jobs; no obsolete adapters. |
| Features – system settings | `app/features/system_settings/` | ✅ reviewed | CRUD helpers minimal and current; no legacy toggles. |
| Features – users | `app/features/users/` | ✅ reviewed | Repository/service methods all invoked by routers/tests; no dead code. |
| Features – workspaces | `app/features/workspaces/` | ✅ reviewed | Workspace services operate without job queue dependencies; no removals needed. |
| Tests – API | `backend/tests/api/` | ✅ reviewed | No queue expectations remain; suite matches synchronous behaviour. |
| Tests – services | `backend/tests/services/` | ✅ reviewed | Removed queue tests and confirmed no worker hooks remain. |

We will update this document as each area is audited and any obsolete code is
removed.
