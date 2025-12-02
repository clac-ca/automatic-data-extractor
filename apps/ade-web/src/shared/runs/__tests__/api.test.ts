import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamRun, streamRunEvents } from "@shared/runs/api";
import type { RunResource } from "@shared/runs/api";
import type { AdeEvent } from "@shared/runs/types";
import { client } from "@shared/api/client";

class MockEventSource {
  static instances: MockEventSource[] = [];

  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  readonly listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>();
  closed = false;

  constructor(readonly url: string, readonly options?: EventSourceInit) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    const existing = this.listeners.get(type) ?? [];
    this.listeners.set(type, [...existing, listener]);
  }

  removeEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    const existing = this.listeners.get(type);
    if (!existing) return;
    this.listeners.set(
      type,
      existing.filter((entry) => entry !== listener),
    );
  }

  emit(type: string, data: string) {
    const event = new MessageEvent<string>(type, { data });
    if (type === "message" && this.onmessage) {
      this.onmessage(event);
    }
    const listeners = this.listeners.get(type) ?? [];
    listeners.forEach((listener) => listener(event));
  }

  fail(error?: Event) {
    this.onerror?.(error ?? new Event("error"));
  }

  close() {
    this.closed = true;
  }
}

const OriginalEventSource = globalThis.EventSource;

describe("streamRunEvents", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    (globalThis as unknown as { EventSource: typeof EventSource }).EventSource = OriginalEventSource;
    MockEventSource.instances = [];
    vi.restoreAllMocks();
  });

  it("consumes named ade.event messages", async () => {
    const iterator = streamRunEvents("http://example.com/stream");
    const pending = iterator.next();
    const source = MockEventSource.instances.at(-1);
    expect(source).toBeDefined();

    const runEvent: AdeEvent = { type: "run.started", created_at: "2025-01-01T00:00:00Z" };
    source?.emit("ade.event", JSON.stringify(runEvent));

    const result = await pending;
    expect(result.done).toBe(false);
    expect(result.value).toEqual(runEvent);

    await iterator.return?.(undefined);
  });

  it("closes the stream after run completion", async () => {
    const iterator = streamRunEvents("http://example.com/stream");
    const first = iterator.next();
    const source = MockEventSource.instances.at(-1);
    expect(source).toBeDefined();

    const startEvent: AdeEvent = { type: "run.started", created_at: "2025-01-01T00:00:00Z" };
    const completedEvent: AdeEvent = {
      type: "run.completed",
      created_at: "2025-01-01T00:05:00Z",
      payload: { status: "succeeded" },
    };

    source?.emit("ade.event", JSON.stringify(startEvent));
    expect((await first).value).toEqual(startEvent);

    const second = iterator.next();
    source?.emit("ade.event", JSON.stringify(completedEvent));
    expect((await second).value).toEqual(completedEvent);

    const done = await iterator.next();
    expect(done.done).toBe(true);
    expect(source?.closed).toBe(true);
  });
});

describe("streamRun", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    (globalThis as unknown as { EventSource: typeof EventSource }).EventSource = OriginalEventSource;
    MockEventSource.instances = [];
    vi.restoreAllMocks();
  });

  it("creates a run via the typed client and streams events", async () => {
    const runResource = {
      id: "run-123",
      object: "ade.run",
      workspace_id: "ws-1",
      configuration_id: "config-123",
      status: "queued",
      created_at: "2025-01-01T00:00:00Z",
      links: {
        self: "/api/v1/runs/run-123",
        summary: "/api/v1/runs/run-123/summary",
        events: "/api/v1/runs/run-123/events",
        logs: "/api/v1/runs/run-123/logs",
        outputs: "/api/v1/runs/run-123/outputs",
      },
    } satisfies RunResource;

    const runEvent: AdeEvent = {
      type: "run.completed",
      created_at: "2025-01-01T00:05:00Z",
      run_id: "run-123",
    };
    const events: AdeEvent[] = [];
    const postResponse = {
      data: runResource,
      error: undefined,
      response: new Response(JSON.stringify(runResource), { status: 200 }),
    } as any;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse as any);

    const stream = streamRun("config-123", { dry_run: true });
    const consume = (async () => {
      for await (const event of stream) {
        events.push(event);
      }
    })();

    await Promise.resolve();
    const source = MockEventSource.instances.at(-1);
    expect(source).toBeDefined();

    source?.emit("ade.event", JSON.stringify(runEvent));

    await consume;

    expect(postSpy).toHaveBeenCalledWith("/api/v1/configurations/{configuration_id}/runs", {
      params: { path: { configuration_id: "config-123" } },
      body: { stream: false, options: { dry_run: true, validate_only: false, force_rebuild: false } },
      signal: undefined,
    });
    expect(source?.url).toContain("/api/v1/runs/run-123/events");
    expect(events).toEqual([runEvent]);
  });

  it("throws when run creation does not return data", async () => {
    const postResponse = {
      data: undefined,
      error: undefined,
      response: new Response(null, { status: 200 }),
    } as any;
    vi.spyOn(client, "POST").mockResolvedValue(postResponse as any);

    await expect(streamRun("config-123").next()).rejects.toThrow("Expected run creation response.");
  });
});
