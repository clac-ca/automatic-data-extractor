# ADE frontend master blueprint

Great products feel inevitable. This living blueprint distils ADE’s product truths, articulates the end-to-end user journey, and decomposes the UI and frontend architecture so designers and engineers can craft an experience that feels effortless while staying maintainable. This revision filters out experiments and emphasises the flows and tooling required for the first production release.

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

## 3. System mental model & scaffolding

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

### 3.3 Frontend technology commitments
- **Foundations** – Vite + React + TypeScript remain the core so we gain fast feedback, typed components, and simple bundling. React Router (v6) owns routing/data loaders for nested layouts without bespoke plumbing.
- **Data layer** – TanStack Query orchestrates server reads/mutations with explicit cache keys (workspace, document type, configuration, run). Derived projections live in hooks inside the features that need them; no additional global store is planned.
- **Forms & validation** – React Hook Form with Zod keeps wizard steps and column editors declarative and aligned with backend schemas. Shared schema utilities sit beside API clients to avoid drift.
- **Stateful flows** – XState is adopted only where diagrams improve clarity (document type wizard, upload queue). Simple toggles and panels stick to local component state.
- **Editors & grids** – `@monaco-editor/react` provides the script editing surface. Column grids, run results, and diff views use `@tanstack/react-table` with `@tanstack/react-virtual` for virtualization without adding a heavy UI kit.
- **Styling & theming** – Design tokens live as CSS variables. Components use CSS Modules for scoping; lightweight utility classes cover layout/spacing. Radix UI primitives supply accessible structure while letting us own the look.
- **Real-time & side effects** – Native WebSocket clients stream events into dedicated services that update TanStack Query caches. Local storage access flows through a typed helper so hydration stays deterministic.

### 3.4 External dependency evaluation
| Dependency | Decision | Rationale |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Proven trio for ADE’s scale; already required for TS-first workflow. |
| React Router v6 loaders | ✅ Adopt | Handles nested layouts, preloading, and redirects cleanly without custom plumbing. |
| @tanstack/react-query | ✅ Adopt | Cache + mutation layer that keeps API usage consistent across views. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe validation for wizards and editors; mirrors backend validation rules. |
| @tanstack/react-table + @tanstack/react-virtual | ✅ Adopt | Composable tables with virtualization for large runs and diff matrices. |
| Radix UI primitives | ✅ Adopt | Accessibility-first building blocks; we own styling while inheriting correct semantics. |
| @monaco-editor/react | ✅ Adopt | Maintains parity with IDE editing experience without hand-rolling integrations. |
| XState | ✅ Targeted | Reserved for flows that benefit from explicit state charts (wizard + uploads). |
| Storybook | ✅ Adopt | Local component workbench; snapshot tests keep tokens honest without SaaS lock-in. |
| File upload helper (Uppy or tus-js-client) | 🕵 Evaluate later | Start with fetch + chunked uploads; add a helper only if resumable flows outgrow native APIs. |
| Charting library (e.g., Recharts) | ⏳ Defer | No charts in MVP; revisit once analytics dashboards exist. |

Avoid cargo-cult additions: no Redux, Moment.js, or sprawling UI suites. Prefer the standard library (`Intl`, `URL`, `Array`) a
nd targeted utilities we can audit.

---

## 4. End-to-end experience map

Each stage lists the desired user experience, implementation hooks, and instrumentation guardrails. Treat onboarding to mastery as a repeatable loop: orient → configure → validate → run → learn.

### 4.1 Onboard & build trust
- **Experience**: Minimal SSO/magic-link entry flows route directly into a focused onboarding checklist. Intro copy clarifies the overall loop without blocking setup.
- **Implementation**: A React Router loader exchanges auth tokens then prefetches `workspaceSummary` via TanStack Query so the checklist renders with data on first paint. Dismissed tips persist through a typed local-storage helper, and a simple reducer keeps checklist progress predictable—no state machine needed yet.
- **Instrumentation**: Track first-login completion and drop-off per checklist task to tune messaging.

### 4.2 Home zero state
- **Experience**: One checklist spelling out the core loop (“Create type → Add configuration → Upload → Run”) guiding users to a first successful run in under five minutes. Optional tips stay collapsed until requested.
- **Implementation**: `useQuery(['workspace','summary'])` keeps the checklist, zero states, and quick links coherent. Actions (e.g., “Create document type”) call React Router mutations so navigation and analytics happen in one place. Persisted dismissals reuse the onboarding storage helper.
- **Guardrails**: Empty states must list the *next* safe action (e.g., “Create a document type”) with copy matching backend terminology.

### 4.3 Define a document type
- **Experience**: Lightweight three-step wizard (**Basics → Column blueprint → Review**) guiding schema creation without overwhelming detail.
- **Implementation**: An XState chart drives the wizard, while React Hook Form + Zod handle field validation and default values. Column blueprints leverage `useFieldArray`; optional CSV import uses native `FileReader` parsing first, upgrading to a helper library only if real-world files expose edge cases. The review step renders the exact payload sent to `POST /document-types` so users build trust in the system.
- **Instrumentation**: Capture drop-off per step and validation errors to tune defaults.

### 4.4 Document type overview
- **Experience**: Hero card confirms creation, call-to-action “Start first configuration”, tabs previewing future data and run history.
- **Implementation**: Nested React Router routes hydrate the overview, while TanStack Query prefetches configuration drafts so moving into the workspace feels instantaneous. Skeletons mirror real card structure to prevent layout shift. Background refetch keeps metrics fresh without jarring reloads.
- **Guardrails**: Provide a dismissible “Next steps” banner until the first configuration is published.

### 4.5 Build the configuration workspace
- **Experience**: Draft workspace opens with seeded columns, inline education about detection/validation/transformation, and autosave reassurance.
- **Implementation**: The column grid uses `@tanstack/react-table` + `@tanstack/react-virtual` for smooth scrolling. `@monaco-editor/react` lazy-loads editors the first time a column is opened and reuses instances thereafter. Autosave runs through a debounced TanStack Query mutation (5 s trailing edge) so PATCHes stay predictable; an inline status chip shows the last sync time and error recovery path. Publish modals read from cached diff endpoints—full activity timelines stay in backlog.
- **Support hooks**: Inline help links jump to precise anchors within `DOCUMENTATION.md` so terminology stays aligned.

### 4.6 Column scripting & testing
- **Experience**: Selecting a column opens a right rail with Monaco editors, optional panels collapsed by default, universal **Test callable** button (⌘↵) running against selected sample docs.
- **Implementation**: A dedicated TanStack Query mutation calls `POST /configurations/{id}/test`; streamed logs (SSE or chunked JSON) append to a ring buffer component. Per-column cache entries store the most recent success + in-flight run so results survive navigation. Assertions render alongside code with copy/paste snippets from `DOCUMENTATION.md` to speed fixes.
- **Failure handling**: Tests surface stack traces trimmed to actionable frames with copy explaining how to report false positives.

### 4.7 Pre-activation validation
- **Experience**: “Review readiness” card summarises missing callables, failing tests, schema conflicts; once resolved, “Publish configuration” reveals diffs vs. current active version with schema diff surfaced first.
- **Implementation**: Shared Zod schemas check for required callables, validation coverage, and naming collisions before the publish button lights up. The publish modal pulls diffs via `GET /configurations/{id}/diff` and raises a confirmation dialog if backend governance checks fail. Promotion events invalidate TanStack Query caches for document types, runs, and comparisons in one sweep.
- **Auditability**: Capture who requested activation, who approved, and the associated change summary in metadata rails.

### 4.8 Upload & run
- **Experience**: Upload console defaults to the latest published configuration with a toggle to add the active config or other published versions (max three total) using colour-coded pills; resilient queue with per-file statuses.
- **Implementation**: A dedicated upload machine coordinates drag-and-drop, client-side validation, and chunked uploads using the Fetch API (`File.slice`, `ReadableStream`, `AbortController`). If resumable requirements exceed native capabilities we upgrade to Uppy/tus. Run selections persist in the URL so reloads rehydrate the same queue. WebSocket events hydrate a TanStack Query observer that fans updates into the run timeline.
- **Offline resilience**: If a socket drops, show reconnection attempts and keep the queue paused rather than silently failing.

### 4.9 Review results & iterate
- **Experience**: Completion toast links to table and comparison views; validation issues surfaced first; comparison matrix highlights changed cells and validation deltas.
- **Implementation**: `useQuery(['runs', id, 'results'])` hydrates structured data for TanStack Table; virtualization keeps scrolling at 60 fps on reference hardware. Diff highlights reuse configuration colour tokens and fall back to patterns for colour-blind safety. Deep links leverage React Router search params to reopen the exact column + callable that produced a flagged cell.
- **Iteration loop**: From results view users can jump straight back to the configuration column responsible for a flagged cell via deep-link anchors.

### 4.10 Post-MVP backlog
- **Experience**: Activity feeds, advanced shortcuts, help centre, and comparison snapshots support continuous improvement once the core loop is stable.
- **Backlog anchors**: Command palette, multiplayer presence, saved comparison sets, and script catalogues stay behind feature flags and lazy-loaded routes so baseline users remain fast.

---

## 5. Interface architecture & navigation

### 5.1 Shell & navigation
- Global shell anchors the workspace selector, breadcrumb trail, and primary call-to-action area using React Router layout routes so nested views inherit structure without prop drilling.
- Left navigation groups by lifecycle: **Home**, **Document Types**, **Runs**, **Comparisons**, **Admin** (feature-flagged). Counts/badges pull from TanStack Query selectors; avoid nested accordions—use contextual tabs inside views.
- Secondary actions stay contextual within page headers. A global command palette remains a backlog experiment until usage data proves the need.

### 5.2 Component tiers
- **Primitives** (Buttons, Inputs, Tabs, Dialogs) expose consistent props, support full keyboard handling, and follow WAI-ARIA guidance. Radix UI seeds behaviour; styling layers atop CSS Modules + tokens.
- **Compound components** (ColumnGrid, ScriptEditor, ComparisonMatrix) compose primitives and encapsulate data-fetch boundaries. Each ships with a Storybook story, README, and Vitest coverage for edge cases.
- **Feature shells** orchestrate view state, analytics events, and error boundaries. They remain declarative, delegating heavy lifting to compounds and hooks. Shells live in `frontend/src/features/*` with colocated loaders and tests.

### 5.3 State management contracts
- Wizard/coach-mark flows handled via state machines (XState or equivalent) to avoid boolean proliferation and to document allowed transitions.
- Local draft state separated from server snapshots; when conflicts arise prompt users to reload or duplicate—full diffing waits for future tooling. Never mirror server state inside React Context if TanStack Query already owns it.
- Comparison selections stored in URL query params for shareable states; navigation preserves selections via `useSearchParams` helpers. URL hydration replays `uploadMachine` progress when possible.

### 5.4 Error handling & resiliency
- All async mutations funnel through a central toast/alert system with severity tiers; destructive errors require explicit acknowledgement and emit Sentry breadcrumbs.
- Inline errors show recovery actions first (“Retry upload”, “Restore last published script”) and link to documentation anchors for self-service.
- WebSocket disconnects trigger exponential backoff and offline banners; never drop progress silently. Client keeps the last known payload cached so replays remain possible.

### 5.5 Accessibility & inclusion
- Every interactive region advertises keyboard shortcuts and focus order in component docs.
- Colour contrasts meet WCAG 2.1 AA; rely on tokenised palettes to guarantee compliance.
- Screen reader narratives accompany complex regions (tables, editors) with live-region updates for long-running operations.

---

## 6. Design system foundations

- Token scales: spacing (4 px base, multiples), typography (rem-based with clamp), colour roles (primary, success, warning, neutral, comparison accents).
- Tokens live in `frontend/src/design/tokens.css` as CSS variables with TypeScript exports for runtime usage. No ad-hoc hex codes—lint blocks them.
- Component library built with headless primitives (e.g., Radix UI) plus custom styling to ensure accessibility and brand alignment. Shared layout utilities live in `design/layout.css`.
- Theme file exports CSS variables consumed by both the application shell and Monaco editor for visual cohesion. Monaco receives the palette through `defineTheme` on mount.
- Global theming supports light/dark parity; Monaco theme switches in lockstep with the app theme to avoid cognitive dissonance.
- Storybook acts as the living spec; documentation mode outlines usage, props, and accessibility notes for every component. Add automated visual regression (Playwright or Chromatic) once manual reviews surface drift.

---

## 7. API & data integration discipline

- HTTP client in `lib/apiClient.ts` with typed helpers (e.g., `getDocumentTypes`, `saveConfigurationDraft`, `testCallable`, `runComparison`).
- React Query cache keys are namespaced by entity ID + version; invalidations trigger after promotions, draft saves, and run completions. Response transformers live beside the query key definitions.
- Mutations return normalised data to keep derived state deterministic; optimistic updates only where rollback is trivial (naming, descriptions).
- Runtime response guards use Zod during development; production builds strip them to avoid overhead while keeping types honest.
- Contract tests mirror backend schemas for edge cases: missing optional scripts, validation failures, schema mismatches. Break the build if the contract drifts.
- Analytics events flow through a typed emitter so tracking plans remain auditable and tree-shakeable. Events batch through `navigator.sendBeacon` to avoid blocking unload.

---

## 8. Quality, security, and instrumentation

### 8.1 Testing strategy
| Layer | Tooling | Focus |
| --- | --- | --- |
| Unit & interaction | Vitest + Testing Library | Component logic, accessibility, keyboard flows. |
| Visual regression | Storybook + Playwright image snapshots (Chromatic later if needed) | Layout stability, token adherence. |
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
- Contextual docs and keyboard references live within the help menu inside each feature shell; keep them lightweight to avoid distracting from core tasks.
- Results view offers “Rerun with previous active configuration” as a safe fallback.
- Production support playbook documents triage steps, escalation paths, and communication templates for incidents.

---

## 9. Implementation roadmap

1. **Foundation sprint**
   - Scaffold Vite + React + TypeScript with React Router, TanStack Query, testing tooling, and Storybook wired into CI.
   - Ship Home zero state with checklist fed by workspace summary endpoint and persisted onboarding storage helper.
   - Spike Monaco/editor integration (accessibility + performance) to lock constraints early and document fallback modes.
2. **Document Type core**
   - Build library grid, creation wizard (Basics → Columns → Review), and detail overview.
   - Wire React Hook Form + Zod schemas, targeted XState wizard machine, and React Query caches.
3. **Configuration workspace**
   - Column grid + right rail skeleton; integrate Monaco; autosave indicator + inline test plumbing.
   - Deliver validation readiness checker and publish/activate modal with required schema diff plus cache invalidation sweep.
4. **Upload & run console**
   - Drag-and-drop uploads, resilient queue, configuration multi-select, WebSocket progress timeline with reconnect/backoff baked in.
   - Stress-test native upload queue; document criteria for introducing Uppy/tus if native stack struggles.
5. **Results & hardening**
   - Table view with virtualisation, diff matrix, validation issue stack, promote/revert actions wired into React Router deep links.
   - Instrument accessibility audits, error handling paths, and performance budgets before release.

Each milestone includes UX reviews, accessibility validation, analytics instrumentation, and documentation updates before exit.

**Definition of done per milestone**
- **Design sign-off**: Figma specs, interaction notes, and accessibility annotations reviewed with design lead.
- **Engineering validation**: Component stories, unit tests, and API mocks merged; performance budget evaluated via Lighthouse/React Profiler snapshots or equivalent.
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
4. Dependency integration dossier: React Query key map, wizard/upload state machine sketches, and design token ownership plan.
5. Prototype of script editor showing inline test execution, diff preview, and error surfacing.
6. API contract review confirming fields for onboarding status, run state machine, comparison diffs, and audit logs.
7. Accessibility plan documenting focus order, keyboard shortcuts, and screen reader narratives for grids/editors.

---

This document evolves with user insights. Keep revisions versioned so designers, engineers, and AI agents stay aligned while bringing ADE’s ideal UI to life.
