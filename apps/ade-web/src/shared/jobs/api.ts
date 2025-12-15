import { resolveApiUrl } from "@shared/api/client";

import type { RunStreamOptions } from "@shared/runs/api";

export type JobStreamMetaEvent = {
  readonly id?: number;
  readonly ts?: string;
  readonly scope?: string;
  readonly level?: string;
  readonly text?: string;
  readonly details?: Record<string, unknown>;
};

export type JobStreamDoneEvent = {
  readonly id?: number;
  readonly ts?: string;
  readonly scope?: string;
  readonly level?: string;
  readonly text?: string;
  readonly details?: Record<string, unknown>;
};

export type JobStreamLogLine = {
  readonly scope: "run" | "build";
  readonly level: "debug" | "info" | "warning" | "error" | "success";
  readonly ts: string;
  readonly message: string;
};

export type JobStreamMessage =
  | { readonly type: "meta"; readonly event: JobStreamMetaEvent }
  | { readonly type: "log"; readonly line: JobStreamLogLine }
  | { readonly type: "done"; readonly event: JobStreamDoneEvent };

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

function parseLogPayload(raw: string): JobStreamLogLine | null {
  const first = raw.indexOf("\t");
  if (first < 0) return null;
  const second = raw.indexOf("\t", first + 1);
  if (second < 0) return null;
  const third = raw.indexOf("\t", second + 1);
  if (third < 0) return null;

  const scopeRaw = raw.slice(0, first).trim().toLowerCase();
  const levelRaw = raw.slice(first + 1, second).trim().toLowerCase();
  const ts = raw.slice(second + 1, third).trim();
  const message = raw.slice(third + 1);

  const scope: JobStreamLogLine["scope"] = scopeRaw === "build" ? "build" : "run";
  const level: JobStreamLogLine["level"] =
    levelRaw === "debug" || levelRaw === "warning" || levelRaw === "error" || levelRaw === "success"
      ? (levelRaw as JobStreamLogLine["level"])
      : "info";

  if (!ts || !message.trim()) return null;
  return { scope, level, ts, message };
}

export async function* streamConfigurationJob(
  configurationId: string,
  options: RunStreamOptions,
  signal?: AbortSignal,
): AsyncGenerator<JobStreamMessage> {
  const abortError =
    typeof DOMException !== "undefined"
      ? new DOMException("Aborted", "AbortError")
      : Object.assign(new Error("Aborted"), { name: "AbortError" });

  const url = buildJobStreamUrl(configurationId, options);
  const queue: JobStreamMessage[] = [];
  let done = false;
  let failure: unknown = null;
  let pendingResolve: ((value: IteratorResult<JobStreamMessage>) => void) | null = null;

  const es = new EventSource(url, { withCredentials: true });

  const close = (error?: unknown) => {
    if (done) return;
    done = true;
    failure = error ?? null;
    try {
      es.close();
    } catch {
      // ignore close errors
    }
    if (pendingResolve) {
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve({ value: undefined as unknown as JobStreamMessage, done: true });
    }
  };

  const abortHandler = () => close(abortError);
  if (signal?.aborted) {
    close(abortError);
  } else if (signal) {
    signal.addEventListener("abort", abortHandler);
  }

  const enqueue = (msg: JobStreamMessage) => {
    if (pendingResolve) {
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve({ value: msg, done: false });
      return;
    }
    queue.push(msg);
  };

  es.addEventListener("meta", (evt) => {
    const raw = typeof (evt as MessageEvent).data === "string" ? (evt as MessageEvent).data : "";
    if (!raw.trim()) return;
    try {
      enqueue({ type: "meta", event: JSON.parse(raw) as JobStreamMetaEvent });
    } catch {
      // ignore malformed meta
    }
  });

  es.addEventListener("log", (evt) => {
    const raw = typeof (evt as MessageEvent).data === "string" ? (evt as MessageEvent).data : "";
    if (!raw.trim()) return;
    const parsed = parseLogPayload(raw);
    if (!parsed) return;
    enqueue({ type: "log", line: parsed });
  });

  es.addEventListener("done", (evt) => {
    const raw = typeof (evt as MessageEvent).data === "string" ? (evt as MessageEvent).data : "";
    if (!raw.trim()) return;
    try {
      enqueue({ type: "done", event: JSON.parse(raw) as JobStreamDoneEvent });
      close();
    } catch {
      // ignore malformed done
    }
  });

  es.onerror = () => {
    // Treat errors as terminal for now; this stream is one-shot and intentionally
    // does not attempt automatic resume.
    close(new Error("Job stream disconnected."));
  };

  try {
    while (true) {
      if (queue.length) {
        yield queue.shift()!;
        continue;
      }
      if (done) {
        if (failure) throw failure;
        return;
      }
      const result = await new Promise<IteratorResult<JobStreamMessage>>((resolve) => {
        pendingResolve = resolve;
      });
      if (result.done) {
        if (failure) throw failure;
        return;
      }
      yield result.value;
    }
  } finally {
    close();
    if (signal) {
      signal.removeEventListener("abort", abortHandler);
    }
  }
}

