import type { RunStreamEvent } from "@/types/runs";

export type RunStreamConnectionState = "connecting" | "streaming" | "reconnecting" | "completed" | "failed";

export interface EventSourceRunStreamOptions {
  readonly afterSequence?: number;
  readonly signal?: AbortSignal;
  readonly onConnectionStateChange?: (state: RunStreamConnectionState) => void;
}

type QueueItem =
  | { readonly kind: "event"; readonly event: RunStreamEvent }
  | { readonly kind: "complete" }
  | { readonly kind: "aborted" }
  | { readonly kind: "failed"; readonly error: Error };

type EndPayload = {
  readonly cursor?: number | string;
};

function createQueue<T>() {
  const items: T[] = [];
  const waiters: Array<(value: T) => void> = [];

  return {
    push(value: T) {
      const waiter = waiters.shift();
      if (waiter) {
        waiter(value);
        return;
      }
      items.push(value);
    },
    async next(): Promise<T> {
      const item = items.shift();
      if (item !== undefined) {
        return item;
      }
      return await new Promise<T>((resolve) => {
        waiters.push(resolve);
      });
    },
  };
}

function normalizeCursor(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value));
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.max(0, Math.floor(parsed)) : 0;
  }
  return 0;
}

function appendCursor(url: string, cursor: number): string {
  if (!Number.isFinite(cursor) || cursor <= 0) {
    return url;
  }
  const hasQuery = url.includes("?");
  return `${url}${hasQuery ? "&" : "?"}cursor=${Math.floor(cursor)}`;
}

function parseRunEvent(rawLine: string): RunStreamEvent | null {
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
  } catch {
    return null;
  }
}

function ensureEventSource(): typeof EventSource {
  const ctor = globalThis.EventSource;
  if (typeof ctor !== "function") {
    throw new Error("EventSource is unavailable in this environment.");
  }
  return ctor;
}

export async function* streamRunEventsWithEventSource(
  url: string,
  options: EventSourceRunStreamOptions = {},
): AsyncGenerator<RunStreamEvent> {
  const queue = createQueue<QueueItem>();
  let closed = false;
  let cursor = normalizeCursor(options.afterSequence);

  const EventSourceCtor = ensureEventSource();
  options.onConnectionStateChange?.("connecting");
  const source = new EventSourceCtor(appendCursor(url, cursor), {
    withCredentials: true,
  });

  const close = () => {
    if (closed) return;
    closed = true;
    source.close();
    options.signal?.removeEventListener("abort", onAbort);
  };

  const onAbort = () => {
    queue.push({ kind: "aborted" });
  };

  const handleOpen = () => {
    options.onConnectionStateChange?.("streaming");
  };

  const handleReady = (event: MessageEvent) => {
    const eventCursor = normalizeCursor(event.lastEventId);
    if (eventCursor > cursor) {
      cursor = eventCursor;
    }
  };

  const handleMessage = (event: MessageEvent) => {
    if (typeof event.data !== "string") {
      return;
    }
    const parsed = parseRunEvent(event.data);
    if (!parsed) {
      return;
    }

    const nextCursor = normalizeCursor(event.lastEventId);
    if (nextCursor > cursor) {
      cursor = nextCursor;
    }

    const withEventId =
      nextCursor > 0 && (!parsed.event_id || !String(parsed.event_id).trim())
        ? { ...parsed, event_id: String(nextCursor) }
        : parsed;
    queue.push({ kind: "event", event: withEventId });
  };

  const handleEnd = (event: MessageEvent) => {
    if (typeof event.data === "string") {
      try {
        const payload = JSON.parse(event.data) as EndPayload;
        const payloadCursor = normalizeCursor(payload?.cursor);
        if (payloadCursor > cursor) {
          cursor = payloadCursor;
        }
      } catch {
        // Best-effort control payload parsing.
      }
    }

    const nextCursor = normalizeCursor(event.lastEventId);
    if (nextCursor > cursor) {
      cursor = nextCursor;
    }

    options.onConnectionStateChange?.("completed");
    queue.push({ kind: "complete" });
  };

  const handleError = () => {
    if (closed) {
      return;
    }

    if (source.readyState === EventSource.CONNECTING) {
      options.onConnectionStateChange?.("reconnecting");
      return;
    }

    options.onConnectionStateChange?.("failed");
    queue.push({ kind: "failed", error: new Error("Run events stream disconnected.") });
  };

  source.addEventListener("open", handleOpen);
  source.addEventListener("ready", handleReady);
  source.addEventListener("message", handleMessage);
  source.addEventListener("end", handleEnd);
  source.addEventListener("error", handleError);

  if (options.signal) {
    if (options.signal.aborted) {
      close();
      throw new DOMException("Aborted", "AbortError");
    }
    options.signal.addEventListener("abort", onAbort, { once: true });
  }

  try {
    while (true) {
      const item = await queue.next();
      if (item.kind === "event") {
        yield item.event;
        continue;
      }
      if (item.kind === "complete") {
        return;
      }
      if (item.kind === "aborted") {
        throw new DOMException("Aborted", "AbortError");
      }
      throw item.error;
    }
  } finally {
    close();
  }
}
