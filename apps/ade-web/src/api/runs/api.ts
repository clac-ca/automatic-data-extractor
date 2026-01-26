import { ApiError } from "@/api/errors";
import { createIdempotencyKey } from "@/api/idempotency";
import { client, resolveApiUrl } from "@/api/client";
import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@/api/listing";

import type { components, paths } from "@/types";
import type { RunStreamEvent } from "@/types/runs";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunPage = components["schemas"]["RunPage"];
export type RunMetricsResource = components["schemas"]["RunMetricsResource"];
export type RunFieldResource = components["schemas"]["RunFieldResource"];
export type RunColumnResource = components["schemas"]["RunColumnResource"];
export type RunColumnsQuery = paths["/api/v1/runs/{runId}/columns"]["get"]["parameters"]["query"];
export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];
export type RunOutputSheet = components["schemas"]["RunOutputSheet"];

export type RunsQuery = {
  limit?: number;
  cursor?: string | null;
  q?: string | null;
  sort?: string | null;
  filters?: FilterItem[];
  joinOperator?: FilterJoinOperator;
  includeTotal?: boolean;
};

export type RunCreateOptions = components["schemas"]["RunCreateOptionsBase"];
type RunCreateRequest = components["schemas"]["RunWorkspaceCreateRequest"];
type RunCreatePathParams =
  paths["/api/v1/workspaces/{workspaceId}/runs"]["post"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions> & {
  input_document_id: RunCreateRequest["input_document_id"];
  configuration_id?: RunCreateRequest["configuration_id"];
};
export const RUNS_PAGE_SIZE = 50;
const DEFAULT_RUN_OPTIONS: RunCreateOptions = {
  dry_run: false,
  validate_only: false,
  log_level: "INFO",
  active_sheet_only: false,
};

export async function fetchWorkspaceRuns(
  workspaceId: string,
  query: RunsQuery,
  signal?: AbortSignal,
): Promise<RunPage> {
  const requestQuery = buildListQuery({
    limit: query.limit,
    cursor: query.cursor ?? null,
    sort: query.sort ?? null,
    q: query.q ?? null,
    joinOperator: query.joinOperator,
    filters: query.filters,
    includeTotal: query.includeTotal,
  });
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs", {
    params: { path: { workspaceId }, query: requestQuery },
    signal,
  });
  if (!data) throw new Error("Expected run page payload.");
  return data;
}

export async function fetchWorkspaceRunsForDocument(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<RunResource[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs", {
    params: {
      path: { workspaceId },
      query: buildListQuery({
        limit: 25,
        filters: [
          {
            id: "inputDocumentId",
            operator: "eq",
            value: documentId,
          },
        ],
      }),
    },
    signal,
  });

  if (!data) throw new Error("Expected run page payload.");
  return data.items ?? [];
}

export async function fetchRunMetrics(runId: string, signal?: AbortSignal): Promise<RunMetricsResource | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{runId}/metrics", {
      params: { path: { runId } },
      signal,
    });
    if (!data) {
      throw new Error("Expected run metrics payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchRunFields(runId: string, signal?: AbortSignal): Promise<RunFieldResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{runId}/fields", {
      params: { path: { runId } },
      signal,
    });
    if (!data) {
      throw new Error("Expected run fields payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchRunColumns(
  runId: string,
  query: RunColumnsQuery | null,
  signal?: AbortSignal,
): Promise<RunColumnResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{runId}/columns", {
      params: { path: { runId }, query: query ?? undefined },
      signal,
    });
    if (!data) {
      throw new Error("Expected run columns payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchRunOutputSheets(
  runId: string,
  signal?: AbortSignal,
): Promise<RunOutputSheet[]> {
  const { data } = await client.GET("/api/v1/runs/{runId}/output/sheets", {
    params: { path: { runId } },
    signal,
  });
  if (!data) throw new Error("Expected run output sheets payload.");
  return data;
}

export async function fetchRunOutputPreview(
  runId: string,
  options: {
    maxRows?: number;
    maxColumns?: number;
    trimEmptyRows?: boolean;
    trimEmptyColumns?: boolean;
    sheetName?: string | null;
    sheetIndex?: number | null;
  } = {},
  signal?: AbortSignal,
): Promise<WorkbookSheetPreview> {
  const query: Record<string, unknown> = {};
  if (options.maxRows !== undefined) query.maxRows = options.maxRows;
  if (options.maxColumns !== undefined) query.maxColumns = options.maxColumns;
  if (options.trimEmptyRows !== undefined) query.trimEmptyRows = options.trimEmptyRows;
  if (options.trimEmptyColumns !== undefined) query.trimEmptyColumns = options.trimEmptyColumns;
  if (options.sheetName) query.sheetName = options.sheetName;
  if (typeof options.sheetIndex === "number") query.sheetIndex = options.sheetIndex;

  const { data } = await client.GET("/api/v1/runs/{runId}/output/preview", {
    params: { path: { runId }, query },
    signal,
  });

  if (!data) throw new Error("Expected run output preview payload.");
  return data;
}

export async function createRunForDocument(
  configurationId: string,
  documentId: string,
  idempotencyKey?: string,
): Promise<RunResource> {
  const { data } = await client.POST("/api/v1/configurations/{configurationId}/runs", {
    params: { path: { configurationId } },
    headers: {
      "Idempotency-Key": idempotencyKey ?? createIdempotencyKey("run"),
    },
    body: {
      options: {
        dry_run: false,
        validate_only: false,
        active_sheet_only: false,
        input_document_id: documentId,
      },
    },
  });

  if (!data) throw new Error("Unable to create run.");
  return data;
}

export async function createRun(
  workspaceId: string,
  options: RunStreamOptions,
  signal?: AbortSignal,
  idempotencyKey?: string,
): Promise<RunResource> {
  const pathParams: RunCreatePathParams = { workspaceId };
  const { input_document_id, configuration_id, ...optionOverrides } = options;
  const mergedOptions: RunCreateOptions = { ...DEFAULT_RUN_OPTIONS, ...optionOverrides };
  if (!input_document_id) {
    throw new Error("input_document_id is required to start a run.");
  }
  const body: RunCreateRequest = {
    input_document_id,
    configuration_id: configuration_id ?? undefined,
    options: mergedOptions,
  };

  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/runs", {
    params: { path: pathParams },
    headers: {
      "Idempotency-Key": idempotencyKey ?? createIdempotencyKey("run"),
    },
    body,
    signal,
  });

  if (!data) {
    throw new Error("Expected run creation response.");
  }

  return data as RunResource;
}

export async function* streamRunEvents(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const response = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/x-ndjson" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run events unavailable.");
  }

  const payload = await response.text();
  const lines = payload.split(/\r?\n/);
  for (const line of lines) {
    const event = parseNdjsonEvent(line);
    if (event) {
      yield event;
    }
  }
}

function parseNdjsonEvent(rawLine: string): RunStreamEvent | null {
  const trimmed = rawLine.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed) as RunStreamEvent;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    if (typeof parsed.event !== "string" || parsed.event.trim().length === 0) {
      return null;
    }
    if (!("timestamp" in parsed)) {
      return null;
    }
    (parsed as Record<string, unknown>)._raw = trimmed;
    return parsed;
  } catch (error) {
    console.warn("Skipping malformed run event", error, rawLine);
    return null;
  }
}

function isTerminalStatus(status: RunStatus | null | undefined): boolean {
  return status === "succeeded" || status === "failed";
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abortError =
      typeof DOMException !== "undefined"
        ? new DOMException("Aborted", "AbortError")
        : Object.assign(new Error("Aborted"), { name: "AbortError" });
    if (signal?.aborted) {
      reject(abortError);
      return;
    }
    const timer = window.setTimeout(() => {
      if (signal) {
        signal.removeEventListener("abort", onAbort);
      }
      resolve();
    }, Math.max(0, ms));

    function onAbort() {
      window.clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      reject(abortError);
    }

    if (signal) {
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

export function runEventsUrl(
  run: RunResource,
  _options?: { afterSequence?: number },
): string | null {
  const baseLink = run.events_download_url ?? run.links?.events_download;
  if (!baseLink) {
    return null;
  }
  return resolveRunLink(baseLink);
}

export async function* streamRunEventsForRun(
  run: RunResource | string,
  options?: { afterSequence?: number; signal?: AbortSignal },
): AsyncGenerator<RunStreamEvent> {
  const signal = options?.signal;
  const runResource = typeof run === "string" ? await fetchRun(run, signal) : run;
  let current = runResource;
  const pollIntervalMs = 2000;

  while (!isTerminalStatus(current.status)) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    await delay(pollIntervalMs, signal);
    current = await fetchRun(current.id, signal);
  }

  const eventsUrl = runEventsUrl(current);
  let sawCompletion = false;
  if (eventsUrl) {
    for await (const event of streamRunEvents(eventsUrl, signal)) {
      if (event.event === "run.complete") {
        sawCompletion = true;
      }
      yield event;
    }
  }

  if (!sawCompletion) {
    yield {
      event: "run.complete",
      timestamp: new Date().toISOString(),
      level: current.status === "failed" ? "error" : "info",
      message: "Run complete",
      data: {
        status: current.status,
        exit_code: current.exit_code ?? undefined,
      },
    } satisfies RunStreamEvent;
  }
}


export async function fetchRun(
  runId: string,
  signal?: AbortSignal,
): Promise<RunResource> {
  const { data } = await client.GET("/api/v1/runs/{runId}", {
    params: { path: { runId } },
    signal,
  });

  if (!data) throw new Error("Run not found");
  return data as RunResource;
}

export function runOutputUrl(run: RunResource): string | null {
  const output = run.output;
  const ready = output?.ready;
  const link = output?.download_url ?? run.links?.output_download ?? run.links?.output;
  if (ready === false || !link) {
    return null;
  }
  return resolveApiUrl(link);
}

export function runLogsUrl(run: RunResource): string | null {
  const link = run.events_download_url ?? run.links?.events_download;
  return link ? resolveApiUrl(link) : null;
}

export function runInputUrl(run: RunResource): string | null {
  const link = run.links?.input_download ?? run.links?.input;
  return link ? resolveApiUrl(link) : null;
}

function resolveRunLink(link: string, options?: { appendQuery?: string }) {
  const hasQuery = link.includes("?");
  const appended = options?.appendQuery
    ? `${link}${hasQuery ? "&" : "?"}${options.appendQuery}`
    : link;
  return resolveApiUrl(appended);
}
