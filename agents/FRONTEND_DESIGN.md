# ADE Frontend Design Document

Use this document as the authoritative spec for ADE's web client. When
behaviour drifts, edit the text before shipping code.

## 1. Mission
- Define the UI contract across authentication, workspace navigation, and
  document configuration.
- Provide ticket-ready direction so engineers or AI agents can execute without
  side conversations.
- Stage future concepts in §12 until the entire flow is deliverable.

## 2. Product Snapshot
ADE (Automatic Data Extractor) turns semi-structured spreadsheets and PDFs into
clean, auditable tables. The frontend is the operator console: it exposes
configuration controls, system status, and audit evidence for internal teams
that prioritise clarity and accountability over sheer throughput.

## 3. Personas
- **Operations Lead** — Monitors queue health, resolves errors, confirms volume.
- **Configuration Specialist** — Edits extraction rules, manages revisions, and
  publishes changes per document type.
- **Auditor / Reviewer** — Audits outcomes and configuration history with
  read-only access.

## 4. Success Metrics
- **State clarity** — Each surface must declare current progress, next action,
  or resolution.
- **Audit in two clicks** — From any document, reach "what changed, when, and by
  whom" within two interactions.
- **Role-fit control** — Specialists get edit levers; reviewers stay on a guided
  read-only path.

## 5. Design Tenets (Jobs Playbook)
- Ship one decision per screen; remove elements that slow it down.
- Speak plainly; headings stay under three words and buttons state the verb
  (for example, `Publish configuration`).
- Keep the chrome invisible; neutral background, single accent colour, generous
  whitespace, one primary CTA.
- Guard mental models; never mix configuration editing with monitoring or
  history, and confirm before switching contexts.
- Release whole flows only; park partial concepts in §12.

## 6. Release Scope
**MVP surfaces**
1. Authentication loop (`/login` credentials, optional SSO, redirect into the
   workspace shell).
2. Workspace shell listing accessible workspaces and summarising document
   types.
3. Document type detail view with status strip and configuration drawer.

**Queued next (hold for later)**
- Analytics and history views for deep dives.
- Bulk ingestion tooling.
- Advanced filtering, tagging, and saved views.

## 7. Experience Map
### 7.1 Routes
- `/login` — Public authentication surface.
- `/workspaces/:workspaceId` — Default authenticated landing experience.
- `/workspaces/:workspaceId/document-types/:documentTypeId` — Document type
  detail rendered inside the workspace shell.

### 7.2 Layout and Navigation
- Keep the top bar slim: product logo, workspace selector, user menu, backend
  connectivity indicator.
- Run a vertical rail with workspaces first, document types second. Collapse it
  into a slide-in panel below 1024 px width.
- Present the active document type in the right pane; maintain breadcrumbs
  (`Workspace / Document Type`) across breakpoints.
- Provide a command palette shortcut (`Ctrl+K` / `Cmd+K`) that searches the same
  data set as the rail.

## 8. Screen Specifications
### 8.1 `/login`
- **Inputs** — Email and password fields with labels and inline validation.
- **Errors** — Top-level summary with `aria-live="assertive"` that repeats the
  inline messages (for example, "Check your email address").
- **Success path** — Persist the auth token once, hydrate TanStack Query with
  `/me`, redirect to the preferred workspace.
- **Force SSO** — When `/auth/providers.force_sso` is true, suppress the
  credential form and show a single SSO CTA plus a "Need help?" mailto link.
- **SSO providers** — Render tiles only when discovery returns entries; respect
  backend order, use supplied labels/icons, show a neutral skeleton while
  loading. Log discovery failures and fall back to credentials unless forced SSO
  applies.

### 8.2 `/workspaces/:workspaceId`
- **Workspace selection** — Default to `preferred_workspace_id` from `/me`,
  otherwise use the first entry from `/workspaces`.
- **Hero metric** — Display `documents_processed_7d` beneath the workspace
  title with a sparkline and SLA breach badge.
- **Navigation** — Rail lists workspaces then document types; no nested
  accordions or tabs. Persist the last selection in `localStorage`.
- **Filters** — Offer quick filters (Healthy, Attention, Error) only when backed
  by real aggregates.

### 8.3 Document Type Detail
- **Status strip** — Surface "Last run", "Success", and "In queue" using
  `last_run_at`, `success_rate_7d`, and `pending_jobs`.
- **Primary actions** — `Review configuration` as the main CTA; `View history`
  as the secondary link (routes to analytics when available).
- **Context panels** — Summaries for active configuration (version, published
  by/at), sample documents processed this week (count plus viewer link when
  ready), and recent alerts tied to the document type.

### 8.4 Configuration Drawer
- **Structure** — Right-anchored drawer that traps focus until closed.
- **Sections** — `Overview` (name, description, version metadata, publish
  status), `Inputs` (structured editor with inline validation), `Publishing`
  (draft/live toggle, revision notes, `Publish` and `Save draft` buttons).
- **Revision context** — Show breadcrumbs such as `v12 • Published by Dana •
  2025-03-04`.
- **Exit handling** — Provide a `Done` button that returns focus to its trigger
  and confirm before discarding unsaved changes.

## 9. Data Contracts and Dependencies
- `/auth/providers` → `providers: List[Provider]` (`id`, `label`, `icon_url`,
  `start_url`) and `force_sso: bool`.
- `/me` → user profile including `preferred_workspace_id` and permissions.
- `/workspaces` → each workspace returns `id`, `name`, `documents_processed_7d`,
  `sla_breach: bool`, and `document_types: List[DocumentTypeSummary]`.
- `DocumentTypeSummary` → `id`, `display_name`, `status`,
  `active_configuration_id`, `last_run_at`, `success_rate_7d`, `pending_jobs`,
  `sample_documents_week`, `recent_alerts`.
- `/configurations/:id` → `version`, `published_by`, `published_at`, `draft`,
  input schema, and revision notes.

## 10. Accessibility and Telemetry
- Guarantee keyboard access with visible focus states; drawers trap focus via
  ARIA attributes and release on close.
- Use `aria-live="assertive"` for error summaries and `aria-describedby` to bind
  inline errors to their controls.
- Emit telemetry for login success/failure, SSO provider choice, workspace
  switch, document type selection, configuration publish/save, and drawer
  abandonment.

## 11. Implementation Guardrails
- Let TanStack Query own server state; avoid duplicate caches and invalidate
  queries after mutations.
- Persist only workspace and document selections in `localStorage`.
- Use React Router for routing and deep linking.
- Style with CSS Modules or Tailwind, but define tokens for the accent colour
  and spacing scale.

## 12. Deferred Features (Do Not Build Yet)
- Analytics/history pages with comparisons and timelines.
- Document upload tooling, bulk retry flows, and advanced filtering.
- Multi-tenant admin controls and role management UI.

Keep this document synchronised with backend capabilities. When the plan
changes, revise the relevant section and flag downstream impacts before
starting new work.
