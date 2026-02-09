import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import {
  cancelRun,
  createRun,
  createRunsBatch,
  runEventsUrl,
  streamRunEvents,
  streamRunEventsForRun,
} from "@/api/runs/api";
import type { RunResource } from "@/api/runs/api";
import type { RunStreamEvent } from "@/types/runs";

const originalEventSource = globalThis.EventSource;

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];

  readonly url: string;
  readonly withCredentials: boolean;
  readyState = MockEventSource.CONNECTING;

  private readonly listeners = new Map<string, Set<(event: Event) => void>>();
  private closed = false;

  constructor(url: string | URL, init?: EventSourceInit) {
    this.url = String(url);
    this.withCredentials = Boolean(init?.withCredentials);
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const handler = normalizeListener(listener);
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)?.add(handler);
  }

  removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const handler = normalizeListener(listener);
    this.listeners.get(type)?.delete(handler);
  }

  close() {
    this.closed = true;
    this.readyState = MockEventSource.CLOSED;
  }

  emitOpen() {
    this.readyState = MockEventSource.OPEN;
    this.emit("open", new Event("open"));
  }

  emitError(readyState = MockEventSource.CONNECTING) {
    this.readyState = readyState;
    this.emit("error", new Event("error"));
  }

  emitReady(data: unknown, lastEventId = "") {
    this.emit(
      "ready",
      new MessageEvent("ready", {
        data: JSON.stringify(data),
        lastEventId,
      }),
    );
  }

  emitMessage(data: string, lastEventId = "") {
    this.emit(
      "message",
      new MessageEvent("message", {
        data,
        lastEventId,
      }),
    );
  }

  emitEnd(data: unknown, lastEventId = "") {
    this.emit(
      "end",
      new MessageEvent("end", {
        data: JSON.stringify(data),
        lastEventId,
      }),
    );
  }

  private emit(type: string, event: Event) {
    if (this.closed) {
      return;
    }
    const listeners = this.listeners.get(type);
    if (!listeners) {
      return;
    }
    for (const listener of listeners) {
      listener(event);
    }
  }
}

function normalizeListener(listener: EventListenerOrEventListenerObject): (event: Event) => void {
  if (typeof listener === "function") {
    return listener;
  }
  return (event) => listener.handleEvent(event);
}

const sampleRunResource = {
  id: "run-123",
  object: "ade.run",
  workspace_id: "ws-1",
  configuration_id: "config-123",
  operation: "process",
  status: "queued",
  created_at: "2025-01-01T00:00:00Z",
  links: {
    self: "/api/v1/workspaces/ws-1/runs/run-123",
    events_stream: "/api/v1/workspaces/ws-1/runs/run-123/events/stream",
    events_download: "/api/v1/workspaces/ws-1/runs/run-123/events/download",
    input_download: "/api/v1/workspaces/ws-1/runs/run-123/input/download",
    output_download: "/api/v1/workspaces/ws-1/runs/run-123/output/download",
    output_metadata: "/api/v1/workspaces/ws-1/runs/run-123/output",
  },
} satisfies RunResource;

type CreateRunPostResponse = Awaited<ReturnType<typeof client.POST>>;

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  MockEventSource.instances = [];
  globalThis.EventSource = originalEventSource;
});

beforeEach(() => {
  MockEventSource.instances = [];
  globalThis.EventSource = MockEventSource as unknown as typeof EventSource;
});

describe("streamRunEvents", () => {
  it("streams NDJSON message events and completes on end control event", async () => {
    const runEvent: RunStreamEvent = { event: "engine.phase.start", timestamp: "2025-01-01T00:00:00Z" };

    const iterator = streamRunEvents("http://example.com/stream");
    const streamPromise = (async () => {
      const events: RunStreamEvent[] = [];
      for await (const evt of iterator) {
        events.push(evt);
      }
      return events;
    })();

    const source = MockEventSource.instances[0];
    expect(source).toBeDefined();
    source.emitOpen();
    source.emitReady({ runId: "run-123", status: "running", cursor: 0 });
    source.emitMessage(JSON.stringify(runEvent), "10");
    source.emitEnd({ runId: "run-123", status: "succeeded", cursor: 10, reason: "run_complete" }, "10");

    const events = await streamPromise;
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ ...runEvent, event_id: "10" });
  });

  it("adds reconnecting connection state when EventSource reports reconnect", async () => {
    const states: string[] = [];

    const iterator = streamRunEvents("http://example.com/stream", {
      onConnectionStateChange: (state) => states.push(state),
    });
    const streamPromise = (async () => {
      const events: RunStreamEvent[] = [];
      for await (const evt of iterator) {
        events.push(evt);
      }
      return events;
    })();

    const source = MockEventSource.instances[0];
    source.emitOpen();
    source.emitError(MockEventSource.CONNECTING);
    source.emitMessage(
      JSON.stringify({ event: "run.start", timestamp: "2025-01-01T00:00:00Z" } satisfies RunStreamEvent),
      "5",
    );
    source.emitEnd({ runId: "run-123", status: "succeeded", cursor: 5, reason: "run_complete" }, "5");

    const events = await streamPromise;
    expect(events.map((event) => event.event)).toEqual(["run.start"]);
    expect(states).toEqual(expect.arrayContaining(["connecting", "streaming", "reconnecting", "completed"]));
  });

  it("fails when stream closes with non-reconnecting error", async () => {
    const states: string[] = [];

    const iterator = streamRunEvents("http://example.com/stream", {
      onConnectionStateChange: (state) => states.push(state),
    });
    const streamPromise = (async () => {
      const events: RunStreamEvent[] = [];
      for await (const evt of iterator) {
        events.push(evt);
      }
      return events;
    })();

    const source = MockEventSource.instances[0];
    source.emitOpen();
    source.emitError(MockEventSource.CLOSED);

    await expect(streamPromise).rejects.toThrow("Run events stream disconnected.");
    expect(states).toContain("failed");
  });

  it("appends cursor query when afterSequence is provided", async () => {
    const iterator = streamRunEvents("http://example.com/stream", { afterSequence: 42 });
    const streamPromise = (async () => {
      for await (const _ of iterator) {
        // consume until complete
      }
    })();

    const source = MockEventSource.instances[0];
    expect(source.url).toContain("cursor=42");
    source.emitEnd({ runId: "run-123", status: "succeeded", cursor: 42, reason: "run_complete" }, "42");
    await streamPromise;
  });
});

describe("createRun", () => {
  it("posts defaults and returns the created run resource", async () => {
    const postResponse = {
      data: sampleRunResource,
      response: new Response(JSON.stringify(sampleRunResource), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    const run = await createRun(
      "workspace-123",
      {
        dry_run: true,
        input_document_id: "doc-123",
        configuration_id: "config-123",
      },
      undefined,
    );

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs", {
      params: { path: { workspaceId: "workspace-123" } },
      body: {
        input_document_id: "doc-123",
        configuration_id: "config-123",
        options: {
          operation: "process",
          dry_run: true,
          log_level: "INFO",
          active_sheet_only: false,
        },
      },
      signal: undefined,
    });
    expect(run).toEqual(sampleRunResource);
  });

  it("throws when run creation does not return data", async () => {
    const postResponse = {
      error: {},
      response: new Response(null, { status: 200 }),
    } as unknown as CreateRunPostResponse;
    vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await expect(createRun("workspace-123", { input_document_id: "doc-123" })).rejects.toThrow(
      "Expected run creation response.",
    );
  });

  it("allows validation runs without an input document", async () => {
    const postResponse = {
      data: sampleRunResource,
      response: new Response(JSON.stringify(sampleRunResource), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await createRun(
      "workspace-123",
      {
        operation: "validate",
        configuration_id: "config-123",
      },
      undefined,
    );

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs", {
      params: { path: { workspaceId: "workspace-123" } },
      body: {
        input_document_id: undefined,
        configuration_id: "config-123",
        options: {
          operation: "validate",
          dry_run: false,
          log_level: "INFO",
          active_sheet_only: false,
        },
      },
      signal: undefined,
    });
  });

  it("supports publish runs through workspace run creation", async () => {
    const postResponse = {
      data: { ...sampleRunResource, operation: "publish" },
      response: new Response(JSON.stringify(sampleRunResource), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await createRun(
      "workspace-123",
      {
        operation: "publish",
        configuration_id: "config-123",
      },
      undefined,
    );

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs", {
      params: { path: { workspaceId: "workspace-123" } },
      body: {
        input_document_id: undefined,
        configuration_id: "config-123",
        options: {
          operation: "publish",
          dry_run: false,
          log_level: "INFO",
          active_sheet_only: false,
        },
      },
      signal: undefined,
    });
  });
});

describe("createRunsBatch", () => {
  it("posts deduped document ids and returns created run resources", async () => {
    const batchResource = { ...sampleRunResource, id: "run-batch-1" } satisfies RunResource;
    const postResponse = {
      data: { runs: [batchResource] },
      response: new Response(JSON.stringify({ runs: [batchResource] }), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    const runs = await createRunsBatch(
      "workspace-123",
      ["doc-1", "doc-1", "doc-2"],
      { active_sheet_only: true, configuration_id: "config-123" },
      undefined,
    );

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs/batch", {
      params: { path: { workspaceId: "workspace-123" } },
      body: {
        document_ids: ["doc-1", "doc-2"],
        configuration_id: "config-123",
        options: {
          operation: "process",
          dry_run: false,
          log_level: "INFO",
          active_sheet_only: true,
        },
      },
      signal: undefined,
    });
    expect(runs).toEqual([batchResource]);
  });

  it("returns an empty array without calling the API when no document ids are provided", async () => {
    const postSpy = vi.spyOn(client, "POST");

    const runs = await createRunsBatch("workspace-123", [], {});

    expect(runs).toEqual([]);
    expect(postSpy).not.toHaveBeenCalled();
  });
});

describe("cancelRun", () => {
  it("posts cancel and returns the updated run", async () => {
    const cancelled = { ...sampleRunResource, status: "cancelled" } satisfies RunResource;
    const postResponse = {
      data: cancelled,
      response: new Response(JSON.stringify(cancelled), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    const run = await cancelRun("workspace-123", "run-123");

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs/{runId}/cancel", {
      params: { path: { workspaceId: "workspace-123", runId: "run-123" } },
    });
    expect(run).toEqual(cancelled);
  });

  it("throws when cancellation does not return data", async () => {
    const postResponse = {
      error: {},
      response: new Response(null, { status: 200 }),
    } as unknown as CreateRunPostResponse;
    vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await expect(cancelRun("workspace-123", "run-123")).rejects.toThrow("Expected run cancellation response.");
  });
});

describe("runEventsUrl helpers", () => {
  it("builds event stream URLs", () => {
    const url = runEventsUrl(sampleRunResource, { afterSequence: 42 });
    expect(url).toContain("/api/v1/workspaces/ws-1/runs/run-123/events/stream");
    expect(url).toContain("cursor=42");
  });

  it("streams events for a run resource", async () => {
    const completedRun = { ...sampleRunResource, status: "succeeded" } satisfies RunResource;
    const iterator = streamRunEventsForRun("ws-1", completedRun, { afterSequence: 3 });
    const streamPromise = (async () => {
      const events: RunStreamEvent[] = [];
      for await (const event of iterator) {
        events.push(event);
      }
      return events;
    })();

    const source = MockEventSource.instances[0];
    expect(source.url).toContain("/api/v1/workspaces/ws-1/runs/run-123/events/stream");
    expect(source.url).toContain("cursor=3");
    source.emitOpen();
    source.emitMessage(
      JSON.stringify({ event: "run.start", timestamp: "2025-01-01T00:00:00Z" } satisfies RunStreamEvent),
      "3",
    );
    source.emitEnd({ runId: "run-123", status: "succeeded", cursor: 3, reason: "run_complete" }, "3");

    const events = await streamPromise;
    expect(events.map((event) => event.event)).toEqual(["run.start"]);
  });

  it("throws when run stream link is missing", async () => {
    const runWithoutStream = {
      ...sampleRunResource,
      links: {
        ...sampleRunResource.links,
        events_stream: "",
      },
    } satisfies RunResource;

    await expect(async () => {
      const iterator = streamRunEventsForRun("ws-1", runWithoutStream);
      await iterator.next();
    }).rejects.toThrow("Run events stream is unavailable.");
  });
});
