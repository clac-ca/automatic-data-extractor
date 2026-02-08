import { ApiError } from "@/api/errors";
import { client, resolveApiUrl } from "@/api/client";
import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@/api/listing";
import {
  streamRunEventsWithEventSource,
  type EventSourceRunStreamOptions,
  type RunStreamConnectionState,
} from "./stream";

import type { components, paths } from "@/types";
import type { RunStreamEvent } from "@/types/runs";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunPage = components["schemas"]["RunPage"];
export type RunMetricsResource = components["schemas"]["RunMetricsResource"];
export type RunFieldResource = components["schemas"]["RunFieldResource"];
export type RunColumnResource = components["schemas"]["RunColumnResource"];
export type RunColumnsQuery =
  paths["/api/v1/workspaces/{workspaceId}/runs/{runId}/columns"]["get"]["parameters"]["query"];
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

type WorkspaceRunPathParams =
  paths["/api/v1/workspaces/{workspaceId}/runs/{runId}"]["get"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions> & {
  input_document_id?: RunCreateRequest["input_document_id"];
  configuration_id?: RunCreateRequest["configuration_id"];
};
export type RunBatchStreamOptions = Partial<RunBatchCreateOptions> & {
  configuration_id?: RunBatchCreateRequest["configuration_id"];
};
export type RunEventsStreamOptions = EventSourceRunStreamOptions;
export type { RunStreamConnectionState };
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

function workspaceRunPath(workspaceId: string, runId: string): WorkspaceRunPathParams {
  return { workspaceId, runId };
}

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

export async function fetchRunMetrics(
  workspaceId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunMetricsResource | null> {
  try {
    const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}/metrics", {
      params: { path: workspaceRunPath(workspaceId, runId) },
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

export async function fetchRunFields(
  workspaceId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunFieldResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}/fields", {
      params: { path: workspaceRunPath(workspaceId, runId) },
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
  workspaceId: string,
  runId: string,
  query: RunColumnsQuery | null,
  signal?: AbortSignal,
): Promise<RunColumnResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}/columns", {
      params: { path: workspaceRunPath(workspaceId, runId), query: query ?? undefined },
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
  workspaceId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunOutputSheet[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}/output/sheets", {
    params: { path: workspaceRunPath(workspaceId, runId) },
    signal,
  });
  if (!data) throw new Error("Expected run output sheets payload.");
  return data;
}

export async function fetchRunOutputPreview(
  workspaceId: string,
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

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}/output/preview", {
    params: { path: workspaceRunPath(workspaceId, runId), query },
    signal,
  });

  if (!data) throw new Error("Expected run output preview payload.");
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

export async function cancelRun(
  workspaceId: string,
  runId: string,
): Promise<RunResource> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/runs/{runId}/cancel", {
    params: { path: workspaceRunPath(workspaceId, runId) },
  });
  if (!data) {
    throw new Error("Expected run cancellation response.");
  }
  return data;
}

export async function* streamRunEvents(
  url: string,
  options: RunEventsStreamOptions = {},
): AsyncGenerator<RunStreamEvent> {
  yield* streamRunEventsWithEventSource(url, options);
}

export function runEventsUrl(
  run: RunResource,
  options?: { afterSequence?: number },
): string | null {
  const baseLink = run.links?.events_stream;
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
  workspaceId: string,
  run: RunResource | string,
  options?: {
    afterSequence?: number;
    signal?: AbortSignal;
    onConnectionStateChange?: (state: RunStreamConnectionState) => void;
  },
): AsyncGenerator<RunStreamEvent> {
  const runResource = typeof run === "string" ? await fetchRun(workspaceId, run, options?.signal) : run;
  const eventsUrl = runEventsUrl(runResource);
  if (!eventsUrl) {
    throw new Error("Run events stream is unavailable.");
  }
  yield* streamRunEvents(eventsUrl, options);
}

export async function fetchRun(
  workspaceId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunResource> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/runs/{runId}", {
    params: { path: workspaceRunPath(workspaceId, runId) },
    signal,
  });

  if (!data) throw new Error("Run not found");
  return data as RunResource;
}

export function runOutputUrl(run: RunResource): string | null {
  const output = run.output;
  const ready = output?.ready;
  const link = output?.download_url ?? run.links?.output_download;
  if (ready === false || !link) {
    return null;
  }
  return resolveApiUrl(link);
}

export function runLogsUrl(run: RunResource): string | null {
  const link = run.links?.events_download;
  return link ? resolveApiUrl(link) : null;
}

export function runInputUrl(run: RunResource): string | null {
  const link = run.links?.input_download;
  return link ? resolveApiUrl(link) : null;
}

function resolveRunLink(link: string, options?: { appendQuery?: string }) {
  const hasQuery = link.includes("?");
  const appended = options?.appendQuery
    ? `${link}${hasQuery ? "&" : "?"}${options.appendQuery}`
    : link;
  return resolveApiUrl(appended);
}
