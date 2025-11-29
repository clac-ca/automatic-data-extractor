> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Capture requirements and UX goals for the new ade-web (incl. streaming use cases and design polish).
* [ ] Decide archive/rename strategy for the existing `apps/ade-web` and scaffold the new frontend baseline.
* [ ] Define target architecture (folders, navigation, data layer, design system) and land docs/stubs.
* [ ] Build the foundational runtime: navigation shell, shared providers, design tokens/theme, RunStream foundation.
* [ ] Migrate/implement core screens (Workspace home, Documents, Config Builder) on the new stack with streaming UX.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Decide archive strategy — existing app moved to apps/ade-web-legacy`

---

# ADE Web Refactor (from scratch)

## 1. Objective

**Goal:**
Rebuild `apps/ade-web` from the ground up (we can rename/archive the current folder) with a clean architecture, modern design system, and first-class run/build event streaming.

You will:

* Archive/rename the current `apps/ade-web` and scaffold a new Vite/React TypeScript app that matches our standards.
* Establish core app shell (navigation, providers, auth), shared design system, and streaming/data foundations.
* Reimplement priority experiences (Workspace, Documents, Config Builder) using the new event stream patterns and polished UX.

The result should:

* Deliver a coherent, high-quality UX with consistent visuals, layouts, and interactions across screens.
* Provide a maintainable architecture with clear layering, strong typing, streaming primitives, and test coverage for critical flows.

---

## 2. Context (What you are starting from)

Current `apps/ade-web` is a routerless, screen-first Vite app with bespoke nav helpers, scattered streaming logic (Config Builder owns its own reducer/SSE wiring), and a mix of UI primitives. Workbench is a large component blending editor, streaming, layout, and persistence. Documents screen embeds telemetry snippets ad hoc. Design system is minimal; theming is manual. We now have a unified backend event envelope (`AdeEvent`) and SSE/NDJSON replay for runs/builds, so the frontend can standardize on a single streaming foundation.

* Existing structure: `src/app` (providers/nav), `src/screens` (Workspace/ConfigBuilder), `src/shared` (API/auth/utils), `src/ui` (primitives), generated OpenAPI types under `src/generated-types`.
* Current behavior / expectations: history-based nav, EventSource for run streaming inside Workbench, summary/telemetry cards in Documents.
* Known issues / pain points: giant Workbench component, duplicated console formatting, streaming not reusable, limited design system, routerless nav adds complexity, telemetry fetch loads entire NDJSON into memory.
* Hard constraints: Keep Vite + React + TS; consume ADE API SSE/NDJSON (`/runs/{id}/events`, `events.ndjson`); use generated OpenAPI types (`ade openapi-types`).

---

## 3. Target architecture / structure (ideal)

Clean, layered Vite app with explicit routing (either keep lightweight history helper or adopt a minimal router), centralized providers, a reusable design system, and shared run-streaming infrastructure usable by any screen.

```text
apps/ade-web-new/          # new app root; archive old app to apps/ade-web-legacy/ or similar
  src/
    app/                   # App shell: providers (Query, Theme, Auth), layout chrome, navigation
    routes/                # Route-level screens (Workspace, RunDetail, Documents, ConfigBuilder)
      workspace/
      documents/
      run-detail/
      config-builder/
    features/              # Reusable domain modules (runs, documents, configs)
      runs/
        api/               # thin API client wrappers
        stream/            # RunStreamProvider, hooks, reducer, selectors
        components/        # RunConsole, RunTimeline, RunSummary, Validation cards
      documents/
      configs/
    ui/                    # Design system primitives (Button, Input, Tabs, Dialog, Toast, Layout)
    shared/                # Cross-cutting utils (storage, env, formatting, hooks)
    schema/                # Curated type exports + view models
    test/                  # Vitest setup + shared test utils
  public/
  vite.config.ts
  package.json
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* UX clarity: bold, intentional layouts; consistent spacing, typography, and interaction states.
* Maintainability: strict typing, shared streaming primitives, co-located feature code, minimal global state.
* Scalability: streaming foundation that supports live + replay, deep links, and large logs without freezing UI.

### 4.2 Key components / modules

* `RunStream` foundation — hook/provider that handles create/attach, SSE, replay, reconnection, backpressure, and selectors.
* `Run Experience` components — console, timeline, validation/table insights, summaries reused across RunDetail/Workbench/Documents.
* `Design system` — tokens, themes, layout primitives, and accessible components powering the new visual language.

### 4.3 Key flows / pipelines

* Run creation/attachment — `POST /runs?stream=false` → `GET /runs/{id}/events?stream=true&after_sequence=...`, with replay and auto-reattach.
* Config editing + run execution — workspace config editing, run/validate with streamed feedback, outputs/summaries inline.
* Document browsing → run insights — list documents, view last/related runs, open Run Detail with replayed telemetry.

### 4.4 Open questions / decisions

* Router: keep lightweight history helper vs adopt React Router (leaning Router for clarity and deep linking)?
* Theming: CSS variables + Tailwind tokens, or a bespoke design token pipeline? Decide before building UI primitives.

> **Agent instruction:**
> If you answer a question or make a design decision, replace the placeholder with the final decision and (optionally) a brief rationale.

---

## 5. Implementation & notes for agents

Use TypeScript strict mode, React Query for data, and a single API client (generated types re-exported via `@schema`). Archive the old app first (e.g., move to `apps/ade-web-legacy/`) before scaffolding the new root; update tooling/scripts accordingly. Build streaming on top of EventSource with robust abort/reconnect and incremental NDJSON parsing for history. Favor co-location under `features/` for domain logic. Ensure accessible components (Tabs/Dialog/Input), keyboard navigation, and responsive layouts. Add Vitest coverage for streaming hooks and console formatting; run `npm test`/`ade test` where applicable.

* Coding standards: strict TS, minimal any, prefer composition over inheritance.
* Testing requirements: unit tests for stream reducer/hooks; integration tests for RunDetail/Workbench happy paths.
* Performance: incremental NDJSON reader for large logs; clamp console buffers; avoid blocking UI on large payloads.
