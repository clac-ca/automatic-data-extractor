import { ApiError } from "@/api/errors";
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
export type RunBatchCreateOptions = components["schemas"]["RunBatchCreateOptions"];
type RunBatchCreateRequest = components["schemas"]["RunWorkspaceBatchCreateRequest"];
type RunBatchCreatePathParams =
  paths["/api/v1/workspaces/{workspaceId}/runs/batch"]["post"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions> & {
  input_document_id?: RunCreateRequest["input_document_id"];
  configuration_id?: RunCreateRequest["configuration_id"];
};
export type RunBatchStreamOptions = Partial<RunBatchCreateOptions> & {
  configuration_id?: RunBatchCreateRequest["configuration_id"];
};
export const RUNS_PAGE_SIZE = 50;
const DEFAULT_RUN_OPTIONS: RunCreateOptions = {
  operation: "process",
  dry_run: false,
  log_level: "INFO",
  active_sheet_only: false,
};
const DEFAULT_BATCH_RUN_OPTIONS: RunBatchCreateOptions = {
  operation: "process",
  dry_run: false,
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
): Promise<RunResource> {
  const { data } = await client.POST("/api/v1/configurations/{configurationId}/runs", {
    params: { path: { configurationId } },
    body: {
      options: {
        operation: "process",
        dry_run: false,
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
): Promise<RunResource> {
  const pathParams: RunCreatePathParams = { workspaceId };
  const { input_document_id, configuration_id, ...optionOverrides } = options;
  const mergedOptions: RunCreateOptions = { ...DEFAULT_RUN_OPTIONS, ...optionOverrides };
  if (mergedOptions.operation === "process" && !input_document_id) {
    throw new Error("input_document_id is required to start a run.");
  }
  const body: RunCreateRequest = {
    input_document_id: input_document_id ?? undefined,
    configuration_id: configuration_id ?? undefined,
    options: mergedOptions,
  };

  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/runs", {
    params: { path: pathParams },
    body,
    signal,
  });

  if (!data) {
    throw new Error("Expected run creation response.");
  }

  return data as RunResource;
}

export async function createRunsBatch(
  workspaceId: string,
  documentIds: string[],
  options: RunBatchStreamOptions = {},
  signal?: AbortSignal,
): Promise<RunResource[]> {
  const pathParams: RunBatchCreatePathParams = { workspaceId };
  const dedupedDocumentIds = Array.from(new Set(documentIds.filter(Boolean)));
  if (dedupedDocumentIds.length === 0) {
    return [];
  }

  const { configuration_id, ...optionOverrides } = options;
  const mergedOptions: RunBatchCreateOptions = { ...DEFAULT_BATCH_RUN_OPTIONS, ...optionOverrides };
  const body: RunBatchCreateRequest = {
    document_ids: dedupedDocumentIds,
    configuration_id: configuration_id ?? undefined,
    options: mergedOptions,
  };

  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/runs/batch", {
    params: { path: pathParams },
    body,
    signal,
  });
  if (!data) {
    throw new Error("Expected run batch creation response.");
  }
  return data.runs ?? [];
}

export async function cancelRun(runId: string): Promise<RunResource> {
  const { data } = await client.POST("/api/v1/runs/{runId}/cancel", {
    params: { path: { runId } },
  });
  if (!data) {
    throw new Error("Expected run cancellation response.");
  }
  return data;
}

export async function* streamRunEvents(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const response = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "text/event-stream, application/x-ndjson" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run events unavailable.");
  }

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/x-ndjson")) {
    yield* streamNdjsonEventsFromResponse(response, signal);
    return;
  }

  if (!response.body) {
    throw new Error("Run events stream is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName: string | undefined;
  let eventId: string | undefined;
  let dataLines: string[] = [];

  const flush = (): RunStreamEvent | null => {
    const rawData = dataLines.join("\n");
    dataLines = [];
    const resolvedEvent = (eventName || "message").trim() || "message";
    const resolvedId = eventId?.trim() || undefined;
    eventName = undefined;
    eventId = undefined;

    if (!rawData.trim() || resolvedEvent === "keepalive") {
      return null;
    }
    const parsed = parseNdjsonEvent(rawData);
    if (parsed) {
      return {
        ...parsed,
        ...(resolvedEvent && parsed.event !== resolvedEvent ? { event: resolvedEvent } : {}),
        ...(resolvedId ? { event_id: resolvedId } : {}),
      };
    }
    return {
      event: resolvedEvent,
      timestamp: new Date().toISOString(),
      message: rawData,
      ...(resolvedId ? { event_id: resolvedId } : {}),
    };
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    while (true) {
      const newlineIndex = buffer.indexOf("\n");
      if (newlineIndex < 0) {
        break;
      }
      let line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      if (line.endsWith("\r")) {
        line = line.slice(0, -1);
      }
      if (!line) {
        const parsed = flush();
        if (parsed) {
          yield parsed;
        }
        continue;
      }
      if (line.startsWith(":")) {
        continue;
      }
      const separator = line.indexOf(":");
      const field = separator >= 0 ? line.slice(0, separator) : line;
      const valueText = separator >= 0 ? line.slice(separator + 1).replace(/^\s/, "") : "";
      if (field === "event") {
        eventName = valueText;
      } else if (field === "id") {
        eventId = valueText;
      } else if (field === "data") {
        dataLines.push(valueText);
      }
    }
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    dataLines.push(buffer.trim());
  }
  const finalParsed = flush();
  if (finalParsed) {
    yield finalParsed;
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

export function runEventsUrl(
  run: RunResource,
  options?: { afterSequence?: number },
): string | null {
  const baseLink = run.links?.events_stream ?? run.events_download_url ?? run.links?.events_download;
  if (!baseLink) {
    return null;
  }
  const cursor = options?.afterSequence;
  if (typeof cursor === "number" && Number.isFinite(cursor) && cursor > 0) {
    return resolveRunLink(baseLink, { appendQuery: `cursor=${Math.floor(cursor)}` });
  }
  return resolveRunLink(baseLink);
}

export async function* streamRunEventsForRun(
  run: RunResource | string,
  options?: { afterSequence?: number; signal?: AbortSignal },
): AsyncGenerator<RunStreamEvent> {
  const signal = options?.signal;
  const runResource = typeof run === "string" ? await fetchRun(run, signal) : run;
  const eventsUrl = runEventsUrl(runResource, { afterSequence: options?.afterSequence });
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
    let current = await fetchRun(runResource.id, signal);
    while (
      current.status !== "succeeded"
      && current.status !== "failed"
      && current.status !== "cancelled"
    ) {
      await sleep(1000, signal);
      current = await fetchRun(runResource.id, signal);
    }
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

async function* streamNdjsonEventsFromResponse(
  response: Response,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  if (!response.body) {
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseNdjsonEvent(line);
      if (event) {
        yield event;
      }
    }
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseNdjsonEvent(buffer);
  if (finalEvent) {
    yield finalEvent;
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = globalThis.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, Math.max(0, ms));
    const onAbort = () => {
      globalThis.clearTimeout(timeout);
      signal?.removeEventListener("abort", onAbort);
      reject(new DOMException("Aborted", "AbortError"));
    };
    if (signal?.aborted) {
      onAbort();
      return;
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
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
