---
Audience: Product design, Frontend engineering, Product management
Goal: Capture the ADE experience and implementation blueprint so the team can deliver an intuitive, rigorous UI that mirrors the backend’s deterministic model.
Prerequisites: Familiarity with ADE document types, configurations, callables, execution lifecycle, and glossary terms.
When to use: During discovery, journey mapping, architecture planning, estimation, and onboarding of new contributors (human or AI).
Validation: Prototype flows against `backend/app/routes/` contracts; usability-test key journeys before build milestone gates.
Escalate to: Head of Product Design when experience changes impact accessibility, compliance, or core workflows.
---

# ADE frontend master blueprint

Great products feel inevitable. This document distils ADE’s product truths, articulates the end-to-end user journey, and decomposes the UI and frontend architecture so designers and engineers can craft an experience that feels effortless while staying maintainable.

---

## 0. Product truths & design posture

**Why ADE exists**
- Turn messy spreadsheets/PDFs into trustworthy tables **without** opaque automation.
- Give operations teams confidence to iterate, compare, and promote logic safely.

**First principles**
1. **Clarity beats cleverness** – every surface must declare “what am I looking at?” before introducing controls.
2. **Progress with reassurance** – users always know what changed, what’s running, and how to undo it.
3. **Craft for iteration** – testing and comparison should be the happy path, not an advanced feature.

**Experience anti-goals**
- Avoid dense data dumps without context; every table needs framing copy and actionable next steps.
- Never hide destructive actions behind ambiguous icons; clarity > minimalism when stakes are high.
- Resist modal overload—prefer inline rails/drawers so users maintain spatial orientation.

**Personas anchoring decisions**
- **Operations Lead** – governance, approvals, adoption metrics.
- **Configuration Engineer** – scripting, debugging, rapid iteration.
- **Reviewer / Analyst** – uploading docs, validating, comparing results.

---

## 1. Conceptual hierarchy & mental model reinforcement

```
Workspace (tenant)
└── Document Type (stable container for configurations)
    └── Configuration (versioned; one active at a time)
        └── Column (metadata + callable scripts)
            ├── Detection callable (required)
            ├── Validation callable (optional)
            └── Transformation callable (optional)
└── Run (executes one or more configurations on uploaded docs)
```

**State vocabulary**
- Configuration: Draft → Published → Active → Retired.
- Column: Ready → Needs Attention (missing callable, failing tests, deprecated).
- Run: Queued → Running → Validating → Complete / Failed.

Document types themselves do **not** have a lifecycle—they are logical containers. Use configuration-level flags (e.g., `needsApproval`, `awaitingSamples`) alongside the state machine above when governance cues are required without inventing extra states.

**UI cues**
- Breadcrumbs show the hierarchy explicitly (`Workspace / Invoice / Config v3 / Column: Due Date`).
- Status chips reuse consistent colours across lists, detail views, and comparison matrices.
- Metadata rails reveal lineage (who activated, when, diff summary) to maintain auditability.

---

## 2. Experience map: first login to mastery

Each stage below lists the ideal user experience **and** the implementation hooks required to realise it.

### 2.1 Login & trust handshake
- **Experience**: Minimal SSO/magic-link pane that routes directly into a focused onboarding checklist. Reserve the “How ADE works” narrative for an optional help link so first-use isn’t cluttered.
- **Implementation**: Reuse backend auth endpoints; prefetch workspace summary post-login so the checklist can render instantly with contextual first task (“Create your first configuration”).

### 2.2 Home zero state
- **Experience**: Checklist-driven guidance spelling out the core loop (“Create type → Add configuration → Upload → Run”). Optional tips stay collapsed until the user asks for them; the command palette tutorial triggers via `?` only after the first task is complete.
- **Implementation**: `GET /workspace/summary` powers checklist state; local storage records dismissed tips; analytics logs first checklist completion for onboarding health.

### 2.3 Create first document type
- **Experience**: Three-step wizard (**Basics → Column blueprint → Review**) that feels lightweight yet guides schema creation.
- **Implementation**: Wizard state machine (XState) ensures validation per step; optional CSV import seeds columns; final step shows backend payload preview for transparency.

### 2.4 Land on document type overview
- **Experience**: Hero card confirming creation, call-to-action “Start first configuration”, tabs previewing future data.
- **Implementation**: Skeleton loaders align with future data grid; optimistic routing to configuration workspace seeds React Query caches.

### 2.5 Build first configuration
- **Experience**: Draft workspace opens with seeded columns, inline education about detection/validation/transformation, autosave reassurance.
- **Implementation**: Monaco editor loaded lazily; autosave throttled (5s) to PATCH draft endpoint; surface a lightweight “unsaved changes” summary instead of full change logs (defer granular history to later releases).

### 2.6 Column scripting & testing
- **Experience**: Selecting column opens right rail with Monaco editors, optional panels collapsed by default, universal **Test callable** button (⌘↵) running against selected sample docs.
- **Implementation**: Run tests via `POST /configurations/{id}/test` with payload identifying callable type + sample document ID; streaming output displayed in log panel. Callables are owned per column and snapshotted when the configuration is published, so persist only the last successful run plus the current run per column (keep broader history on the backlog).

### 2.7 Pre-activation validation
- **Experience**: “Review readiness” card summarises missing callables, failing tests, schema conflicts; once resolved, “Publish configuration” reveals diff vs. current active version with schema diff surfaced first.
- **Implementation**: Frontend validator mirrors backend constraints; publish/activate modal always fetches schema and callable diffs and prevents promotion if backend fails preflight or flags (e.g., `needsApproval`) remain unresolved.

### 2.8 Upload & run
- **Experience**: Upload console defaults to the latest published configuration, with a simple toggle to add the active config or other published versions (max three total) using colour-coded pills; resilient queue with per-file statuses.
- **Implementation**: Drag-and-drop component with resumable uploads; multi-select limited by schema compatibility; WebSocket channel streams run updates; refresh resilience via run ID stored in URL params.

### 2.9 Review results & iterate
- **Experience**: Completion toast linking to table and comparison views; validation issues surfaced first; comparison matrix highlights changed cells and validation deltas.
- **Implementation**: `GET /runs/{id}/results` returns normalized data for table + diff; virtualization handles large tables; colour palette from config selection reused for diff highlights.

### 2.10 Ongoing mastery
- **Experience**: Activity feeds, keyboard shortcuts, help centre, and comparison snapshots support continuous improvement.
- **Implementation**: Presence via WebSocket heartbeat; shareable snapshot tokens expire after configurable TTL; keyboard map documented and enforced through `@floating-ui` menus.

### 2.11 Experience heuristics & failure-mode mitigations
- **Guidance debt**: If a user lands on an empty state more than twice, escalate help from inline copy → interactive walkthrough.
- **Confidence gaps**: Whenever a destructive or schema-impacting action occurs, show preview diff and require typed confirmation if downstream runs could be affected.
- **Latency tolerance**: Loading indicators should communicate cause (“Fetching column scripts…”) and offer fallback navigation after 10 s.
- **Draft abandonment**: Send weekly reminder email for drafts untouched for seven days with direct link into the workspace and snapshot of outstanding tasks.
- **Role confusion**: Role-based prompts clarify capabilities (view vs. edit) and direct read-only users to request access without dead ends.

---

## 3. Primary surfaces (jobs, treatments, states)

| Surface | Primary jobs-to-be-done | Key treatments | Critical states |
| --- | --- | --- | --- |
| **Home** | Understand status, finish onboarding, jump back into recent work | Checklist, recent activity, spotlight metrics, “What’s new” card | Empty workspace, partial onboarding, active runs |
| **Document Type Library** | Browse, search, and manage document types | Data grid with owner/tag filters, inline quick actions | Empty, filtered-no-results, bulk select |
| **Document Type Detail** | Monitor health, inspect lineage, manage configs & samples | Overview hero, tabs (Overview/Configurations/Activity/Samples), metadata rail | Highlight latest active config, outstanding drafts, missing samples, failing health |
| **Configuration Workspace** | Author, test, and prepare versions | Header with breadcrumbs + status chips, column grid, right rail editors, lightweight change summary | Draft, Published awaiting activation, flagged (needsApproval), collaborative editing |
| **Upload & Run Console** | Queue documents, select configs, watch progress | Upload dropzone, run summary cards, configuration multi-select, live log panel | Idle, uploading, paused network, failed run |
| **Results & Comparison Center** | Validate outputs, compare versions, take action | Column diff matrix, table viewer, validation issue stack, CTA row (promote, rerun, annotate) | No diff, validation failures, schema mismatch |

Each surface should ship with documented empty/loading/error states and instrumentation events.

### 3.1 Home blueprint
- **Layout**: Left column for onboarding checklist & recent work, right insight rail for metrics (active configs, success rate) and alerts.
- **Orientation**: Welcome banner collapses after first run; command palette tip anchored beside global search; zero-state illustrations reinforce action.
- **Implementation**: Checklist items derived from workspace summary; metrics cards query aggregated run stats; alerts fetch from notification feed.

### 3.2 Document type library & detail
- **Library grid**: Column headers (Name, Owner, Last Run, Active Config, Health). Quick actions appear on hover (Open, Duplicate, Archive).
- **Filtering**: Saved views for owner/team; tag chips support multi-select AND/OR logic.
- **Detail page**: Sticky header with type metadata and CTA; tab content loads lazily; activity timeline groups events by day with inline diffs for publishes/activations.
- **Implementation**: Grid virtualization for 100+ types; detail tabs share cached config data; activity timeline consumes audit log endpoint with pagination.

### 3.3 Configuration workspace deep layout
- **Header**: Breadcrumbs, status chip, autosave indicator, primary actions (Test entire configuration, Review readiness, Publish/Activate when eligible).
- **Canvas**: Column grid occupying central area; right rail toggled for script editing; lightweight change summary panel sits below editors (full history and diff viewer reserved for later iterations).
- **Focus management**: Keyboard navigation highlights row + opens right rail; command palette exposes “Jump to validation errors”.
- **Implementation**: Column grid built on accessible table semantics; right rail is resizable; autosave status derived from mutation promises.

### 3.4 Upload & run console specifics
- **Run builder**: Stepper across top (Upload → Configure → Review → Monitor) with ability to revisit previous steps before submission.
- **Document list**: File cards show size, tags, detection status, per-file logs; bulk actions to remove/retry.
- **Monitoring**: Live log panel supports filters (All / Warnings / Errors) and persists collapse state across sessions.
- **Implementation**: File uploads chunked with backoff; progress timeline mapped to backend state machine; logs delivered via WebSocket channel with reconnection logic.

### 3.5 Results & comparison center layout
- **Summary header**: Diff outcome badges (“12 columns unchanged, 3 changed, 1 failed validation”), run metadata, quick toggles for showing only changes/failures.
- **Dual-view**: Table view with column toggles; diff matrix pinned to left for quick scanning. Row click reveals panel with raw extraction, validation messages, script metadata.
- **Call-to-actions**: Promote, create follow-up ticket, rerun with adjustments; share snapshot button generates short-lived link.
- **Implementation**: Diff matrix relies on memoized selectors; snapshot creation triggers backend share-token endpoint; CTA availability based on role + config state.

### 3.6 North-star user narratives
- **First-time success**: New configuration engineer guided from zero state to first activated configuration within one session, with checklists updating in real time and contextual docs at every step.
- **Operational triage**: Reviewer receives alert about validation failures, jumps directly to affected run, filters diff matrix to failing columns, and exports annotated report for stakeholders in <5 minutes.
- **Continuous improvement**: Ops lead explores analytics on comparison frequency, reviews publish diff insights, and schedules targeted regression runs, all within a cohesive dashboard experience.

---

## 4. Navigation, layout, and orientation grammar

- **Global shell**: 240 px left rail (Home, Document Types, Upload & Run, Results, future Monitoring/Admin), 64 px top bar (env switcher, global search, notifications, help), command palette (⇧⌘K / ⇧Ctrl+K) for omnibox navigation.
- **Responsive grid**: Desktop 12-column grid (8-column work canvas + 4-column insight rail), tablet collapses rails into drawers, mobile stacks cards with sticky primary actions.
- **Orientation zone**: Top 25 % reserved for page title, breadcrumbs, status chips, key metrics; primary actions right-aligned with destructive options separated visually.
- **Progressive disclosure**: Tooltips/badges in lists, expanded metadata in rails/drawers/modals to keep main canvas focused.

---

## 5. Column authoring & testing deep dive

**Selection model**
- Column grid supports keyboard navigation, multi-select for bulk actions (duplicate, mark optional, reorder via drag handles).
- Callables are scoped per column and snapshotted at publish—there’s no shared callable library to manage in the workspace.

**Right rail structure**
1. Column summary (description, data type, nullability, tags).
2. Detection editor (required) with linting + snippet gallery.
3. Validation panel (optional) collapsed but surfaced when failing tests.
4. Transformation panel (optional) with preview toggle.
5. Inline test panel surfaces the current run alongside the last successful result (pinning full histories is deferred).

**Test callable experience**
- Single button chooses callable scope based on focused panel; advanced dropdown for “Run detection+transformation pipeline”.
- Test execution overlay shows spinner with expected duration; results include stdout, structured return value, and line-highlighted errors.
- Last successful output persists to guide future edits; offer quick compare vs. the last published callable snapshot (full change log comes later).

**Implementation hooks**
- Monaco configured with Python language server, inline diagnostics from backend lint endpoint.
- Publish modal provides the authoritative script/schema diff; inline editor simply references “Last published” for context to keep the workspace lean.
- Local cache of unsaved edits to handle offline/resume scenarios.

**Edge-case choreography**
- Empty script slots show “Start with template” shortcuts seeded from common detection/validation scenarios.
- When backend linting fails, surface actionable message with link to docs and highlight offending lines; do not dismiss until user confirms understanding.
- Guard against simultaneous edits by prompting users to pull latest changes; advanced merge tooling can wait for future releases.
- Offer AI-assisted snippet generator (future) with explicit review checklist to keep accountability clear.

---

## 6. Multi-configuration selection & comparison mechanics

**Selection guardrails**
- Default to the latest published configuration (which is often the active one); optional “Compare additional configurations” toggle reveals searchable list limited to three selections.
- Disabled options show tooltip reason (schema mismatch, retired, already selected).

**Visual language**
- Each selected configuration receives a colour-coded pill (unique accent). The colour persists from selection → run summary → results diff for cognitive continuity.

**Comparison view**
- Matrix rows = output columns; columns = configurations.
- Cell states: identical (neutral), value diff (highlight), validation failure (warning), missing data (striped placeholder).
- Side-by-side script diff references published snapshots for columns with changed callables.

**Implementation**
- React Query query composes `GET /runs/{id}/comparison` data; virtualization ensures performance for 100+ columns.
- Diff calculations handled in web worker to keep UI responsive.
- Promote/activate actions check backend gating (only Draft or Published configs promotable).

**Scenarios to design for**
- **Quick sanity check**: Analyst runs active vs. draft configuration; diff view defaults to “Show changes only”.
- **Schema verification**: Publish modal already surfaces schema diff; comparison view reinforces column-level mismatches with grouped callouts.
- **Backlog**: Timeline overlays, regression hunt analytics, and deeper run metrics are explicitly deferred until the core workflow feels effortless.

**Interaction guardrails**
- Persist comparison selections in URL so recipients land in identical view.
- Provide “Clear selections” action to recover quickly from overwhelming comparisons.
- Warn when comparing configurations using different callable runtimes or dependencies, linking to release notes.

---

## 7. Upload & run execution flow

1. **Queue documents** – Drag-and-drop with file type validation, manual select fallback, inline metadata editing (tags, notes).
2. **Choose configurations** – Latest published config preselected; multi-select as above; warning banner if mixing versions with incompatible schemas.
3. **Run summary** – Card summarizing configs chosen, expected duration, last run status.
4. **Progress tracking** – Timeline reflecting backend state machine; live logs collapsible; per-file cards show detection/validation progression.
5. **Completion** – Toast linking to results/comparison; queue retains run history for quick reruns.

**Resilience features**
- Run ID pinned to URL for reconnection.
- Background queue persists in IndexedDB for recoverability if page closes mid-upload.
- Graceful handling of partial failures (retry single document, fallback to previous active config).

**Operational analytics**
- Track average run duration by configuration and highlight anomalies directly within run summary card.
- Capture per-file failure reasons to inform training data improvements; expose download for support team.
- Instrument “Test callable” frequency vs. production run failures to validate editor efficacy.

**Edge cases**
- If upload queue detects incompatible file format, surface remediation (download template, contact support) rather than silent drop.
- For extremely large documents, display estimated processing time sourced from backend heuristics and allow user to reprioritise queue order.
- When network disconnects mid-run, pause UI timers, show offline banner, and resume once connection restored.

---

## 8. Interaction patterns & micro-interactions

- **Autosave & undo**: Draft changes autosave every 5 s (debounced) and on blur; provide quick undo to the last autosave or last published snapshot (full per-field history is future scope).
- **Guided discovery**: Contextual coach marks retire after two dismissals; help icon opens side-panel docs instead of new tab to maintain focus.
- **Keyboard coverage**: Tab order mirrors visual layout; grid navigation with arrows/home/end; command palette exposes high-value actions (“Create configuration”, “Test callable”).
- **Empty & loading states**: Skeleton placeholders maintain structure; friendly illustrations lighten zero-data screens; instructive copy clarifies next action.
- **Notification tiers**: Inline banners for blocking errors, toasts for transient successes, notification inbox for system-wide alerts.
- **Presence & collaboration**: Avatar stack indicates collaborators editing same configuration; soft locks prevent overwriting without blocking view-only access.

---

## 9. Accessibility, responsiveness, and performance commitments

- **WCAG 2.1 AA**: 4.5:1 contrast, focus outlines, skip links, ARIA roles for grids/editors, accessible command palette fallback (Ctrl+/).
- **Assistive support**: Screen readers announce column position within grids; editors expose lint errors via ARIA live regions; voice-over friendly tooltips. Validate Monaco focus management and screen reader hints with early usability passes because this is a known risk area.
- **Responsive design**: Down to 1024 px tablets and 768 px mobile; tables pivot to card stacks with disclosure drawers; sticky action bars keep primary controls reachable.
- **Performance**: Code-split Monaco, diff views, and comparison matrix; prefetch configuration metadata on hover; throttle WebSocket log rendering; use IntersectionObserver to lazily load heavy panels.

---

## 10. Frontend architecture & maintainability blueprint

**Tech stack (assumed)**
- React + TypeScript + Vite (Next.js optional if SSR/SEO required).
- React Router for routing, React Query for server state, Zustand or XState for complex local flows (wizard, comparison selection).
- Monaco editor for Python callables with custom workers for linting and completion.

**Backbone first**
- Prioritise Configuration grid + right rail editing, inline callable testing, and the comparison workbench before investing in activity feeds, presence, or advanced analytics.
- Keep change-tracking simple in MVP—lean on publish snapshots and schema diff modals rather than bespoke history systems.

**Suggested directory structure**
```
frontend/
└─ src/
   ├─ app/                # Routes, layout shells, loaders
   ├─ features/
   │  ├─ document-types/
   │  ├─ configurations/
   │  ├─ runs/
   │  └─ comparisons/
   ├─ components/         # Shared primitives (Button, Input, Card, Modal)
   ├─ design/             # Tokens, typography, theme utilities
   ├─ lib/                # API client, error boundaries, formatters
   ├─ state/              # Zustand stores or state machines
   ├─ services/           # Command palette, analytics, feature flags
   ├─ test-utils/
   └─ main.tsx
```

**Design system foundations**
- Token scales: spacing (4 px base, multiples), typography (rem-based with clamp), colour roles (primary, success, warning, neutral, comparison accents).
- Component library built with headless primitives (e.g., Radix UI) and custom styling to ensure accessibility.
- Theme file exports CSS variables consumed by both application shell and Monaco editor for visual cohesion.

**API discipline**
- HTTP client in `lib/apiClient.ts` with typed helpers (e.g., `getDocumentTypes`, `saveConfigurationDraft`, `testCallable`, `runComparison`).
- React Query cache keys namespaced by entity ID + version; invalidations triggered after promotions or run completions.
- Mutations return normalized data to keep derived state deterministic; optimistic updates only where rollback is trivial (naming, descriptions).

**Component layering**
- **Primitives** (Buttons, Inputs, Tabs, Dialogs) expose consistent props and support full keyboard handling.
- **Compound components** (ColumnGrid, ScriptEditor, ComparisonMatrix) compose primitives and encapsulate data fetching boundaries.
- **Feature shells** orchestrate view state, analytics events, and error boundaries; they should remain thin and declarative.

**State management contracts**
- Wizard/coach-mark flows handled via state machines to avoid ad-hoc boolean flags.
- Local draft state separated from server snapshots; when conflicts arise prompt users to reload or duplicate—full diffing can wait for future tooling.
- Comparison selections stored in URL query params for shareable states.

**Documentation & governance**
- Each feature directory houses README describing data flow, critical states, and testing strategy.
- Prop-level Storybook docs double as living spec; chromatic regression ensures layout stability across iterations.
- Adoption checklist for new contributors covers lint rules, analytics events, accessibility expectations, and error-handling conventions.

**Testing strategy**
- Vitest + Testing Library for unit/interaction tests.
- Contract tests verifying behaviour against mocked backend schemas (missing optional scripts, validation failures, schema mismatches).
- Playwright smoke flows: first login → create document type → build configuration → run comparison.
- Storybook with accessibility and visual regression add-ons to lock styling.

**Maintainability guardrails**
- Design tokens centralised; theme switch (light/dark) syncs with Monaco theme.
- Feature flags wrap emerging capabilities (multi-config comparison, script catalog).
- Observability via analytics events (onboarding completion, test callable usage, comparison frequency).
- Link UI help to anchors in `DOCUMENTATION.md` for language consistency.

---

## 11. Implementation roadmap (how we make it real)

1. **Foundation sprint**
   - Scaffold frontend project, design tokens, global shell, authentication integration.
   - Ship Home zero state with checklist fed by workspace summary endpoint.
2. **Document Type core**
   - Build library grid, creation wizard (Basics → Columns → Review), and detail overview.
   - Implement React Query caches and activity feed stubs.
3. **Configuration workspace**
   - Column grid + right rail skeleton; integrate Monaco; autosave + lightweight change summary; inline test plumbing.
   - Deliver validation readiness checker and publish/activate modal with required schema diff.
4. **Upload & run console**
   - Drag-and-drop uploads, resumable queue, configuration multi-select, WebSocket progress timeline.
5. **Results & comparison center**
   - Table view with virtualization, diff matrix, validation issue stack, promote/revert actions.
6. **Collaboration & polish**
   - Command palette, keyboard shortcuts, presence indicators, notification inbox, advanced analytics hooks.

Each milestone should include UX reviews, accessibility validation, analytics instrumentation, and documentation updates.

**Milestone definitions of done**
- **Design sign-off**: Figma specs, interaction notes, and accessibility annotations reviewed with design lead.
- **Engineering validation**: Component stories, unit tests, and API mocks merged; performance budget evaluated via Lighthouse/React Profiler snapshots.
- **Product acceptance**: Demo recorded for stakeholders, instrumentation dashboards updated, rollout plan defined (feature flags + changelog copy).

**Risks & mitigations**
- **Complex Monaco integrations** → Spike early with proof-of-concept; wrap editor in isolated component with fallback plain-text mode.
- **WebSocket reliability** → Implement exponential backoff and offline buffering in first release to avoid regressions later.
- **Scope creep on comparison tooling** → Ship baseline diff with clear backlog of advanced analytics to avoid delaying MVP.
- **Cross-team alignment** → Weekly design/dev sync with shared status doc; update `CURRENT_TASK.md` to keep AI contributors synchronized.

---

## 12. Quality, security, and support scaffolding

- **Instrumentation**: Start with time-to-first-run, test callable usage, and publish/activation success rate. Layer in comparison diffs resolved and rerun frequency once the core loop proves stable.
- **Security**: Enforce role-based access on edit vs. view actions; scrub sensitive payloads from client-side logs; use secure storage for auth tokens.
- **Error handling**: Inline stack traces trimmed and linked to docs; results view offers “Rerun with previous active configuration” fallback.
- **Support**: Floating help beacon exposes contextual docs, keyboard cheat sheet, and support contact; AI assistant surfaces code hints within editors.
- **Recovery**: Version history accessible per configuration; duplication workflow to branch from active config; run history exports for audit teams.

**Operational guardrails**
- Error budget: aim for <1 % failed runs attributable to frontend issues; monitor via Sentry tags referencing UI state.
- Performance SLO: key views (Home, Configuration workspace, Results) interactive under 2.5 s on reference hardware; track using Real User Monitoring.
- Accessibility regression suite executed pre-release; failures block deployment until resolved.
- Production support playbook documents triage steps, escalation paths, and templates for communicating incidents to stakeholders.

---

## 13. Next tangible deliverables

1. Narrative storyboard from first login through first comparison run.
2. Low-fidelity wireframes for Home, Document Type library/detail, Configuration workspace, Upload & Run, Results/Comparison.
3. Component inventory with state diagrams (loading, empty, error) for major UI elements.
4. Prototype of script editor showing inline test execution, diff preview, and error surfacing.
5. API contract review confirming fields for onboarding status, run state machine, comparison diffs, audit logs, and presence.
6. Accessibility plan documenting focus order, keyboard shortcuts, screen reader narratives for grids/editors.

---

This living document should be updated as user insights emerge. Keep revisions versioned so everyone—designers, engineers, AI agents—stays aligned while bringing ADE’s ideal UI to life.
