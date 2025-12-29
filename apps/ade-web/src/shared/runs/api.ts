import { client, resolveApiUrl } from "@shared/api/client";

import type { components, paths } from "@schema";
import type { RunStreamEvent } from "./types";

export type RunResource = components["schemas"]["RunResource"];
export type RunCreateOptions = components["schemas"]["RunCreateOptionsBase"];
type RunCreateRequest = components["schemas"]["RunWorkspaceCreateRequest"];
type RunCreatePathParams =
  paths["/api/v1/workspaces/{workspace_id}/runs"]["post"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions> & {
  input_document_id: RunCreateRequest["input_document_id"];
  configuration_id?: RunCreateRequest["configuration_id"];
};
const DEFAULT_RUN_OPTIONS: RunCreateOptions = {
  dry_run: false,
  validate_only: false,
  force_rebuild: false,
  log_level: "INFO",
};

export async function createRun(
  workspaceId: string,
  options: RunStreamOptions,
  signal?: AbortSignal,
): Promise<RunResource> {
  const pathParams: RunCreatePathParams = { workspace_id: workspaceId };
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

  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/runs", {
    params: { path: pathParams },
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
  yield* streamRunEventsViaFetch(url, signal);
}

async function* streamRunEventsViaFetch(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const abortError =
    typeof DOMException !== "undefined"
      ? new DOMException("Aborted", "AbortError")
      : Object.assign(new Error("Aborted"), { name: "AbortError" });
  const controller = new AbortController();
  const abortHandler = () => controller.abort();
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

  if (signal?.aborted) {
    controller.abort();
  } else if (signal) {
    signal.addEventListener("abort", abortHandler);
  }

  try {
    const response = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "text/event-stream" },
      signal: controller.signal,
    });

    if (!response.body || !response.ok) {
      throw new Error("Run event stream unavailable.");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let shouldClose = false;

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const event = parseSseEvent(part);
        if (!event) {
          continue;
        }
        yield event;
        if (event.event === "run.complete") {
          shouldClose = true;
          break;
        }
      }

      if (done || shouldClose) {
        const finalEvent = parseSseEvent(buffer);
        if (finalEvent) {
          yield finalEvent;
        }
        return;
      }
    }
  } catch (error) {
    if (controller.signal.aborted) {
      throw abortError;
    }
    throw error;
  } finally {
    if (signal) {
      signal.removeEventListener("abort", abortHandler);
    }
    if (reader) {
      try {
        await reader.cancel();
      } catch {
        // ignore cancellation failures
      }
    }
    if (!controller.signal.aborted) {
      controller.abort();
    }
  }
}

function parseSseEvent(rawEvent: string): RunStreamEvent | null {
  const dataLines: string[] = [];

  for (const line of rawEvent.split(/\n/)) {
    if (line.startsWith("data:")) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
      continue;
    }
  }

  if (!dataLines.length) {
    return null;
  }

  const payload = dataLines.join("\n");
  if (!payload.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(payload) as RunStreamEvent;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    if (typeof parsed.event !== "string" || parsed.event.trim().length === 0) {
      return null;
    }
    if (!("timestamp" in parsed)) {
      return null;
    }
    (parsed as Record<string, unknown>)._raw = payload;

    return parsed;
  } catch (error) {
    console.warn("Skipping malformed run event", error, payload);
    return null;
  }
}

export function runEventsUrl(
  run: RunResource,
  options?: { afterSequence?: number },
): string | null {
  const baseLink = run.events_stream_url ?? run.links?.events_stream;
  if (!baseLink) {
    return null;
  }
  const queryParts: string[] = [];
  if (typeof options?.afterSequence === "number" && Number.isFinite(options.afterSequence)) {
    const normalized = Math.max(0, Math.floor(options.afterSequence));
    queryParts.push(`after_sequence=${normalized}`);
  }
  const appendQuery = queryParts.length ? queryParts.join("&") : undefined;
  return resolveRunLink(baseLink, { appendQuery });
}

export async function* streamRunEventsForRun(
  run: RunResource | string,
  options?: { afterSequence?: number; signal?: AbortSignal },
): AsyncGenerator<RunStreamEvent> {
  const runResource = typeof run === "string" ? await fetchRun(run, options?.signal) : run;
  const eventsUrl = runEventsUrl(runResource, { afterSequence: options?.afterSequence });
  if (!eventsUrl) {
    throw new Error("Run events link unavailable.");
  }
  for await (const event of streamRunEvents(eventsUrl, options?.signal)) {
    yield event;
  }
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
