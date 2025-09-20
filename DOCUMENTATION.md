# Documentation strategy

## Purpose
ADE runs on configurations, not constant code releases. Our documentation must show every reader how to change, review, and operate those configurations safely while keeping deployment and security stories discoverable. All content should render cleanly in GitHub and inside the in-app documentation viewer.

## Personas and promises
| Persona | Arrive asking | Leave knowing | Entry points |
| --- | --- | --- | --- |
| **Platform administrators** | “How do I stand ADE up, secure it, and keep it running?” | Provision paths (local, Docker, Azure Container Apps), secret rotation, backup routines, and recovery runbooks. | `README.md`, `docs/platform/`, `docs/operations/`
| **IT architects** | “What is the system I am approving and how do configs move through it?” | Architecture boundaries, configuration model, audit expectations, and shared vocabulary. | `docs/foundation/`, `docs/security/`
| **Support teams / configuration managers** | “How do I author, validate, publish, and roll back configurations without breaking jobs?” | Configuration lifecycle, testing tools, comparison workflows, and export/import safety nets. | `docs/configuration/`, `docs/operations/runbooks/`
| **Data teams** | “How do I integrate programmatically and consume normalised data?” | Auth patterns, API/SQL usage, payload schemas, and retention rules. | `docs/data-integration/`, `docs/reference/`
| **End users** | “How do I process my documents in the UI?” | Task-focused walkthroughs for uploading, monitoring, reviewing, and downloading results. | `docs/user-guide/`

Each landing page must restate prerequisites, access needed, and who to contact when tasks fail.

## Guiding principles
1. **Configuration-first story** – Explain lifecycle states, auditability, and rollbacks before code internals.
2. **Persona-first navigation** – Keep every reader within two clicks of their tasks by using clear section overviews and cross-links.
3. **Task over theory** – Procedures start with context, then numbered steps, validation checks, and rollback notes.
4. **Single source of truth** – Reuse `ADE_GLOSSARY.md`, OpenAPI exports, and schema diagrams rather than duplicating definitions.
5. **Operational boundary** – Troubleshooting covers supported incidents only (storage limits, Azure Container Apps, SSO, admin access recovery, backups, configuration export/import).

## Navigation blueprint
- **Root `README.md`** – Orientation for new admins: short product synopsis, local quickstart link, documentation hub link, and glossary pointer.
- **`docs/README.md`** – Acts as the documentation home. Present persona cards (Deploy, Understand, Configure, Support Users, Integrate) with direct links to the highest-priority guides and runbooks.
- **Metadata block** – Begin every guide with audience, goal, prerequisites, estimated time, related docs, and last validation date. Keep it Markdown-only for in-app rendering.
- **README per folder** – Offer the section overview, intended personas, and reading order. This supports both GitHub browsing and the in-app menu.

### Section directory
| Section | Primary persona(s) | Stories covered | Notes |
| --- | --- | --- | --- |
| `docs/foundation/` | IT architects, platform admins | System overview, architecture diagrams, configuration model, glossary surface | Keep diagrams in `docs/assets/` (Mermaid + PNG)
| `docs/platform/` | Platform admins | Local/Docker/ACA setup, environment management, upgrades | Includes backup guidance for `var/` volumes and secret rotation
| `docs/security/` | Platform admins, architects | Auth modes, SSO setup + recovery, access management | Highlight compliance expectations and escalation paths
| `docs/configuration/` | Support teams | Concepts, authoring, validation, publishing, rollback, diff/history, automation hooks | Anchor all configuration tooling here; reuse glossary terms
| `docs/user-guide/` | End users, support teams | Upload, monitor, review, download, lightweight UI troubleshooting | Add screenshots when frontend ships
| `docs/data-integration/` | Data teams | API usage, automation recipes, payload schemas, SQL access, export patterns | Reference API schema and checksum practices
| `docs/operations/` | Platform admins, support teams | Monitoring, job operations, document retention, account/session admin | Houses runbooks for supported incidents
| `docs/operations/runbooks/` | Platform admins, support teams | Storage capacity, Azure Container Apps, SSO recovery, admin access recovery, backup/restore, configuration export/import | Each runbook includes triggers, diagnostics, resolution, and escalation
| `docs/reference/` | All personas | Environment variables, CLI tools, database schema, release notes, change-control checklist | Source-of-truth tables and templates
| `docs/assets/` | Authors | Architecture and workflow diagrams | Track which guides embed each asset

## Persona walkthroughs
### Platform administrators
- **Start here**: Root `README.md` → `docs/README.md` → `docs/platform/README.md`.
- **Key guides**: `quickstart-local.md`, `local-development.md`, `azure-container-apps.md`, `environment-management.md`, `upgrade-paths.md`.
- **Runbooks**: Storage capacity, Azure Container Apps health, backup-and-restore, admin access recovery.
- **What success looks like**: They can deploy ADE, rotate secrets, back up `var/`, and recover from supported outages without touching backend code.

### IT architects
- **Start here**: `docs/foundation/system-overview.md` paired with `docs/foundation/architecture.md` and `docs/security/README.md`.
- **Key guides**: `configuration-model.md` for lifecycle insight, `access-management.md` for governance, `glossary.md` for shared language.
- **What success looks like**: They understand trust boundaries, audit trails, and how configuration state flows through the platform.

### Support teams / configuration managers
- **Start here**: `docs/configuration/README.md`.
- **Key guides**: `concepts.md`, `authoring-guide.md`, `validation-and-testing.md`, `publishing-and-rollback.md`, `diff-and-history.md`, `import-export.md`.
- **Runbooks**: Configuration export/import, rollback checklist (in publishing guide), escalation to platform team when tests fail.
- **What success looks like**: They can create, compare, publish, and roll back configurations with documented validations and audit notes.

### Data teams
- **Start here**: `docs/data-integration/README.md`.
- **Key guides**: `api-overview.md`, `automation-recipes.md`, `job-payloads.md`, `sql-access.md`, `data-export.md`.
- **Reference hooks**: Environment variables affecting outputs, CLI tools, release notes.
- **What success looks like**: They automate ingestion, consume outputs deterministically, and respect retention/verification policies.

### End users
- **Start here**: `docs/user-guide/README.md`.
- **Key guides**: `upload-and-queue.md`, `monitor-and-review.md`, `download-and-share.md`, `troubleshooting.md`.
- **What success looks like**: They complete the upload → review → download workflow independently and know when to contact support.

## Immediate build queue
1. **Orientation** – Refresh root `README.md`, write `docs/README.md`, and seed `docs/foundation/README.md` with a concise system overview.
2. **Deployment & security** – Deliver `docs/platform/quickstart-local.md`, `docs/platform/local-development.md`, `docs/platform/azure-container-apps.md`, and split `docs/security/authentication-modes.md` + `docs/security/sso-setup.md` with recovery instructions.
3. **Configuration lifecycle** – Author `docs/configuration/README.md`, `concepts.md`, `authoring-guide.md`, `validation-and-testing.md`, and `publishing-and-rollback.md` so support teams can manage change safely.
4. **End-user workflows** – Draft `docs/user-guide/upload-and-queue.md` and `monitor-and-review.md`; add placeholders for screenshots.
5. **Runbooks** – Create `runbooks/storage-capacity.md`, `runbooks/azure-container-apps.md`, and `runbooks/sso-recovery.md`, each with triggers, diagnostics, resolution, validation, and escalation sections.

Subsequent passes can extend automation recipes, SQL guidance, admin access recovery, backup/restore, and configuration export/import runbooks.

## Existing content migration
- `docs/authentication.md` → `docs/security/README.md` (overview) + `authentication-modes.md` (basic/session/API/CLI) + `sso-setup.md` (OIDC setup, testing, recovery).
- `docs/configuration_lifecycle.md` → `docs/configuration/concepts.md` and `publishing-and-rollback.md`, summarised in `docs/configuration/README.md`.
- `docs/document_retention_and_deletion.md` → `docs/operations/document-retention.md`, linked from `docs/operations/README.md` and the storage runbook.
- `ADE_GLOSSARY.md` → surfaced via `docs/foundation/glossary.md` (import or include) with cross-links.
- Existing diagrams → relocate under `docs/assets/` with references inside relevant guides.

## Maintenance guardrails
- **Front-matter discipline** – Update the metadata block whenever procedures change; include a “Last validated” date.
- **Validation steps** – Close every procedure with checks (health endpoint, sample job, audit log review) so readers know the task finished successfully.
- **Change tracking** – Update affected guides and append entries to `docs/reference/release-notes.md` when configurations, defaults, or operational behaviour shift.
- **Cross-linking** – Prefer relative links to runbooks, glossary terms, and configuration guides instead of duplicating content.
- **Review cadence** – Assign section owners and review quarterly or after major releases; log the review in the metadata block.

This lean structure keeps every persona focused on configuration-driven operations, avoids code-level debugging, and ensures the documentation stays approachable in both GitHub and the in-app viewer.
