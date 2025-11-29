import { post } from "@shared/api";
import { client, resolveApiUrl } from "@shared/api/client";

import type { RunSummaryV1, components } from "@schema";
import type { AdeEvent as RunStreamEvent } from "./types";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunOutputListing = components["schemas"]["RunOutputListing"];
export type RunCreateOptions = components["schemas"]["RunCreateOptions"];

export interface RunStreamOptions {
  readonly dry_run?: boolean;
  readonly validate_only?: boolean;
  readonly force_rebuild?: boolean;
  readonly document_ids?: readonly string[];
  readonly input_document_id?: string;
  readonly input_sheet_name?: string;
  readonly input_sheet_names?: readonly string[];
  readonly metadata?: Record<string, string>;
}

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const run = await post<RunResource>(
    `/configurations/${encodeURIComponent(configId)}/runs`,
    {
      stream: false,
      options,
    },
    { signal },
  );

  const runId = run.id ?? (run as { run_id?: string | null }).run_id;
  if (!runId) {
    throw new Error("Run ID missing from creation response");
  }

  const eventsUrl = resolveApiUrl(
    `/api/v1/runs/${encodeURIComponent(runId)}/events?stream=true&after_sequence=0`,
  );

  for await (const event of streamRunEvents(eventsUrl, signal)) {
    yield event;
  }
}

async function* streamRunEvents(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const abortError = new DOMException("Aborted", "AbortError");
  const queue: Array<RunStreamEvent | null> = [];
  const awaiters: Array<() => void> = [];

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
    source.close();
    queue.push(null);
    flush();
  };

  const source = new EventSource(url, { withCredentials: true });

  source.onmessage = (msg) => {
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
}

export async function fetchRunOutputs(
  runId: string,
  signal?: AbortSignal,
): Promise<RunOutputListing> {
  const { data } = await client.GET("/api/v1/runs/{run_id}/outputs", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (!data) throw new Error("Run outputs unavailable");
  return data as RunOutputListing;
}

export async function fetchRunTelemetry(
  runId: string,
  signal?: AbortSignal,
): Promise<RunStreamEvent[]> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/logfile`, {
    headers: { Accept: "application/x-ndjson" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run telemetry unavailable");
  }

  const text = await response.text();
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

export const runQueryKeys = {
  detail: (runId: string) => ["run", runId] as const,
  outputs: (runId: string) => ["run-outputs", runId] as const,
  telemetry: (runId: string) => ["run-telemetry", runId] as const,
  summary: (runId: string) => ["run-summary", runId] as const,
};
