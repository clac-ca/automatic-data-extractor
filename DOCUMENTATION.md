# Documentation strategy draft

## Goals and audiences
- **Primary readers**
  - *Platform administrators* – deploy ADE in controlled environments (Azure Container Apps, Docker/Kubernetes), manage upgrades, and own configuration secrets.
  - *Support engineers / on-call responders* – triage incidents, understand the pipeline, run maintenance commands, and explain behaviour to internal stakeholders.
  - *Configuration authors / power users* – maintain document-type logic, inspect jobs and events, and validate extraction output.
- **Secondary readers**
  - *Contributors inside the repo* – need pointers from the README into the operator-focused docs without duplicating guidance.
- **Objectives**
  - Provide persona-based navigation that separates foundational concepts, setup tasks, day-to-day operations, and deep reference material.
  - Keep the README as a concise overview that links to the documentation set; avoid duplicating long-form procedures in both places.
  - Optimise for actionability: every task page should surface prerequisites, commands, validation steps, and rollback guidance where applicable.

## Documentation principles
- **Persona-first navigation** – every top-level section should map to a reader goal (understand, set up, operate, secure, integrate).
- **Task-oriented content** – lead with checklists and copy-pasteable commands; follow with background context for curious readers.
- **Single source of truth** – reuse canonical assets (e.g. `ADE_GLOSSARY.md`, OpenAPI schema) instead of restating definitions.
- **Progressive disclosure** – intro pages summarise concepts and link to detailed guides so readers can stop when they have enough information.
- **Change awareness** – highlight configuration flags, defaults, and the impact of changing them; flag risky operations.

## Information architecture
```
docs/
├─ index.md                       # Landing page + persona jump links
├─ understand/
│  ├─ architecture.md             # System diagram, component responsibilities
│  ├─ data-flow.md                # End-to-end job lifecycle, storage layout
│  └─ glossary.md                 # Include or link to ADE_GLOSSARY.md
├─ setup/
│  ├─ quickstart-docker.md        # Run the published container locally
│  ├─ local-development.md        # Backend-only and full-stack dev without Docker
│  ├─ azure-container-apps.md     # ACA deployment guide (prereqs + IaC pointers)
│  ├─ other-platforms.md          # Generic Docker/Kubernetes/Compose guidance
│  └─ sample-data.md              # Using examples/ to exercise the pipeline
├─ operate/
│  ├─ configuration-lifecycle.md  # Versioning workflow and audit trails
│  ├─ document-retention.md       # Expiration defaults, purge scheduler, CLI
│  ├─ jobs-and-processing.md      # Job states, metrics, replay guidance
│  ├─ monitoring-and-alerting.md  # Health endpoint, logs, capacity checks
│  └─ upgrade-and-backup.md       # Rolling upgrades, backup/restore procedures
├─ security/
│  ├─ authentication.md           # Modes, session cookies, CLI usage
│  ├─ sso-setup.md                # OIDC configuration + troubleshooting
│  └─ access-management.md        # Roles, API keys, audit expectations
├─ integrate/
│  ├─ api-overview.md             # REST surface, auth, pagination
│  ├─ job-payloads.md             # Canonical JSON contracts with examples
│  ├─ automation-recipes.md       # Upload, launch job, poll, download scripts
│  └─ data-export.md              # Consuming outputs and stored URIs
├─ reference/
│  ├─ environment-variables.md    # ADE_* catalogue with defaults and notes
│  ├─ cli-tools.md                # Auth + maintenance CLIs, exit codes
│  ├─ database-schema.md          # Table descriptions and relationships
│  └─ release-notes.md            # Version history and upgrade callouts
└─ runbooks/
   ├─ purge-runbook.md            # Troubleshooting expired documents
   ├─ storage-capacity.md         # Responding to low disk scenarios
   ├─ sso-troubleshooting.md      # Debugging authentication failures
   └─ upgrade-verification.md     # Pre/post deployment checklist
```

### Navigation experience
- `index.md` acts as the hub: short description, persona cards (“Deploy ADE”, “Operate ADE”, “Integrate with ADE”), quick links to critical pages (Quickstart, Azure deployment, SSO setup, purge runbook).
- Each folder’s landing page (e.g. `operate/index.md` if needed later) should summarise the contained pages and when to read them.
- Runbooks live separately from conceptual operations docs so on-call engineers can jump straight into actionable checklists.

## Page outlines

### Landing page (`docs/index.md`)
- Purpose of ADE, supported scenarios, and call-outs for who should read what.
- Persona-based entry points and highlights for the most common tasks.
- Link back to README for contributors plus instructions on where to report issues.

### Understand
- **architecture.md**
  - Diagram (Mermaid/PNG) showing UI ↔ FastAPI ↔ processor ↔ SQLite/document storage.
  - Bullet summary of each component and the directories to inspect in the repo.
  - Deterministic design principles (immutable configurations, ULIDs, event log).
- **data-flow.md**
  - Step-by-step walkthrough: upload → configuration resolution → job execution → outputs → events.
  - Storage paths (`var/documents/uploads`, derived outputs) and purge lifecycle.
  - How event timelines relate to job/doc responses.
- **glossary.md**
  - Surface ADE_GLOSSARY verbatim or via include; add navigation tips from glossary terms to relevant guides.

### Setup
- **quickstart-docker.md**
  - Pull/run commands, required environment variables, mounted volumes, default credentials.
  - Sanity checks: `/health`, upload sample, create job via API.
- **local-development.md**
  - Cross-platform setup (Windows/macOS/Linux) for backend (venv, uvicorn) and optional frontend.
  - Quality gates (pytest, ruff, mypy, npm scripts when frontend lands), resetting SQLite/doc storage.
  - Tips for `.env` usage and cleaning stale sessions.
- **azure-container-apps.md**
  - Prerequisites (resource group, ACR, identity, storage).
  - Deployment flow: build/push image, create secrets, configure ACA revision, mount Azure Files for `var/`.
  - Bicep/ARM/Terraform snippets, scaling notes, Log Analytics pointers, post-deploy validation.
- **other-platforms.md**
  - Docker Compose and generic Kubernetes notes: readiness/liveness, volumes, secrets, load balancers.
  - Guidance for air-gapped environments or on-prem Docker hosts.
- **sample-data.md**
  - Overview of files in `examples/`, how to run them through the pipeline, and expected results for smoke tests.

### Operate
- **configuration-lifecycle.md**
  - Adapt existing doc: lifecycle stages (draft → active → retired), activation workflow, rollback patterns, related events.
  - Quick reference table for statuses and key API endpoints/CLI commands.
- **document-retention.md**
  - Adapt existing doc: default expiration, manual overrides, purge scheduler, CLI usage, environment knobs.
- **jobs-and-processing.md**
  - Job status transitions, metrics/log schema, reprocessing guidance, links to automation recipes.
- **monitoring-and-alerting.md**
  - `/health` response fields, purge summary, log patterns to watch, suggested alert thresholds.
- **upgrade-and-backup.md**
  - Rolling upgrade checklist (backup, deploy, verify, rollback), copying SQLite + documents, restoration testing.

### Security
- **authentication.md**
  - Combine existing authentication overview with session handling, CLI usage, failure responses.
- **sso-setup.md**
  - Deep dive into OIDC configuration (issuer discovery, redirect URLs, claims mapping), provider-specific notes (Azure AD, Okta, Auth0), validation/testing steps, troubleshooting links.
- **access-management.md**
  - Roles, API keys, session TTLs, auditing expectations, how to rotate secrets and deactivate accounts.

### Integrate
- **api-overview.md**
  - Base URL conventions, auth requirements, pagination patterns, link to OpenAPI schema.
- **job-payloads.md**
  - Annotated request/response examples (upload, job creation, events) referencing glossary terms.
- **automation-recipes.md**
  - `curl`/Python snippets for upload → job → poll → download, idempotency advice, error handling.
- **data-export.md**
  - How to consume outputs (`stored_uri`, directories), verifying checksums, clean-up considerations.

### Reference
- **environment-variables.md**
  - Table of all `ADE_*` settings from `config.Settings`, defaults, when required, security notes, interactions.
- **cli-tools.md**
  - Auth management CLI and purge CLI commands, arguments, sample output, exit codes, error handling.
- **database-schema.md**
  - Table-by-table descriptions (primary keys, important columns, relationships) referencing `models.py`, future ERD placeholder.
- **release-notes.md**
  - Template for version/date, highlights, upgrade steps, incompatible changes.

### Runbooks
- Opinionated checklists with clear prerequisites, diagnostics, remediation steps, and escalation guidance.
- Planned pages: purge issues, low disk/storage, SSO failures, upgrade verification. Add more as incidents surface.

## Prioritised rollout
1. **Foundation (phase 1)** – index, architecture, quickstart, local development, azure deployment, authentication, sso setup, configuration lifecycle, document retention, environment variables, purge runbook.
2. **Operations deep dive (phase 2)** – jobs-and-processing, monitoring, upgrade/backup, automation recipes, cli tools, storage capacity runbook.
3. **Richer references (phase 3)** – database schema, data export, release notes template, additional runbooks (SSO troubleshooting, upgrade verification), other-platforms guide.

## Existing content migration plan
- `docs/authentication.md` → split into `security/authentication.md` and `security/sso-setup.md` (keep CLI snippets, expand SSO steps).
- `docs/configuration_lifecycle.md` → becomes `operate/configuration-lifecycle.md` with lifecycle tables and workflow diagrams.
- `docs/document_retention_and_deletion.md` → becomes `operate/document-retention.md`; reuse scheduler/CLI sections and link to purge runbook.
- `README.md` retains the high-level overview and local-dev primer but delegates detailed procedures to the docs; update cross-links once new pages exist.
- `ADE_GLOSSARY.md` remains canonical; expose it via `understand/glossary.md` (include or symlink) and link glossary terms to relevant guides.

## Assets and tooling
- Generate a simple architecture diagram and job lifecycle diagram (Mermaid or PNG checked into `docs/assets/`).
- Capture OpenAPI schema automatically for `integrate/api-overview.md` (e.g. export during build).
- Standardise admonitions (“Note”, “Warning”, “Tip”) for operational caveats and troubleshooting callouts.
- Consider adopting MkDocs (Material theme) or similar static site tooling later; initial draft can live as Markdown in repo.

## Style and maintenance guidelines
- Lead with a summary and task checklist before diving into details; keep steps numbered for easy tracking during incidents.
- Surface environment variable names, defaults, and impact in tables; call out when changes require a restart.
- Use consistent terminology from the glossary; link to reference pages instead of re-describing concepts.
- Embed validation/verification steps for every procedure (e.g. check `/health`, inspect events, confirm job status).
- Cross-link related guides and runbooks to minimise duplication (e.g. document retention page links to purge runbook).
- During development changes, update affected docs within the same PR; treat `release-notes.md` as part of the release checklist.
