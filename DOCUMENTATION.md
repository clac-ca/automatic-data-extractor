# Documentation strategy draft

## Goals and audiences
- **Primary readers**
  - *Platform administrators*: deploy and operate ADE in controlled environments (e.g. Azure Container Apps, on-prem Docker hosts).
  - *Support engineers*: triage incidents, understand data flow, run maintenance commands, and answer "how does it work" questions.
  - *Configuration authors / power users*: design document-type logic, manage revisions, inspect jobs and events.
- **Objectives**
  - Provide a single navigation structure that separates conceptual knowledge, day-to-day tasks, and deep references.
  - Minimise duplicated guidance between README and docs by turning the README into a concise overview that points into the doc set.
  - Keep operational content actionable (checklists, commands, environment variables) so teams can follow it during incidents.

## Proposed documentation architecture
```
docs/
├─ index.md                        # Landing page + personas + quick entry points
├─ overview/
│  ├─ system-overview.md           # Architecture, components, glossary pointers
│  ├─ data-flow.md                 # End-to-end job lifecycle, storage layout
│  └─ glossary.md                  # Link/alias to ADE_GLOSSARY.md
├─ getting-started/
│  ├─ quickstart-docker.md         # Run the published container locally (single command)
│  ├─ local-development.md         # Backend + frontend setup without Docker, tests
│  └─ sample-data.md               # Using examples/ to exercise the pipeline
├─ deployment/
│  ├─ prerequisites.md             # Network, storage, identity, sizing expectations
│  ├─ azure-container-apps.md      # Step-by-step ACA deployment + Bicep/Terraform pointers
│  ├─ container-platforms.md       # Generic Docker/Kubernetes guidance, volumes, secrets
│  ├─ configuration-management.md  # Managing env vars, secrets, image updates
│  └─ upgrade-and-backup.md        # Rolling upgrades, backup/restore of SQLite + docs
├─ operations/
│  ├─ configuration-lifecycle.md   # Adapt existing doc; UI/API workflows, event trails
│  ├─ document-retention.md        # Adapt existing doc; manual delete, purge scheduler, CLI
│  ├─ jobs-and-processing.md       # Job statuses, metrics, logs, replaying inputs
│  ├─ monitoring-and-alerting.md   # Health endpoint, purge status, log signals
│  └─ runbooks.md
│      ├─ purge-runbook.md         # Troubleshooting expired documents
│      ├─ storage-capacity.md      # Responding to low disk scenarios
│      ├─ sso-troubleshooting.md   # Debugging auth failures
│      └─ upgrade-checklist.md     # Pre/post deployment verification steps
├─ security/
│  ├─ authentication.md            # Expand existing doc, modes, session cookies
│  ├─ sso-setup.md                 # Detailed OIDC setup, provider matrices, claims mapping
│  ├─ user-and-api-access.md       # CLI usage, roles, API keys, admin allowlist
│  └─ audit-and-events.md          # Event feed model, querying timelines, retention expectations
├─ integration/
│  ├─ api-overview.md              # REST surface, pagination, auth requirements
│  ├─ job-payloads.md              # Canonical JSON contracts (reuse glossary cheat sheets)
│  ├─ automation-recipes.md        # Sample scripts (upload, launch job, poll results)
│  └─ data-export.md               # How to consume outputs, document storage URIs
└─ reference/
   ├─ environment-variables.md     # Every ADE_* variable, defaults, notes
   ├─ cli-tools.md                 # `auth.manage`, purge CLI usage, exit codes
   ├─ database-schema.md           # Tables, key fields, relationships
   └─ release-notes.md             # Version history, incompatible changes
```

## Page-by-page outlines

### Landing page (`docs/index.md`)
- Purpose of ADE and high-level value proposition.
- Persona-based navigation: "Deploy ADE", "Operate ADE", "Integrate with ADE".
- Quick links to Quickstart, Azure deployment, Authentication, Runbooks.
- Pointer to README for repo contributors vs operators (clarify separation).

### Overview
- **system-overview.md**
  - Summarise architecture diagram (FastAPI backend, React UI, processor helpers, SQLite, filesystem storage).
  - Link to components in codebase (`backend/app`, `frontend/`, `var/`).
  - Describe deterministic principles (immutable configs, ULIDs, event log).
- **data-flow.md**
  - Step-by-step: upload document → configuration resolution → job execution → outputs → events.
  - Illustrate storage locations (`var/documents/uploads`, `output`) and how job responses embed document summaries.
  - Call out scheduler + purge lifecycle.
- **glossary.md**
  - Surface ADE_GLOSSARY content, either by embedding or referencing the canonical file.

### Getting started
- **quickstart-docker.md**
  - Pull published image, run via `docker run` or `docker compose` with mounted volumes for `var/`.
  - Default credentials, minimal configuration (only `ADE_AUTH_MODES=basic`).
  - Sanity checks: hit `/health`, upload sample doc, run a demo job via API.
- **local-development.md**
  - Expand README Windows instructions into cross-platform guidance (macOS/Linux + Windows).
  - Setup Python venv, install `[dev]`, run backend with `uvicorn`, run frontend (if/when added), execute pytest/ruff/mypy.
  - Tips on resetting SQLite/db state, using `.env`.
- **sample-data.md**
  - Explain contents of `examples/`, how to trigger jobs using sample files, expected outputs for smoke tests.

### Deployment
- **prerequisites.md**
  - Supported infrastructure assumptions (CPU/memory baseline, disk layout, TLS termination, outbound internet for SSO discovery).
  - Identity requirements (OIDC provider, secrets store) and compliance considerations.
- **azure-container-apps.md**
  - Container registry prep (ACR), building/pushing image, defining ACA environment.
  - Bicep/ARM/Terraform snippet for container app with volume mounts (Azure Files for `var/`), secrets for `ADE_SSO_*`, `ADE_SESSION_*`.
  - Scaling guidance, log streaming via Log Analytics, backup strategy using scheduled Jobs or Azure Storage snapshots.
  - Post-deploy smoke tests.
- **container-platforms.md**
  - Generic Docker/Kubernetes instructions: persistent volumes, readiness probe hitting `/health`, environment variable injection.
  - Guidance for running on Docker Compose for small teams.
- **configuration-management.md**
  - How to manage configuration (env var overrides, `.env` usage, secret rotation) across environments (dev/stage/prod).
  - Recommendations for storing `.env` securely and layering defaults vs overrides.
- **upgrade-and-backup.md**
  - Rolling upgrade steps (build image, apply, verify) and rollback plan.
  - Backing up SQLite + documents, verifying restore.
  - Automating backups (e.g. cron, Azure Automation).

### Operations
- **configuration-lifecycle.md**
  - Rework existing doc to fit new format (lifecycle goals, APIs, UI actions, event log examples, rollback scenarios).
  - Add quick reference table for statuses (draft/active/retired) and commands.
- **document-retention.md**
  - Adapt existing retention doc with clearer summary, scheduler diagrams, CLI usage table, environment knobs.
- **jobs-and-processing.md**
  - Explain job statuses, transitions, metrics/log fields, how to inspect outputs.
  - Include guidance for reprocessing: duplicate input doc, reuse configuration version.
- **monitoring-and-alerting.md**
  - Describe `/health` payload, purge status block, log patterns to alert on (failed purge, auth errors, DB connection issues).
  - Suggest Prometheus or log search queries if available.
- **runbooks.md** sub-pages
  - Opinionated, checklist-style instructions: prerequisites, verify, remediate, escalate.
  - Provide commands, API calls, log locations, expected outcomes.

### Security
- **authentication.md**
  - Combine existing authentication overview with session details, cookie attributes, fallback order.
  - Document `ADE_AUTH_MODES`, failure responses, multi-mode behaviour.
- **sso-setup.md**
  - Deep dive into OIDC configuration: discovery expectations, state token signing, supported algorithms (RS256/HS256), auto-provisioning toggle.
  - Provider-specific notes (Azure AD, Okta, Auth0) mapping claims to email.
  - Troubleshooting tips referencing runbook.
- **user-and-api-access.md**
  - CLI usage (`python -m backend.app.auth.manage` commands) with examples, admin allowlist behaviour, API key lifecycle (future placeholder if not implemented yet but schema exists).
- **audit-and-events.md**
  - Explain event schema, common event types, how UI uses timeline endpoints, retention/cleanup considerations.

### Integration
- **api-overview.md**
  - Entry point for external systems: authentication requirements, base URL, JSON conventions, pagination.
  - Link to OpenAPI (if generated) and highlight critical endpoints (`/documents`, `/jobs`, `/events`).
- **job-payloads.md**
  - Expand glossary "payload cheat sheets" with annotated examples and field descriptions.
  - Clarify deterministic fields vs mutable metrics/logs.
- **automation-recipes.md**
  - Sample `curl`/Python snippets: upload document, create job, poll status, download outputs.
  - Mention idempotency considerations, recommended retries.
- **data-export.md**
  - How to fetch outputs, meaning of `stored_uri`, guidance for cleaning up downloaded files, verifying checksums.

### Reference
- **environment-variables.md**
  - Table of all `ADE_*` vars from `config.Settings`, defaults, when required, interactions (e.g. `session_cookie_secure` + `SameSite`).
  - Notes on runtime overrides, `.env` usage.
- **cli-tools.md**
  - Summaries for auth manage CLI and purge CLI (options, sample output, exit codes, failure modes).
  - Mention future CLI placeholders.
- **database-schema.md**
  - Table-per-table breakdown referencing `backend/app/models.py` (primary keys, indexes, relationships, important columns).
  - Include ER-style diagram guidance (textual now, future visual asset).
- **release-notes.md**
  - Template for tracking changes: version, date, highlights, upgrade notes, migrations.

## Existing content migration plan
- `docs/authentication.md` → feed into `security/authentication.md` and `security/sso-setup.md` (split general vs SSO deep dive).
- `docs/configuration_lifecycle.md` → becomes `operations/configuration-lifecycle.md` with refreshed structure.
- `docs/document_retention_and_deletion.md` → becomes `operations/document-retention.md` plus supporting runbook.
- `README.md` retains high-level summary but will link into docs for detailed procedures; trim duplicated instructions after docs are created.
- `ADE_GLOSSARY.md` remains canonical; expose it under `overview/glossary.md` via include or symlink.

## Assets and tooling
- Produce a simple architecture diagram (Mermaid or PNG) showing UI ↔ API ↔ processor ↔ SQLite/storage relationships.
- Diagram job lifecycle (upload → job → outputs → events) and purge scheduler timing.
- Consider generating OpenAPI schema automatically for API references.
- Adopt consistent admonitions ("Note", "Warning", "Tip") for operational steps.

## Style and maintenance guidelines
- Use task-focused headings ("Configure Azure Container Apps", "Run the purge CLI") and include copy-pasteable commands.
- Provide before/after validation steps for any procedure (e.g. check `/health`, confirm job status).
- Surface environment variable names in backticks and explain defaults vs overrides.
- Link related runbooks and conceptual docs to avoid duplicated explanations.
- Review documentation with each code change that modifies API shape, auth behaviour, or configuration.
- Store future changelog entries in `reference/release-notes.md` as part of release process.

