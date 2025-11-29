# Frontend Streaming - Vanilla React Integration

This doc explains:

- How the frontend (vanilla React) should **attach to the event stream**.
- How to **process events efficiently** and share them across the UI.
- How to keep the implementation simple and aligned with "standard" patterns.

We assume the backend implements the API described in `030-API-DESIGN-RUNS-AND-BUILDS.md`.

---

## 1. Recommended pattern (React)

We recommend a **two-step pattern** for the UI:

1. **Create the run via POST (non-streaming)**.
2. **Attach an SSE connection via GET** for the run's events.

Why:

- `EventSource` (the standard browser SSE API) only supports `GET`.
- Keeping POST as "create job" and GET as "stream events" is a common pattern.

### 1.1 Step 1: Create the run

```ts
async function createRun(params: {
  workspaceId: string;
  configurationId: string;
  body: any; // Run request body
}): Promise<{ run_id: string }> {
  const res = await fetch(
    `/workspaces/${params.workspaceId}/configurations/${params.configurationId}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params.body),
    }
  );

  if (!res.ok) {
    throw new Error("Failed to create run");
  }

  return res.json(); // { run_id, status }
}
```

### 1.2 Step 2: Attach SSE to events

```ts
function attachRunEventSource(
  workspaceId: string,
  configurationId: string,
  runId: string,
  onEvent: (event: AdeEvent) => void
): EventSource {
  const url = `/workspaces/${workspaceId}/configurations/${configurationId}/runs/${runId}/events?stream=true`;
  const es = new EventSource(url);

  es.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data);
      onEvent(data as AdeEvent);
    } catch (e) {
      console.error("Failed to parse event", e, msg.data);
    }
  };

  es.onerror = (err) => {
    console.error("EventSource error", err);
    // Optionally: auto-reconnect logic with Last-Event-ID
  };

  return es;
}
```

We treat each incoming message as one `AdeEvent` (see `020-EVENT-TYPES-REFERENCE.md`).

---

## 2. State model in React

We want a **single source of truth per run** for:

* Build progress and status.
* Run phases and status.
* Console lines.
* Table summaries and validation summary.
* Final summary.

### 2.1 Suggested state shape

Conceptual TypeScript-ish:

```ts
type ConsoleLine = {
  sequence: number;
  scope: "build" | "run";
  stream: "stdout" | "stderr";
  level: "debug" | "info" | "warn" | "error";
  phase?: string;
  message: string;
};

type PhaseState = {
  status: "pending" | "running" | "succeeded" | "failed" | "skipped";
  durationMs?: number;
};

type RunEventState = {
  status: "queued" | "building" | "running" | "succeeded" | "failed" | "cancelled";

  buildPhases: Record<string, PhaseState>;
  runPhases: Record<string, PhaseState>;

  consoleLines: ConsoleLine[]; // truncated to last N lines to avoid huge arrays

  tableSummaries: Record<string, any>; // run.table.summary payloads
  validationSummary?: any;            // run.validation.summary payload

  completedEvent?: any;               // run.completed payload
};
```

We will derive this state by "reducing" the event stream.

---

## 3. React implementation pattern

Use:

* A **context + reducer** per run, so:

  * Multiple components (console, progress bar, result panel) can read the same state.
  * We do not create multiple SSE connections for the same run.

### 3.1 `RunEventsContext`

```ts
type RunEventsAction =
  | { type: "EVENT_RECEIVED"; event: AdeEvent }
  | { type: "RESET" };

function runEventsReducer(state: RunEventState, action: RunEventsAction): RunEventState {
  switch (action.type) {
    case "EVENT_RECEIVED":
      return applyEventToState(state, action.event);
    case "RESET":
      return initialState();
    default:
      return state;
  }
}

const RunEventsContext = React.createContext<{
  state: RunEventState;
  dispatch: React.Dispatch<RunEventsAction>;
}>({
  state: initialState(),
  dispatch: () => {},
});
```

`applyEventToState` is a pure function that:

* Looks at `event.type`.
* Updates relevant parts of `state`.

### 3.2 `RunEventsProvider`

```tsx
function RunEventsProvider({
  workspaceId,
  configurationId,
  runId,
  children,
}: {
  workspaceId: string;
  configurationId: string;
  runId: string;
  children: React.ReactNode;
}) {
  const [state, dispatch] = React.useReducer(runEventsReducer, undefined, initialState);

  React.useEffect(() => {
    dispatch({ type: "RESET" });

    const es = attachRunEventSource(workspaceId, configurationId, runId, (event) => {
      dispatch({ type: "EVENT_RECEIVED", event });
    });

    return () => es.close();
  }, [workspaceId, configurationId, runId]);

  return (
    <RunEventsContext.Provider value={{ state, dispatch }}>
      {children}
    </RunEventsContext.Provider>
  );
}
```

Any component under this provider can call `useContext(RunEventsContext)` to read state.

---

## 4. Applying events to state

### 4.1 Example `applyEventToState`

Conceptual only; real code will be more detailed:

```ts
function applyEventToState(state: RunEventState, event: AdeEvent): RunEventState {
  const { type, sequence, payload } = event;

  switch (type) {
    case "run.queued":
      return { ...state, status: "queued" };

    case "build.started":
      return { ...state, status: "building" };

    case "build.phase.started":
      return {
        ...state,
        buildPhases: {
          ...state.buildPhases,
          [payload.phase]: { status: "running" },
        },
      };

    case "build.phase.completed":
      return {
        ...state,
        buildPhases: {
          ...state.buildPhases,
          [payload.phase]: {
            status: payload.status as PhaseState["status"],
            durationMs: payload.duration_ms,
          },
        },
      };

    case "build.completed":
      // Keep status as building or move to running when run.started arrives
      return state;

    case "run.started":
      return { ...state, status: "running" };

    case "run.phase.started":
      return {
        ...state,
        runPhases: {
          ...state.runPhases,
          [payload.phase]: { status: "running" },
        },
      };

    case "run.phase.completed":
      return {
        ...state,
        runPhases: {
          ...state.runPhases,
          [payload.phase]: {
            status: payload.status as PhaseState["status"],
            durationMs: payload.duration_ms,
          },
        },
      };

    case "console.line": {
      const line: ConsoleLine = {
        sequence,
        scope: payload.scope,
        stream: payload.stream,
        level: payload.level,
        phase: payload.phase,
        message: payload.message,
      };

      const maxLines = 1000;
      const newLines = [...state.consoleLines, line];
      if (newLines.length > maxLines) {
        newLines.splice(0, newLines.length - maxLines);
      }

      return { ...state, consoleLines: newLines };
    }

    case "run.table.summary":
      return {
        ...state,
        tableSummaries: {
          ...state.tableSummaries,
          [payload.table_id]: payload,
        },
      };

    case "run.validation.summary":
      return { ...state, validationSummary: payload };

    case "run.completed":
      return {
        ...state,
        status: payload.status as RunEventState["status"],
        completedEvent: payload,
      };

    default:
      return state;
  }
}
```

This "event reducer" gives us a nice, event-sourced view for the UI.

---

## 5. Using the state in React components

Because state is shared via context, components stay simple:

### 5.1 Console component

```tsx
function RunConsole() {
  const { state } = React.useContext(RunEventsContext);
  const lines = state.consoleLines;

  return (
    <pre className="console">
      {lines.map((line) => (
        <div key={line.sequence}>
          {/* Optionally style by scope/level/stream */}
          {line.message}
        </div>
      ))}
    </pre>
  );
}
```

### 5.2 Build/run progress indicator

```tsx
function RunProgress() {
  const { state } = React.useContext(RunEventsContext);

  const buildStatus = state.status === "building" ? "Building..." : "Build complete";
  const runStatus = state.status === "running" ? "Running..." : state.status;

  return (
    <div>
      <div>Build: {buildStatus}</div>
      <div>Run: {runStatus}</div>
    </div>
  );
}
```

### 5.3 Result summary

```tsx
function RunSummaryView() {
  const { state } = React.useContext(RunEventsContext);

  if (!state.completedEvent) {
    return <div>Run in progress...</div>;
  }

  const { status, summary } = state.completedEvent;

  return (
    <div>
      <h3>Run status: {status}</h3>
      {/* Render summary fields as needed */}
      <pre>{JSON.stringify(summary, null, 2)}</pre>
    </div>
  );
}
```

---

## 6. Reuse across the frontend

### 6.1 Config builder screen

* When user clicks "Run":

  1. Call `createRun(...)`.
  2. Wrap the workbench view in `<RunEventsProvider runId={run_id} ...>`.
* Workbench children (`Console`, `Progress`, `Summary`) all consume from `RunEventsContext`.

### 6.2 Run details page

* Use the same `<RunEventsProvider>`:

  * On first mount:

    * Option A: open SSE with `from_sequence=1` to replay.
    * Option B: fetch NDJSON and play it through the reducer (offline replay).
* UI code is identical; only initialization differs.

---

## 7. Performance and simplicity notes

* **Bounded consoleLines**:

  * Keep only last ~1000 lines in memory.
  * Full logs are always available via `events.ndjson` download if needed.
* **One SSE per run**:

  * The context ensures only one live SSE connection for a given run in a given tab.
* **Pure, testable reducer**:

  * `applyEventToState` is deterministic; we can unit-test event handling without a browser.
* **No over-engineering**:

  * No Redux/tooling required.
  * Just `useReducer`, context, and `EventSource`.

---

## 8. Current ade-web integration points to update

- Console/rendering helpers that still expect `build.console` / `run.console`: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts` and `.../utils/__tests__/console.test.ts`.
- Docs that describe old run/build streams: `apps/ade-web/docs/04-data-layer-and-backend-contracts.md`.
- Event types are imported from `@shared/runs/types`; align those with the new `AdeEvent` schema before wiring the reducer.

---

## 9. Summary

Frontend pattern:

* **Create run** with POST.
* **Attach SSE** with `GET /runs/{run_id}/events?stream=true`.
* **Reduce events into state** via context + reducer.
* **Render from that state** in any components that care.

This matches common patterns for streaming UIs (CI logs, chat/LLM consoles) and keeps the React codebase simple and easy to reason about.
