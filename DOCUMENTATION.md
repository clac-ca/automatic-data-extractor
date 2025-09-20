# Documentation strategy

## Purpose
ADE is configuration-driven. Deployments remain stable while configurations evolve, so the documentation must teach every reader how to operate, govern, and change configurations safely. Content must render cleanly in GitHub and within the in-app viewer, giving the same navigation, context, and cross-links in both places.

## Audiences and promises
| Persona | They arrive asking | They leave knowing | Primary entry points |
| --- | --- | --- | --- |
| **Platform administrators** | “How do I install, secure, and keep ADE healthy?” | Local/Docker/Azure Container Apps setup, environment management, backup/restore of `data/`, secret rotation, and supported runbooks. | Root `README.md`, `docs/platform/`, `docs/operations/` |
| **IT architects** | “What system am I approving and how are configurations governed?” | Trust boundaries, auth and SSO model, configuration lifecycle, audit trail expectations, and shared terminology. | `docs/foundation/`, `docs/security/` |
| **Support / configuration managers** | “How do I author, validate, publish, and roll back configurations?” | Configuration concepts, drafting tools, comparison/diff views, validation workflows, promotion/rollback steps, and export/import safety nets. | `docs/configuration/`, `docs/operations/runbooks/` |
| **Data teams** | “How do I integrate with the outputs?” | Auth patterns, APIs, SQL access, file export formats, checksum expectations, and retention rules. | `docs/data-integration/`, `docs/reference/` |
| **End users** | “How do I run my documents through ADE?” | Step-by-step GUI walkthroughs for upload → review → download and the lightweight troubleshooting they can perform. | `docs/user-guide/` |

Every landing page restates prerequisites, required roles/access, and escalation paths so readers immediately know whether they are in the right place.

## Principles
1. **Configuration-first narrative** – Lead with lifecycle states, auditing, testing, and rollback; code internals are secondary.
2. **Persona-first navigation** – Every persona should reach their task-focused guide within two clicks.
3. **Task over theory** – Procedures start with context, list numbered steps, highlight validation checks, and close with rollback or escalation guidance.
4. **Single source of truth** – Reuse the glossary, OpenAPI spec, and schema diagrams instead of duplicating definitions.
5. **Operational boundary** – Troubleshooting covers only supported incidents (storage capacity, Azure Container Apps issues, SSO setup/recovery, admin access recovery, database backup/restore, configuration export/import).
6. **Metadata discipline** – Each guide begins with a Markdown front-matter block: `Audience`, `Goal`, `Prerequisites`, `When to use`, `Validation`, `Escalate to`. This renders well both on GitHub and in-app.

## Documentation architecture
### Surfaces
- **Root `README.md`** – Concise product synopsis, links to the docs hub, local quickstart, glossary pointer, and a “Which persona are you?” card deck.
- **`docs/README.md`** – Documentation home with persona-specific cards (Deploy ADE, Understand the system, Configure document types, Support users, Integrate data). Each card lists the top three guides and related runbooks.
- **README in every folder** – Clarifies the audience, scope, and reading order for that slice of the docs so GitHub browsing and in-app navigation stay aligned.

### Content types
- **Guides** – End-to-end instructions for tasks (e.g., activating a new configuration). Include validation steps and rollback notes.
- **Runbooks** – Incident responses with the structure: _Triggers → Diagnostics → Resolution → Validation → Escalation_. Focused on supported operational issues only.
- **Reference** – Tables, API shapes, CLI commands, environment variable matrices, release notes, and templates that should not duplicate narrative guides.

### Section map
| Location | Primary personas | Core topics | Notes |
| --- | --- | --- | --- |
| `docs/foundation/` | IT architects, platform admins | System overview, architecture diagram, configuration lifecycle summary, glossary surface, data flows, security model boundaries. | Store diagrams under `docs/assets/` (Mermaid + exported PNG). |
| `docs/platform/` | Platform admins | Local quickstart, local development stack, Docker basics, Azure Container Apps deployment, environment variables, secret rotation, upgrade paths, database/document backups. | Include checklist sidebars for preflight and post-deploy validation. |
| `docs/security/` | Platform admins, architects | Auth modes, SSO setup + recovery (including certificate/key rotation), account provisioning CLI, admin allowlist. | Link directly to relevant runbooks. |
| `docs/configuration/` | Support/config managers | Concepts, drafting and cloning, validation/testing options, publishing/activation workflow, rollback recipes, diff/history tooling, export/import, change approval checklist. | Emphasise safe iteration and audit logging. |
| `docs/user-guide/` | End users, support | Uploading documents, monitoring jobs, reviewing outputs, downloading exports, light UI troubleshooting, when to contact support. | Add screenshots or short clips when the frontend stabilises. |
| `docs/data-integration/` | Data teams | Auth patterns, REST API usage, job payload schema, SQL queries, webhooks/automation, data retention guidance. | Reference API schema and checksum practices instead of re-describing fields. |
| `docs/operations/` | Platform admins, support | Monitoring (health endpoint, logs), document retention, job queue expectations, account/session management, scheduler status checks. | Houses links to runbooks and recurring operational checklists. |
| `docs/operations/runbooks/` | Platform admins, support | Storage capacity exhaustion, Azure Container Apps outage recovery, SSO outage/setup recovery, admin access recovery, database backup & restore, configuration export/import, configuration promotion rollback verification. | Each runbook includes sample commands and when to escalate. |
| `docs/reference/` | All personas | Environment variables, CLI quick reference, database schema ERD, release notes, change-control checklist, configuration payload schema. | Keep tables synced with source files via automation when possible. |
| `docs/assets/` | Doc authors | Architecture diagrams, workflow charts, UI screenshots. | Track usage in a simple index to avoid stale assets. |

## Persona navigation guides
### Platform administrators
- **Start**: Root `README.md` → `docs/README.md` → `docs/platform/README.md`.
- **Essential guides**: `quickstart-local.md`, `local-development.md`, `docker-compose.md`, `azure-container-apps.md`, `environment-management.md`, `upgrade-paths.md`.
- **Runbooks**: Storage capacity, Azure Container Apps stability, SSO recovery, admin access recovery, database backup/restore, configuration export/import.
- **Success state**: They can deploy ADE in their environment, manage secrets, back up `data/`, restore service after supported incidents, and know when to escalate.

### IT architects
- **Start**: `docs/foundation/README.md` and `docs/security/README.md`.
- **Essential guides**: `system-overview.md`, `architecture.md`, `configuration-model.md`, `security-boundaries.md`, `glossary.md`.
- **Success state**: They understand how ADE enforces deterministic runs, where data lives, how authentication works, and what controls protect configurations.

### Support teams / configuration managers
- **Start**: `docs/configuration/README.md`.
- **Essential guides**: `concepts.md`, `authoring-guide.md`, `validation-and-testing.md`, `publishing-and-rollback.md`, `diff-and-history.md`, `import-export.md`.
- **Runbooks**: Configuration export/import, rollback checklist (linked from publishing guide), failed validation escalation, publishing freeze procedures.
- **Success state**: They can create drafts, validate changes, promote safely, roll back, compare revisions, and maintain audit-ready notes without touching code.

### Data teams
- **Start**: `docs/data-integration/README.md`.
- **Essential guides**: `api-overview.md`, `authentication-recipes.md`, `job-payloads.md`, `sql-access.md`, `data-export.md`.
- **References**: Environment variables affecting outputs, CLI recipes, release notes, checksum/retention commitments.
- **Success state**: They integrate via API/SQL, automate ingestion, and understand how configuration changes might affect downstream systems.

### End users
- **Start**: `docs/user-guide/README.md`.
- **Essential guides**: `upload-and-queue.md`, `monitor-and-review.md`, `download-and-share.md`, `troubleshooting.md`.
- **Success state**: They complete the upload → review → download workflow confidently and know when to involve support.

## Immediate build queue
1. **Orientation layer** – Refresh the root `README.md`, create `docs/README.md`, and seed `docs/foundation/README.md` with a digestible system overview and glossary links.
2. **Platform and security essentials** – Draft `docs/platform/quickstart-local.md`, `docs/platform/local-development.md`, `docs/platform/azure-container-apps.md`, `docs/platform/environment-management.md`, and `docs/security/authentication-modes.md` plus `docs/security/sso-setup.md` (with recovery steps).
3. **Configuration lifecycle core** – Author `docs/configuration/README.md`, `concepts.md`, `authoring-guide.md`, `validation-and-testing.md`, `publishing-and-rollback.md`, and `import-export.md` to give support teams the full workflow.
4. **Operational runbooks** – Produce `runbooks/storage-capacity.md`, `runbooks/azure-container-apps.md`, `runbooks/sso-recovery.md`, `runbooks/admin-access-recovery.md`, and `runbooks/database-backup-restore.md` (including export/import guidance).
5. **End-user workflows** – Draft `docs/user-guide/upload-and-queue.md` and `docs/user-guide/monitor-and-review.md`, leaving clear TODOs for screenshots.
6. **Integration baseline** – Outline `docs/data-integration/api-overview.md` and `docs/reference/environment-variables.md` so data teams have an initial contract.

## Migration and reuse
- `docs/authentication.md` → `docs/security/README.md` (overview) plus `authentication-modes.md` (mode matrix) and `sso-setup.md` (setup + recovery instructions).
- `docs/configuration_lifecycle.md` → `docs/configuration/concepts.md`, `publishing-and-rollback.md`, and `diff-and-history.md`, referenced from the configuration README.
- `docs/document_retention_and_deletion.md` → `docs/operations/document-retention.md` with pointers from storage and backup runbooks.
- `ADE_GLOSSARY.md` → surfaced as `docs/foundation/glossary.md` or transcluded directly, with links from every section.
- Existing diagrams or future assets → relocate to `docs/assets/` with usage notes in a simple index (`docs/assets/README.md`).

## Maintenance guardrails
- Update metadata blocks whenever steps or prerequisites change; record the “Last validated” date.
- Add validation checks (health endpoint call, sample job run, audit log review) at the end of every guide and runbook.
- Reflect configuration or behavioural changes in `docs/reference/release-notes.md` and cross-link affected guides.
- Prefer relative links and glossary references over duplicating explanations.
- Assign section owners and review quarterly or after major releases; document the review in the metadata block to keep in-app readers confident the guidance is current.

This structure keeps each persona focused on configuration-driven operations, delivers consistent navigation in GitHub and the in-app viewer, and ensures the most critical operational and configuration workflows are documented first.
