import { client, resolveApiUrl } from "@shared/api/client";

import type { RunSummaryV1, components, paths } from "@schema";
import type { AdeEvent as RunStreamEvent } from "./types";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunOutputListing = components["schemas"]["RunOutputListing"];
export type RunCreateOptions = components["schemas"]["RunCreateOptions"];
type RunCreateRequest = components["schemas"]["RunCreateRequest"];
type RunCreatePathParams =
  paths["/api/v1/configurations/{configuration_id}/runs"]["post"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions>;
const DEFAULT_RUN_OPTIONS: RunCreateOptions = {
  dry_run: false,
  validate_only: false,
  force_rebuild: false,
};

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const pathParams: RunCreatePathParams = { configuration_id: configId };
  const mergedOptions: RunCreateOptions = { ...DEFAULT_RUN_OPTIONS, ...options };
  const body: RunCreateRequest = {
    stream: false,
    options: mergedOptions,
  };

  const { data } = await client.POST("/api/v1/configurations/{configuration_id}/runs", {
    params: { path: pathParams },
    body,
    signal,
  });

  if (!data) {
    throw new Error("Expected run creation response.");
  }

  const runId = data.id;
  const eventsLink = data.links?.events;
  if (!runId || !eventsLink) {
    throw new Error("Run creation response is missing required links.");
  }

  const eventsUrl = resolveRunLink(eventsLink, { appendQuery: "stream=true&after_sequence=0" });

  for await (const event of streamRunEvents(eventsUrl, signal)) {
    yield event;
  }
}

export async function* streamRunEvents(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const abortError = new DOMException("Aborted", "AbortError");
  const queue: Array<RunStreamEvent | null> = [];
  const awaiters: Array<() => void> = [];

  let source: EventSource | null = null;
  let done = false;
  let error: unknown;

  const flush = () => {
    while (awaiters.length) {
      const resolve = awaiters.shift();
      resolve?.();
    }
  };

  const close = (reason?: unknown) => {
    if (done) return;
    done = true;
    if (reason) {
      error = reason;
    }
    if (source) {
      source.removeEventListener?.("ade.event", handleRunEvent as EventListener);
      source.onmessage = null;
      source.onerror = null;
      source.close();
    }
    queue.push(null);
    flush();
  };

  const handleRunEvent = (msg: MessageEvent<string>) => {
    try {
      const event = JSON.parse(msg.data) as RunStreamEvent;
      queue.push(event);
      flush();
      if (event.type === "run.completed") {
        close();
      }
    } catch (err) {
      console.warn("Skipping malformed run event", err, msg.data);
    }
  };

  source = new EventSource(url, { withCredentials: true });
  source.addEventListener("ade.event", handleRunEvent as EventListener);
  source.onmessage = handleRunEvent;

  source.onerror = () => {
    if (signal?.aborted) {
      close(abortError);
      return;
    }
    if (!done) {
      close(new Error("Run event stream interrupted"));
    }
  };

  if (signal) {
    if (signal.aborted) {
      close(abortError);
    } else {
      signal.addEventListener("abort", () => close(abortError));
    }
  }

  try {
    while (true) {
      if (!queue.length) {
        await new Promise<void>((resolve) => awaiters.push(resolve));
      }

      const next = queue.shift();
      if (next === null) {
        if (error) {
          throw error;
        }
        break;
      }
      if (!next) {
        continue;
      }
      if (error) {
        throw error;
      }
      yield next;
    }
  } finally {
    close();
  }
}

export async function fetchRunOutputs(
  run: RunResource | string,
  signal?: AbortSignal,
): Promise<RunOutputListing> {
  const runResource = typeof run === "string" ? await fetchRun(run, signal) : run;
  const outputsLink = runResource.links?.outputs;
  const runId = runResource.id;
  if (!outputsLink || !runId) {
    throw new Error("Run outputs link unavailable.");
  }

  const { data, error } = await client.GET("/api/v1/runs/{run_id}/outputs", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (error || !data) throw new Error("Run outputs unavailable");
  return data as RunOutputListing;
}

export async function fetchRunTelemetry(
  run: RunResource | string,
  signal?: AbortSignal,
): Promise<RunStreamEvent[]> {
  const runResource = typeof run === "string" ? await fetchRun(run, signal) : run;
  const logsLink = runResource.links?.logs;
  const runId = runResource.id;
  if (!logsLink || !runId) {
    throw new Error("Run logs link unavailable.");
  }

  const { data, error } = await client.GET("/api/v1/runs/{run_id}/logs", {
    params: { path: { run_id: runId } },
    headers: { Accept: "application/x-ndjson" },
    signal,
    parseAs: "text",
  });

  if (error) {
    throw new Error("Run telemetry unavailable");
  }

  const text = data ?? "";
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as RunStreamEvent;
      } catch (error) {
        console.warn("Skipping invalid telemetry line", { error, line });
        return null;
      }
    })
    .filter((value): value is RunStreamEvent => Boolean(value));
}

export async function fetchRun(
  runId: string,
  signal?: AbortSignal,
): Promise<RunResource> {
  const { data } = await client.GET("/api/v1/runs/{run_id}", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (!data) throw new Error("Run not found");
  return data as RunResource;
}

export async function fetchRunSummary(runId: string, signal?: AbortSignal): Promise<RunSummaryV1 | null> {
  // Prefer the dedicated summary endpoint; fall back to embedded summaries when present.
  try {
    const { data } = await client.GET("/api/v1/runs/{run_id}/summary", {
      params: { path: { run_id: runId } },
      signal,
    });
    if (data) return data as RunSummaryV1;
  } catch (error) {
    // If the backend is older or the endpoint is unavailable, continue to fallback parsing.
    console.warn("Falling back to embedded run summary", error);
  }

  const run = await fetchRun(runId, signal);
  const summary = (run as { summary?: RunSummaryV1 | string | null })?.summary;
  if (!summary) return null;
  if (typeof summary === "string") {
    try {
      return JSON.parse(summary) as RunSummaryV1;
    } catch (error) {
      console.warn("Unable to parse run summary", { error });
      return null;
    }
  }
  return summary as RunSummaryV1;
}

export function runOutputsUrl(run: RunResource): string | null {
  const link = run.links?.outputs;
  return link ? resolveApiUrl(link) : null;
}

export function runLogsUrl(run: RunResource): string | null {
  const link = run.links?.logs;
  return link ? resolveApiUrl(link) : null;
}

function resolveRunLink(link: string, options?: { appendQuery?: string }) {
  const hasQuery = link.includes("?");
  const appended = options?.appendQuery
    ? `${link}${hasQuery ? "&" : "?"}${options.appendQuery}`
    : link;
  return resolveApiUrl(appended);
}

export const runQueryKeys = {
  detail: (runId: string) => ["run", runId] as const,
  outputs: (runId: string) => ["run-outputs", runId] as const,
  telemetry: (runId: string) => ["run-telemetry", runId] as const,
  summary: (runId: string) => ["run-summary", runId] as const,
};
