import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shared/api/client";
import { runEventsUrl, streamRun, streamRunEvents, streamRunEventsForRun } from "@shared/runs/api";
import type { RunResource } from "@shared/runs/api";
import type { AdeEvent } from "@shared/runs/types";

const encoder = new TextEncoder();

function createSseStream() {
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(ctrl) {
      controller = ctrl;
    },
  });
  return {
    stream,
    emit(event: AdeEvent) {
      const payload = `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
      controller?.enqueue(encoder.encode(payload));
    },
    close() {
      controller?.close();
    },
  };
}

function mockSseFetch() {
  const sse = createSseStream();
  const response = new Response(sse.stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
  return { sse, fetchMock };
}

const sampleRunResource = {
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
    events_stream: "/api/v1/runs/run-123/events/stream",
    logs: "/api/v1/runs/run-123/logs",
    outputs: "/api/v1/runs/run-123/outputs",
  },
} satisfies RunResource;

type CreateRunPostResponse = Awaited<
  ReturnType<typeof client.POST<"/api/v1/configurations/{configuration_id}/runs">>
>;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamRunEvents", () => {
  it("consumes any SSE event type", async () => {
    const { sse } = mockSseFetch();
    const iterator = streamRunEvents("http://example.com/stream");

    const pending = iterator.next();
    await Promise.resolve();

    const runEvent: AdeEvent = { type: "engine.phase.start", created_at: "2025-01-01T00:00:00Z" };
    sse.emit(runEvent);

    const result = await pending;
    expect(result.done).toBe(false);
    expect(result.value).toEqual(runEvent);

    await iterator.return?.(undefined);
    sse.close();
  });

  it("closes the stream after run completion", async () => {
    const { sse } = mockSseFetch();
    const iterator = streamRunEvents("http://example.com/stream");

    const first = iterator.next();
    await Promise.resolve();

    const startEvent: AdeEvent = { type: "run.start", created_at: "2025-01-01T00:00:00Z" };
    const completedEvent: AdeEvent = {
      type: "run.complete",
      created_at: "2025-01-01T00:05:00Z",
      payload: { status: "succeeded" },
    };

    sse.emit(startEvent);
    expect((await first).value).toEqual(startEvent);

    const second = iterator.next();
    sse.emit(completedEvent);
    expect((await second).value).toEqual(completedEvent);

    sse.close();
    const done = await iterator.next();
    expect(done.done).toBe(true);
  });
});

describe("streamRun", () => {
  it("creates a run via the typed client and streams events", async () => {
    const { sse, fetchMock } = mockSseFetch();
    const runEvent: AdeEvent = {
      type: "run.complete",
      created_at: "2025-01-01T00:05:00Z",
      run_id: "run-123",
    };
    const events: AdeEvent[] = [];
    const postResponse: CreateRunPostResponse = {
      data: sampleRunResource,
      error: undefined,
      response: new Response(JSON.stringify(sampleRunResource), { status: 200 }),
    };
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    const stream = streamRun("config-123", { dry_run: true });
    const consume = (async () => {
      for await (const event of stream) {
        events.push(event);
      }
    })();

    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalled();
    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/v1/runs/run-123/events/stream");
    expect(String(url)).toContain("after_sequence=0");

    sse.emit(runEvent);

    await consume;

    expect(postSpy).toHaveBeenCalledWith("/api/v1/configurations/{configuration_id}/runs", {
      params: { path: { configuration_id: "config-123" } },
      body: { options: { dry_run: true, validate_only: false, force_rebuild: false } },
      signal: undefined,
    });
    expect(events).toEqual([runEvent]);
    sse.close();
  });

  it("throws when run creation does not return data", async () => {
    const postResponse: CreateRunPostResponse = {
      data: undefined,
      error: undefined,
      response: new Response(null, { status: 200 }),
    };
    vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await expect(streamRun("config-123").next()).rejects.toThrow("Expected run creation response.");
  });
});

describe("runEventsUrl helpers", () => {
  it("builds streaming event URLs with sequence parameters", () => {
    const legacyRun = {
      ...sampleRunResource,
      links: { ...sampleRunResource.links, events_stream: undefined },
    } as unknown as RunResource;

    const url = runEventsUrl(legacyRun, { afterSequence: 42, stream: true });
    expect(url).toContain("/api/v1/runs/run-123/events");
    expect(url).toContain("stream=true");
    expect(url).toContain("after_sequence=42");
  });

  it("streams events for an existing run resource", async () => {
    const { sse, fetchMock } = mockSseFetch();
    const iterator = streamRunEventsForRun(sampleRunResource, { afterSequence: 3 });
    const pending = iterator.next();
    await Promise.resolve();

    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/v1/runs/run-123/events/stream");
    expect(String(url)).toContain("after_sequence=3");

    const runEvent: AdeEvent = { type: "run.start", created_at: "2025-01-01T00:00:00Z" };
    sse.emit(runEvent);
    const result = await pending;
    expect(result.value).toEqual(runEvent);
    await iterator.return?.(undefined);
    sse.close();
  });
});
