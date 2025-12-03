# ADE Web – Architecture Overview

> This document explains **how** the new `apps/ade-web` is structured and how the main pieces fit together:
>
> - App shell, navigation, and routing.
> - Feature modules (runs, documents, configs).
> - Run streaming + telemetry pipeline.
> - Data and state management.
> - Extensibility and performance considerations.
>
> For UX flows and screen behavior, see `030-UX-FLOWS.md`.  
> For streaming details, see `050-RUN-STREAMING-SPEC.md`.  
> For navigation details, see `060-NAVIGATION.md`.

---

## 1. Goals & Design Principles

The architecture should enable us to:

1. **Support rich streaming UX**  
   The run event system (SSE + NDJSON) must be a first-class citizen, not an afterthought glued onto screens.

2. **Make Documents & Config Builder shareable primitives**  
   Runs started from Documents and runs started from Config Builder use the **same** streaming foundation and UI components.

3. **Keep navigation “vanilla React” but structured**  
   Custom history-based routing with a typed route model, no React Router, but still fully URL-driven and deep-linkable.

4. **Be feature-oriented and composable**  
   Domain concepts (runs, documents, configs) live in `features/*`, each owning their API, types, and higher-level UI components.

5. **Be easy to extend & refactor**  
   Adding new screens, run views, or dashboards should mean wiring together existing primitives, not copy-pasting logic.

---

## 2. High-Level View

At a high level, the app looks like this:

```text
┌─────────────────────────────────────────────────────────────┐
│                     AppShell & Providers                    │
│  (Nav, Auth, Query, Theme, RunStreamRoot)                   │
└─────────────────────────────────────────────────────────────┘
                 │                         │
     URL → Route │                         │ Global Contexts
                 ▼                         ▼
          ┌───────────────┐      ┌────────────────────────────┐
          │   Screens      │      │        Features            │
          │  (Workspace,   │◀────▶│ runs / documents / configs │
          │  Documents,    │      │ (api, stream, components)  │
          │  RunDetail,    │      └────────────────────────────┘
          │  ConfigBuilder)│                 │
          └───────────────┘                 ▼
                          ┌───────────────────────┐
                          │   UI Design System    │
                          │  (tokens, layout,     │
                          │   primitives)         │
                          └───────────────────────┘
````

* **AppShell**: sets up global providers (Auth, Query, Theme, Nav, RunStream root) and decides which screen to render based on the current route.
* **Screens**: thin, route-level components that orchestrate feature modules and UI primitives.
* **Features**: domain modules (runs, documents, configs) with their own API surface, hooks, and “feature components”.
* **UI Design System**: shared primitives (buttons, cards, layout) and visual tokens.
* **Shared**: cross-cutting utilities (API client, storage, formatting).

---

## 3. Folder Structure

The new app lives in `apps/ade-web/` and follows this structure:

```text
apps/ade-web/
  src/
    app/
      AppShell.tsx            # top-level layout and providers
      nav/
        routes.ts             # Route type + helpers
        navigation.ts         # history integration
        useNavigation.ts      # hook for components
      providers/
        AuthProvider.tsx
        QueryProvider.tsx
        ThemeProvider.tsx
        ToastProvider.tsx
        RunStreamRootProvider.tsx
    screens/
      Workspace/
        WorkspaceScreen.tsx
      Documents/
        DocumentsScreen.tsx
      RunDetail/
        RunDetailScreen.tsx
      ConfigBuilder/
        ConfigBuilderScreen.tsx
    features/
      runs/
        api/
          runsApi.ts
        stream/
          RunStreamState.ts
          runStreamReducer.ts
          RunStreamProvider.tsx
          useRunStream.ts
          useRunTelemetry.ts
        components/
          RunConsole.tsx
          RunTimeline.tsx
          RunSummaryPanel.tsx
          ValidationSummary.tsx
        schema/
          RunTypes.ts
      documents/
        api/
          documentsApi.ts
        components/
          DocumentList.tsx
          DocumentDetail.tsx
          UploadPanel.tsx
          DocumentRunsPanel.tsx
          DocumentOutputsPanel.tsx
        hooks/
          useDocuments.ts
          useDocumentRuns.ts
          useDocumentOutputs.ts
      configs/
        api/
          configsApi.ts
        components/
          ConfigBuilderShell.tsx
          ConfigEditor.tsx
          ConfigSidebar.tsx
        hooks/
          useWorkbenchRun.ts
      auth/
        api/
        hooks/
    ui/
      theme/
        tokens.css
        ThemeProvider.tsx
      components/
        Button.tsx
        Input.tsx
        Select.tsx
        Tabs.tsx
        Dialog.tsx
        Tooltip.tsx
        Toast.tsx
        Tag.tsx
        Badge.tsx
        Table.tsx
      layout/
        Page.tsx
        PageHeader.tsx
        SplitPane.tsx
        Panel.tsx
        Sidebar.tsx
        ScrollArea.tsx
    shared/
      api-client/
        client.ts
      hooks/
        useAsync.ts
        usePrevious.ts
      formatting/
        dateTime.ts
        numbers.ts
      storage/
        localStorage.ts
        sessionStorage.ts
      errors/
        ErrorBoundary.tsx
        errorTypes.ts
    schema/
      index.ts                # curated exports of generated ADE types + view models
    test/
      setupTests.ts
      testUtils.tsx
```

---

## 4. Navigation & App Shell

### 4.1 Route Model

We use a typed union to represent all navigable screens:

```ts
export type Route =
  | { name: 'workspace'; params: {} }
  | { name: 'documents'; params: { workspaceId: string } }
  | { name: 'document'; params: { workspaceId: string; documentId: string } }
  | { name: 'runDetail'; params: { workspaceId: string; runId: string; sequence?: number } }
  | { name: 'configBuilder'; params: { workspaceId: string; configId: string } };
```

This gives us:

* A single source of truth for routes.
* Type-safe navigation (`navigate({ name: 'document', params: { ... } })`).
* Explicit mapping between URL and route.

See `060-NAVIGATION.md` for URL schemes and edge cases.

### 4.2 Navigation Implementation (no React Router)

The navigation layer:

* Parses `window.location` into a `Route`.
* Listens to `popstate` events.
* Exposes a `useNavigation()` hook:

```ts
export function useNavigation() {
  // returns current Route and navigate/replace functions
  return { route, navigate, replace };
}
```

Screens use `route.name` to switch which view to render. There is no React Router, but behavior is still fully URL-driven and bookmarkable.

### 4.3 AppShell & Providers

`AppShell` is responsible for:

1. Mounting global providers:

   * `AuthProvider`
   * `QueryProvider`
   * `ThemeProvider`
   * `ToastProvider`
   * `RunStreamRootProvider` (shared streaming context)
2. Using `useNavigation()` to read the current `Route`.
3. Rendering the appropriate screen under a common layout:

```tsx
export function AppShell() {
  const { route } = useNavigation();

  return (
    <AppProviders>
      <PageLayout>
        {route.name === 'workspace' && <WorkspaceScreen />}
        {route.name === 'documents' && (
          <DocumentsScreen workspaceId={route.params.workspaceId} />
        )}
        {/* ...other screens... */}
      </PageLayout>
    </AppProviders>
  );
}
```

---

## 5. Feature Modules

### 5.1 Runs Feature

**Responsibilities:**

* Running and querying run data.
* Streaming SSE & NDJSON telemetry.
* Providing reusable run-centric UI components.

**Submodules:**

* `api/` – thin wrappers like:

  * `startRunForDocument(documentId, configId?)`
  * `startRunForConfig(configId)`
  * `getRunSummary(runId)`
* `stream/` – streaming infrastructure:

  * `RunStreamState`, `runStreamReducer`
  * `RunStreamProvider`, `useRunStream(runId)`
  * `useRunTelemetry(runId)`
* `components/` – UI primitives:

  * `RunConsole` – log viewer with filters.
  * `RunTimeline` – phases & durations.
  * `RunSummaryPanel` – status, duration, key metrics.
  * `ValidationSummary` – per-table validation status.
* `schema/` – types:

  * `RunStatus`, `RunPhase`, `ConsoleLine`, `ValidationSummary`, etc.

**Consumers:**

* Documents screen (live run card, run list).
* Run Detail screen.
* Config Builder run panel.

### 5.2 Documents Feature

**Responsibilities:**

* Upload, list, and manage documents.
* Show aggregated run state per document.
* Provide a coherent download surface (original, normalized, logs).

**Submodules:**

* `api/` – e.g.:

  * `listDocuments(workspaceId)`
  * `uploadDocument(workspaceId, file)`
  * `getDocumentRuns(documentId)`
  * `getDocumentOutputs(documentId, runId)`
* `components/`:

  * `DocumentList` – left column list.
  * `DocumentDetail` – right panel with tabs (Overview, Runs, Outputs).
  * `UploadPanel` – drag & drop, progress.
  * `DocumentRunsPanel`, `DocumentOutputsPanel`.
* `hooks/`:

  * `useDocuments(workspaceId)`
  * `useDocumentRuns(documentId)`
  * `useDocumentOutputs(documentId)`

**Screens:**

* `DocumentsScreen` composes Documents + Runs features and UI primitives.

### 5.3 Configs Feature

**Responsibilities:**

* List, load, and persist configs.
* Provide Config Builder shell and integrate run streaming.

**Submodules:**

* `api/` – `listConfigs`, `getConfig`, `updateConfig`, etc.
* `components/` – `ConfigBuilderShell`, `ConfigEditor`, `ConfigSidebar`.
* `hooks/` – `useWorkbenchRun`:

  * Wraps `useRunStream` + run creation logic for config context.

**Screens:**

* `ConfigBuilderScreen` orchestrates config editing and run experience.

---

## 6. Data Management & API Layer

### 6.1 API Client

`shared/api-client/client.ts` centralizes HTTP configuration:

* Base URL and environment.
* Auth token injection (if needed).
* Standard error translation (to typed `ApiError`).

Feature APIs `features/*/api` call into this client but only expose domain-specific functions.

### 6.2 React Query

We use React Query for server state:

* Example patterns:

  * `useQuery(['documents', workspaceId], () => documentsApi.listDocuments(workspaceId))`
  * `useQuery(['runSummary', runId], () => runsApi.getRunSummary(runId))`
* Behaviors:

  * Caching and background refetch for lists and summaries.
  * Screen components stay focused on composition, not imperative data fetching.

### 6.3 Local State

* Screen-level state (selected document, active tab, filters) lives in each screen or feature hook.
* We avoid global “app-wide” state managers beyond:

  * Navigation route.
  * Auth state.
  * Global run streaming root (see next section).

---

## 7. Run Streaming Architecture

Run streaming is central to the app; it lives entirely inside `features/runs/stream`.

### 7.1 RunStreamState & Reducer

* Shared `RunStreamState` models:

  * Current status (idle/attaching/live/replaying/completed/error).
  * `lastSequence`.
  * Derived console lines, phases, validation summary, table summaries.
* `runStreamReducer` is pure and is the only place that mutates this state shape.

Details: `050-RUN-STREAMING-SPEC.md`.

### 7.2 Live SSE (useRunStream)

`useRunStream(runId)`:

* Attaches to `/runs/{runId}/events?stream=true&after_sequence=...`.
* Uses `EventSource` to receive `AdeEvent`s.
* Dispatches `EVENT_BATCH_RECEIVED` into the reducer.
* Provides selectors to consumers:

  * `consoleLines`, `phases`, `validationSummary`, `tableSummaries`.
* Handles reconnection:

  * On network issues, re-attaches SSE using `after_sequence = lastSequence`.

### 7.3 Historical NDJSON (useRunTelemetry)

`useRunTelemetry(runId)`:

* Fetches `/runs/{runId}/events.ndjson` as a `ReadableStream`.
* Streams lines through a parser and dispatches them via `EVENT_BATCH_RECEIVED`.
* Supports partial replay:

  * Optionally stops at `sequence` for deep-linked views.
* Used by Run Detail to reconstruct state for completed runs, especially when not live.

### 7.4 Backpressure & Performance

* Console line cap (e.g. default 5000–10000 lines in UI).

  * Older lines dropped from in-memory console buffer; underlying events may still be retained or re-fetchable via replay.
* Batch updates:

  * Events are buffered briefly (frame-level or short window) before updating React state to avoid excessive renders.

---

## 8. Screens as Orchestrators

Screens are **thin**; they orchestrate features and layout but do not contain deep domain logic.

### 8.1 DocumentsScreen

**Responsibilities:**

* Read route parameters (workspaceId).
* Use Documents hooks:

  * `useDocuments(workspaceId)` for list.
* Use Runs hooks:

  * For each active run, use `useRunStream(runId)` in the detail panel/card.
* Compose UI:

  * `Page` + `SplitPane` + `DocumentList` + `DocumentDetail`.

### 8.2 RunDetailScreen

**Responsibilities:**

* Read `workspaceId`, `runId`, `sequence?` from route.
* Decide whether to:

  * Use `useRunStream(runId)` (if run is live), or
  * Use `useRunTelemetry(runId)` for replay and derived state.
* Pass state into:

  * `RunTimeline`
  * `RunConsole`
  * `RunSummaryPanel`
  * `ValidationSummary`

### 8.3 ConfigBuilderScreen

**Responsibilities:**

* Load config via React Query.
* Use `ConfigBuilderShell` + `ConfigEditor`.
* Use `useWorkbenchRun` hook to:

  * Start runs.
  * Bind to streaming via `useRunStream`.

---

## 9. Error Handling & Observability

### 9.1 Error Boundaries

* `shared/errors/ErrorBoundary.tsx` used around:

  * Entire app (global fallback).
  * Critical screens (config builder, run detail) when appropriate.

### 9.2 API & Streaming Errors

* API errors:

  * Shown via inline message or toast, depending on severity.
  * Throw typed `ApiError` with structured details.
* Streaming errors:

  * Mark `RunStreamState.status = 'error'`.
  * Show subtle banner/toast in relevant screen.
  * Allow user to “Retry streaming” (reattach SSE).

---

## 10. Performance & Scalability

Key considerations:

* **Large telemetry**:

  * NDJSON parsing is incremental; we never load huge logs in a single `JSON.parse`.
  * Console rendering uses capped buffers and can be virtualized later if necessary.
* **Bundle size**:

  * Feature-oriented structure supports code-splitting by screen if needed.
* **Streaming**:

  * Batching SSE updates avoids render storms for high-volume runs.

---

## 11. Extensibility

This architecture should make the following easy:

* Adding new run-based views:

  * E.g., “Run comparison” screen that reuses `RunTimeline`, `RunSummaryPanel`, and streaming hooks.
* Adding new entity types:

  * A new `features/*` module can follow the same pattern (api/hooks/components).
* Evolving navigation:

  * New routes added via expanding the `Route` union and updating `routes.ts`.

---

## 12. Non-Goals (for this iteration)

The architecture supports them, but they are **not required** for this workpackage:

* Global run wallboard with real-time tiles for all active runs.
* Cross-workspace dashboards or search.
* Advanced analytics (run regression trends, phase performance graphs).
* Plug-and-play module system for third-party features.

These can be introduced later as new feature modules and screens.

---

## 13. Summary

The new `apps/ade-web` architecture is:

* **Feature-oriented** – runs, documents, configs are clearly separated but compose nicely.
* **Streaming-first** – SSE + NDJSON are treated as core primitives via `RunStreamState` and hooks.
* **URL-driven, vanilla React** – custom routing gives structure without pulling in a router framework.
* **Design-system backed** – UX and UI are consistent across screens.

If you need to change a foundational decision (navigation mode, streaming shape, data layer), update this document and the relevant spec (`050-RUN-STREAMING-SPEC.md`, `060-NAVIGATION.md`) before touching code.