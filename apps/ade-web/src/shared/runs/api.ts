import { client, resolveApiUrl } from "@shared/api/client";

import type { components, paths } from "@schema";
import type { RunStreamEvent } from "./types";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunCreateOptions = components["schemas"]["RunCreateOptions"];
type RunCreateRequest = components["schemas"]["RunCreateRequest"];
type RunCreatePathParams =
  paths["/api/v1/configurations/{configuration_id}/runs"]["post"]["parameters"]["path"];

export type RunStreamOptions = Partial<RunCreateOptions>;
const DEFAULT_RUN_OPTIONS: RunCreateOptions = {
  dry_run: false,
  validate_only: false,
  force_rebuild: false,
  debug: false,
};

export async function createRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): Promise<RunResource> {
  const pathParams: RunCreatePathParams = { configuration_id: configId };
  const mergedOptions: RunCreateOptions = { ...DEFAULT_RUN_OPTIONS, ...options };
  const body: RunCreateRequest = { options: mergedOptions };

  const { data } = await client.POST("/api/v1/configurations/{configuration_id}/runs", {
    params: { path: pathParams },
    body,
    signal,
  });

  if (!data) {
    throw new Error("Expected run creation response.");
  }

  return data as RunResource;
}

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const runResource = await createRun(configId, options, signal);
  const eventsUrl = runEventsUrl(runResource, { afterSequence: 0 });
  if (!eventsUrl) {
    throw new Error("Run creation response is missing required links.");
  }

  for await (const event of streamRunEvents(eventsUrl, signal)) {
    yield event;
  }
}

export async function* streamRunEvents(
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
  let sseId: string | null = null;
  let sseEvent: string | null = null;

  for (const line of rawEvent.split(/\n/)) {
    if (line.startsWith("data:")) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
      continue;
    }
    if (line.startsWith("id:")) {
      sseId = line.slice(3).trim();
      continue;
    }
    if (line.startsWith("event:")) {
      sseEvent = line.slice(6).trim();
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

    // Fill in missing event/type from SSE event field if not present in payload.
    if (sseEvent && !(parsed as Record<string, unknown>).event && !(parsed as Record<string, unknown>).type) {
      (parsed as Record<string, unknown>).event = sseEvent;
    }

    // Attach sequence/id if absent and SSE id is numeric or non-empty.
    if (sseId && (parsed as Record<string, unknown>).sequence === undefined) {
      const numeric = Number(sseId);
      if (Number.isFinite(numeric)) {
        (parsed as Record<string, unknown>).sequence = numeric;
      } else {
        (parsed as Record<string, unknown>).sse_id = sseId;
      }
    }

    return parsed;
  } catch (error) {
    console.warn("Skipping malformed run event", error, payload);
    return null;
  }
}

export function runEventsUrl(
  run: RunResource,
  options?: { afterSequence?: number; stream?: boolean },
): string | null {
  const baseLink =
    run.events_stream_url ??
    run.links?.events_stream ??
    run.events_url ??
    run.links?.events;
  if (!baseLink) {
    return null;
  }
  const queryParts: string[] = [];
  const wantsStream = options?.stream ?? true;
  const alreadyStreaming = baseLink.endsWith("/stream") || baseLink.includes("stream=true");
  if (wantsStream && !alreadyStreaming) {
    queryParts.push("stream=true");
  }
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

export async function fetchRunEvents(
  run: RunResource | string,
  options?: { afterSequence?: number; signal?: AbortSignal },
): Promise<RunStreamEvent[]> {
  const runResource = typeof run === "string" ? await fetchRun(run, options?.signal) : run;
  const eventsUrl = runEventsUrl(runResource, { afterSequence: options?.afterSequence, stream: false });
  if (!eventsUrl) {
    throw new Error("Run events link unavailable.");
  }
  const response = await fetch(eventsUrl, {
    method: "GET",
    credentials: "include",
    signal: options?.signal,
  });
  if (!response.ok) {
    throw new Error(`Run events unavailable (${response.status}).`);
  }
  const text = await response.text();
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const events: RunStreamEvent[] = [];
  for (const line of lines) {
    try {
      events.push(JSON.parse(line) as RunStreamEvent);
    } catch (error) {
      console.warn("Skipping malformed run event line", error, line);
    }
  }
  return events;
}

export async function fetchRunTelemetry(
  run: RunResource | string,
  signal?: AbortSignal,
): Promise<RunStreamEvent[]> {
  const runResource = typeof run === "string" ? await fetchRun(run, signal) : run;
  const downloadLink =
    runResource.events_download_url ??
    runResource.links?.events_download ??
    runResource.links?.logs;
  if (!downloadLink) {
    throw new Error("Run logs link unavailable.");
  }

  const response = await fetch(resolveApiUrl(downloadLink), {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/x-ndjson" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Run telemetry unavailable (${response.status}).`);
  }
  const data = await response.text();

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
  const link = run.events_download_url ?? run.links?.events_download ?? run.links?.logs;
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
  telemetry: (runId: string) => ["run-telemetry", runId] as const,
};
