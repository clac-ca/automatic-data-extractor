import { resolveApiUrl } from "@shared/api/client";

import type { RunStreamOptions } from "@shared/runs/api";
import type { RunStreamEvent } from "@shared/runs/types";

function buildJobStreamUrl(configurationId: string, options: RunStreamOptions): string {
  const params = new URLSearchParams();
  if (options.dry_run) params.set("dry_run", "true");
  if (options.validate_only) params.set("validate_only", "true");
  if (options.force_rebuild) params.set("force_rebuild", "true");
  if (options.debug) params.set("debug", "true");
  if (options.input_document_id) params.set("input_document_id", options.input_document_id);
  const sheetNames = options.input_sheet_names ?? [];
  for (const sheetName of sheetNames) {
    params.append("input_sheet_names", sheetName);
  }

  const base = resolveApiUrl(`/api/v1/configurations/${configurationId}/jobs/stream`);
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

export async function* streamConfigurationJobEvents(
  configurationId: string,
  options: RunStreamOptions,
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const url = buildJobStreamUrl(configurationId, options);
  yield* streamSseJsonEvents(url, signal);
}

async function* streamSseJsonEvents(url: string, signal?: AbortSignal): AsyncGenerator<RunStreamEvent> {
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
      throw new Error("Job event stream unavailable.");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const event = parseSseEvent(part);
        if (!event) continue;
        yield event;
      }

      if (done) {
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
    (parsed as Record<string, unknown>)._raw = payload;

    if (sseEvent && !(parsed as Record<string, unknown>).event && !(parsed as Record<string, unknown>).type) {
      (parsed as Record<string, unknown>).event = sseEvent;
    }

    if (sseId && (parsed as Record<string, unknown>).sequence === undefined) {
      const numeric = Number(sseId);
      if (Number.isFinite(numeric)) {
        (parsed as Record<string, unknown>).sequence = numeric;
      } else {
        (parsed as Record<string, unknown>).sse_id = sseId;
      }
    }

    return parsed;
  } catch {
    return null;
  }
}

