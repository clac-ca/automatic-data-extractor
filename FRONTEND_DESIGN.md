# ADE frontend master blueprint

Great products feel inevitable. This living blueprint distils ADE’s product truths, articulates the end-to-end user journey, and decomposes the UI and frontend architecture so designers and engineers can craft an experience that feels effortless while staying maintainable.

---

## 1. Document intent & working agreements

- **Purpose** – Provide a single, opinionated reference for product, design, and frontend implementation decisions. If a question arises about how ADE should feel or behave, this document is the starting point.
- **Scope** – Focused on the web frontend: information architecture, interaction patterns, component strategy, and touchpoints with backend services. Non-UI topics live in the backend and infra plans.
- **Update discipline** – Treat changes like code. Every edit should state *why* the blueprint shifted (new research, metrics, constraints) and remove outdated guidance so ambiguity never lingers.
- **Decision record** – When trade-offs are made (e.g., dropping a wizard step, deferring comparison history), capture the rationale inline so future contributors understand the context.
- **Living loop** – Designers and engineers review this file at the start of each milestone kickoff to confirm it still reflects the desired state. If reality diverges, update the blueprint before shipping more deltas.

---

## 2. Product truths & design posture

### 2.1 Why ADE exists
- Turn messy spreadsheets/PDFs into trustworthy tables **without** opaque automation.
- Give operations teams confidence to iterate, compare, and promote logic safely.

### 2.2 First principles
1. **Clarity beats cleverness** – every surface must declare “what am I looking at?” before introducing controls.
2. **Progress with reassurance** – users always know what changed, what’s running, and how to undo it.
3. **Craft for iteration** – testing and comparison should be the happy path, not an advanced feature.

### 2.3 Experience anti-goals
- Avoid dense data dumps without context; every table needs framing copy and actionable next steps.
- Never hide destructive actions behind ambiguous icons; clarity > minimalism when stakes are high.
- Resist modal overload—prefer inline rails/drawers so users maintain spatial orientation.

### 2.4 Personas anchoring decisions
| Persona | Core needs | Success signal |
| --- | --- | --- |
| **Operations Lead** | Governance, approvals, adoption metrics. | Can review readiness and approve promotions without digging into code. |
| **Configuration Engineer** | Scripting, debugging, rapid iteration. | Can author, test, and publish callables without context switching. |
| **Reviewer / Analyst** | Uploading docs, validating, comparing results. | Can spot regressions and confirm fixes quickly. |

---

## 3. Mental model reinforcement

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

### 3.1 State vocabulary
| Entity | States | Notes |
| --- | --- | --- |
| Configuration | Draft → Published → Active → Retired | Only one Active per Document Type. Promotions always move through Published. |
| Column | Ready ↔ Needs Attention | Needs Attention surfaces missing callables, failing tests, deprecated APIs. |
| Run | Queued → Running → Validating → Complete / Failed | Metadata flags (e.g., `needsApproval`) accompany states but never mutate them. |

Document types do **not** have a lifecycle—they are logical containers. Keep governance metadata scoped to configurations and columns.

### 3.2 UI cues
- Breadcrumbs show the hierarchy explicitly (`Workspace / Invoice / Config v3 / Column: Due Date`).
- Status chips reuse consistent colours across lists, detail views, and comparison matrices.
- Metadata rails reveal lineage (who activated, when, diff summary) to maintain auditability.

---

## 4. End-to-end experience map

Each stage lists the desired user experience, implementation hooks, and instrumentation guardrails. Treat onboarding to mastery as a repeatable loop: orient → configure → validate → run → learn.

### 4.1 Onboard & build trust
- **Experience**: Minimal SSO/magic-link pane routes directly into a focused onboarding checklist. “How ADE works” stays discoverable but out of the way.
- **Implementation**: Reuse backend auth endpoints; prefetch workspace summary post-login so the checklist renders instantly with the contextual first task (“Create your first configuration”).
- **Instrumentation**: Track first-login completions and drop-off per checklist task to refine messaging.

### 4.2 Home zero state
- **Experience**: One checklist spelling out the core loop (“Create type → Add configuration → Upload → Run”) guiding users to a first successful run in under five minutes. Optional tips stay collapsed until requested; the command palette tutorial unlocks after checklist completion and resurfaces contextually later.
- **Implementation**: `GET /workspace/summary` powers checklist state; local storage records dismissed tips; analytics logs first checklist completion for onboarding health.
- **Guardrails**: Empty states must list the *next* safe action (e.g., “Create a document type”) with copy matching backend terminology.

### 4.3 Define a document type
- **Experience**: Lightweight three-step wizard (**Basics → Column blueprint → Review**) guiding schema creation without overwhelming detail.
- **Implementation**: Wizard state machine (XState) enforces per-step validation; optional CSV import seeds columns; final step shows backend payload preview for transparency.
- **Instrumentation**: Capture drop-off per step and validation errors to tune defaults.

### 4.4 Document type overview
- **Experience**: Hero card confirms creation, call-to-action “Start first configuration”, tabs previewing future data and run history.
- **Implementation**: Skeleton loaders align with future data grid; optimistic routing to configuration workspace primes React Query caches.
- **Guardrails**: Provide a dismissible “Next steps” banner until the first configuration is published.

### 4.5 Build the configuration workspace
- **Experience**: Draft workspace opens with seeded columns, inline education about detection/validation/transformation, and autosave reassurance.
- **Implementation**: Monaco editor loads lazily; autosave throttled (5 s) to PATCH draft endpoint; autosave indicator shows last sync time. Publish modal handles diffs—granular change logs wait for future iterations.
- **Support hooks**: Inline help links jump to precise anchors within `DOCUMENTATION.md` so terminology stays aligned.

### 4.6 Column scripting & testing
- **Experience**: Selecting a column opens a right rail with Monaco editors, optional panels collapsed by default, universal **Test callable** button (⌘↵) running against selected sample docs.
- **Implementation**: `POST /configurations/{id}/test` identifies callable type + sample document ID; streaming output appears in a log panel. Store only the last successful run plus the current run per column; broader history lives in backlog.
- **Failure handling**: Tests surface stack traces trimmed to actionable frames with copy explaining how to report false positives.

### 4.7 Pre-activation validation
- **Experience**: “Review readiness” card summarises missing callables, failing tests, schema conflicts; once resolved, “Publish configuration” reveals diffs vs. current active version with schema diff surfaced first.
- **Implementation**: Frontend validator mirrors backend constraints; publish/activate modal fetches schema + callable diffs alongside key metrics deltas and blocks promotion if backend preflight fails or governance flags remain unresolved.
- **Auditability**: Capture who requested activation, who approved, and the associated change summary in metadata rails.

### 4.8 Upload & run
- **Experience**: Upload console defaults to the latest published configuration with a toggle to add the active config or other published versions (max three total) using colour-coded pills; resilient queue with per-file statuses.
- **Implementation**: Drag-and-drop component with resumable uploads; multi-select limited by schema compatibility; WebSocket channel streams run updates; refresh resilience via run ID stored in URL params.
- **Offline resilience**: If a socket drops, show reconnection attempts and keep the queue paused rather than silently failing.

### 4.9 Review results & iterate
- **Experience**: Completion toast links to table and comparison views; validation issues surfaced first; comparison matrix highlights changed cells and validation deltas.
- **Implementation**: `GET /runs/{id}/results` returns normalised data for table + diff; virtualization handles large tables; colour palette from config selection reused for diff highlights.
- **Iteration loop**: From results view users can jump straight back to the configuration column responsible for a flagged cell via deep-link anchors.

### 4.10 Ongoing mastery (post-MVP growth)
- **Experience**: Activity feeds, advanced shortcuts, help centre, and comparison snapshots support continuous improvement once the core loop is sticky.
- **Backlog anchors**: Multiplayer presence, saved comparison sets, and script catalogs remain flagged for future prioritisation. Keep space for them in the navigation but behind feature flags.

---

## 5. Interface architecture & navigation

### 5.1 Shell & navigation
- Global shell anchors the workspace selector, breadcrumb trail, and primary call-to-action area.
- Left navigation groups by lifecycle: **Home**, **Document Types**, **Runs**, **Comparisons**, **Admin** (feature-flagged). Avoid nested accordions; use contextual tabs within views instead.
- Command palette (⌘K) exposes navigation shortcuts, callable actions, and quick help.

### 5.2 Component tiers
- **Primitives** (Buttons, Inputs, Tabs, Dialogs) expose consistent props, support full keyboard handling, and follow WAI-ARIA guidance.
- **Compound components** (ColumnGrid, ScriptEditor, ComparisonMatrix) compose primitives and encapsulate data-fetch boundaries. Each includes a README covering data flow and error states.
- **Feature shells** orchestrate view state, analytics events, and error boundaries. They remain declarative, delegating heavy lifting to compounds and hooks.

### 5.3 State management contracts
- Wizard/coach-mark flows handled via state machines (XState or equivalent) to avoid boolean proliferation.
- Local draft state separated from server snapshots; when conflicts arise prompt users to reload or duplicate—full diffing waits for future tooling.
- Comparison selections stored in URL query params for shareable states; navigation preserves selections via `useSearchParams` helpers.

### 5.4 Error handling & resiliency
- All async mutations funnel through a central toast/alert system with severity tiers; destructive errors require explicit acknowledgement.
- Inline errors show recovery actions first (“Retry upload”, “Restore last published script”).
- WebSocket disconnects trigger exponential backoff and offline banners; never drop progress silently.

### 5.5 Accessibility & inclusion
- Every interactive region advertises keyboard shortcuts and focus order in component docs.
- Colour contrasts meet WCAG 2.1 AA; rely on tokenised palettes to guarantee compliance.
- Screen reader narratives accompany complex regions (tables, editors) with live-region updates for long-running operations.

---

## 6. Design system foundations

- Token scales: spacing (4 px base, multiples), typography (rem-based with clamp), colour roles (primary, success, warning, neutral, comparison accents).
- Component library built with headless primitives (e.g., Radix UI) plus custom styling to ensure accessibility and brand alignment.
- Theme file exports CSS variables consumed by both the application shell and Monaco editor for visual cohesion.
- Global theming supports light/dark parity; Monaco theme switches in lockstep with the app theme to avoid cognitive dissonance.
- Storybook (with Chromatic) acts as the living spec; documentation mode outlines usage, props, and accessibility notes for every component.

---

## 7. API & data integration discipline

- HTTP client in `lib/apiClient.ts` with typed helpers (e.g., `getDocumentTypes`, `saveConfigurationDraft`, `testCallable`, `runComparison`).
- React Query cache keys are namespaced by entity ID + version; invalidations trigger after promotions, draft saves, and run completions.
- Mutations return normalised data to keep derived state deterministic; optimistic updates only where rollback is trivial (naming, descriptions).
- Contract tests mirror backend schemas for edge cases: missing optional scripts, validation failures, schema mismatches. Break the build if the contract drifts.
- Analytics events flow through a typed emitter so tracking plans remain auditable and tree-shakeable.

---

## 8. Quality, security, and instrumentation

### 8.1 Testing strategy
| Layer | Tooling | Focus |
| --- | --- | --- |
| Unit & interaction | Vitest + Testing Library | Component logic, accessibility, keyboard flows. |
| Visual regression | Storybook + Chromatic | Layout stability, token adherence. |
| Contract tests | Vitest against mocked backend | API request/response fidelity, error edge cases. |
| End-to-end | Playwright | Smoke flows: first login → create document type → build configuration → run comparison. |

### 8.2 Security & data handling
- Enforce role-based access on edit vs. view actions; disable inputs, don’t hide objects entirely.
- Scrub sensitive payloads from client-side logs; rely on secure storage for auth tokens.
- Publish snapshots act as the rollback mechanism; duplication workflow enables branching from the active config without raw history exposure.

### 8.3 Observability & metrics
- Core metrics: time to first run, time to first publish, promote conversion rate.
- Secondary (post-launch): callable test usage, run failure ratios, comparison diff adoption.
- Error budget: <1 % failed runs attributable to frontend issues; monitor via Sentry tags referencing UI state.
- Performance SLO: key views (Home, Configuration workspace, Results) become interactive under 2.5 s on reference hardware; track via Real User Monitoring.
- Accessibility regression suite executed pre-release; failures block deployment until resolved.

### 8.4 Support & recovery
- Floating help beacon exposes contextual docs, keyboard cheat sheet, and support contact; AI assistant surfaces code hints within editors.
- Results view offers “Rerun with previous active configuration” as a safe fallback.
- Production support playbook documents triage steps, escalation paths, and communication templates for incidents.

---

## 9. Implementation roadmap

1. **Foundation sprint**
   - Scaffold frontend project, design tokens, global shell, authentication integration.
   - Ship Home zero state with checklist fed by workspace summary endpoint.
   - Spike Monaco/editor integration (including accessibility/perf evaluation) to lock constraints early.
2. **Document Type core**
   - Build library grid, creation wizard (Basics → Columns → Review), and detail overview.
   - Implement React Query caches and activity feed stubs.
3. **Configuration workspace**
   - Column grid + right rail skeleton; integrate Monaco; autosave indicator + inline test plumbing.
   - Deliver validation readiness checker and publish/activate modal with required schema diff.
4. **Upload & run console**
   - Drag-and-drop uploads, resumable queue, configuration multi-select, resilient WebSocket progress timeline with reconnect/backoff baked in.
5. **Results & comparison centre**
   - Table view with virtualisation, diff matrix, validation issue stack, promote/revert actions.
6. **Collaboration & polish**
   - Command palette, keyboard shortcuts, presence indicators, notification inbox, advanced analytics hooks.

Each milestone includes UX reviews, accessibility validation, analytics instrumentation, and documentation updates before exit.

**Definition of done per milestone**
- **Design sign-off**: Figma specs, interaction notes, and accessibility annotations reviewed with design lead.
- **Engineering validation**: Component stories, unit tests, and API mocks merged; performance budget evaluated via Lighthouse/React Profiler snapshots.
- **Product acceptance**: Demo recorded for stakeholders, instrumentation dashboards updated, rollout plan defined (feature flags + changelog copy).

**Risks & mitigations**
- **Complex Monaco integrations** → Spike early with proof-of-concept; wrap editor in isolated component with fallback plain-text mode.
- **WebSocket reliability** → Implement exponential backoff and offline buffering in the first release to avoid regressions later.
- **Scope creep on comparison tooling** → Ship baseline diff with clear backlog of advanced analytics to avoid delaying MVP.
- **Cross-team alignment** → Weekly design/dev sync with shared status doc; update `CURRENT_TASK.md` to keep AI contributors synchronised.

---

## 10. Next tangible deliverables

1. Narrative storyboard from first login through first comparison run, highlighting user emotions and confidence cues.
2. Low-fidelity wireframes for Home, Document Type library/detail, Configuration workspace, Upload & Run, Results/Comparison.
3. Component inventory with state diagrams (loading, empty, error) for major UI elements.
4. Prototype of script editor showing inline test execution, diff preview, and error surfacing.
5. API contract review confirming fields for onboarding status, run state machine, comparison diffs, audit logs, and presence.
6. Accessibility plan documenting focus order, keyboard shortcuts, and screen reader narratives for grids/editors.
7. Support playbook outline covering incident response, communication templates, and tooling checkpoints.

---

This document evolves with user insights. Keep revisions versioned so designers, engineers, and AI agents stay aligned while bringing ADE’s ideal UI to life.
