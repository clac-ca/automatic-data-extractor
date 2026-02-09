export type WorkbenchPane = "terminal" | "problems";
export type WorkbenchConsoleState = "open" | "closed";

export interface WorkbenchSearchState {
  readonly pane: WorkbenchPane;
  readonly console: WorkbenchConsoleState;
  readonly fileId?: string;
}

export interface WorkbenchSearchSnapshot extends WorkbenchSearchState {
  readonly present: {
    readonly pane: boolean;
    readonly console: boolean;
    readonly fileId: boolean;
  };
}

export const DEFAULT_WORKBENCH_SEARCH: WorkbenchSearchState = {
  pane: "terminal",
  console: "closed",
};

const WORKBENCH_PARAM_KEYS = ["pane", "console", "file"] as const;

function normalizeConsole(value: string | null): WorkbenchConsoleState {
  return value === "open" ? "open" : "closed";
}

function normalizePane(value: string | null): WorkbenchPane {
  if (value === "problems") return "problems";
  return "terminal";
}

export function readWorkbenchSearchParams(source: URLSearchParams | string): WorkbenchSearchSnapshot {
  const params = source instanceof URLSearchParams ? source : new URLSearchParams(source);
  const paneRaw = params.get("pane");
  const consoleRaw = params.get("console");
  const fileRaw = params.get("file");

  return {
    pane: normalizePane(paneRaw),
    console: normalizeConsole(consoleRaw),
    fileId: fileRaw ?? undefined,
    present: {
      pane: params.has("pane"),
      console: params.has("console"),
      fileId: params.has("file"),
    },
  };
}

export function mergeWorkbenchSearchParams(
  current: URLSearchParams,
  patch: Partial<WorkbenchSearchState>,
): URLSearchParams {
  const existing = readWorkbenchSearchParams(current);
  const mergedState: WorkbenchSearchState = {
    ...DEFAULT_WORKBENCH_SEARCH,
    ...existing,
    ...patch,
  };

  const next = new URLSearchParams(current);
  for (const key of WORKBENCH_PARAM_KEYS) {
    next.delete(key);
  }
  if (mergedState.pane !== DEFAULT_WORKBENCH_SEARCH.pane) {
    next.set("pane", mergedState.pane);
  }
  if (mergedState.console !== DEFAULT_WORKBENCH_SEARCH.console) {
    next.set("console", mergedState.console);
  }
  if (mergedState.fileId && mergedState.fileId.length > 0) {
    next.set("file", mergedState.fileId);
  }
  return next;
}

export type WorkbenchSearchPatch =
  | Partial<WorkbenchSearchState>
  | ((snapshot: WorkbenchSearchSnapshot) => Partial<WorkbenchSearchState>);

export function applyWorkbenchSearchPatch(
  current: URLSearchParams,
  patch: WorkbenchSearchPatch,
): URLSearchParams {
  const snapshot = readWorkbenchSearchParams(current);
  const resolvedPatch = typeof patch === "function" ? patch(snapshot) : patch;
  return mergeWorkbenchSearchParams(current, resolvedPatch);
}
