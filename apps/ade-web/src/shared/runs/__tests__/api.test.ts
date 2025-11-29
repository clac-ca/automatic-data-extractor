import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { streamRunEvents } from "@shared/runs/api";
import type { AdeEvent } from "@shared/runs/types";

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

  emit(type: string, data: unknown) {
    const event = new MessageEvent(type, { data });
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

    await iterator.return?.();
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
