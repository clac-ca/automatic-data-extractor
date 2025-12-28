import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shared/api/client";
import { runEventsUrl, streamRun, streamRunEvents, streamRunEventsForRun } from "@shared/runs/api";
import type { RunResource } from "@shared/runs/api";
import type { RunStreamEvent } from "@shared/runs/types";

const encoder = new TextEncoder();

function createSseStream() {
  let closed = false;
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(ctrl) {
      controller = ctrl;
    },
  });
  return {
    stream,
    emit(event: RunStreamEvent) {
      if (closed) return;
      const payload = `event: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`;
      controller?.enqueue(encoder.encode(payload));
    },
    close() {
      if (closed) return;
      closed = true;
      try {
        controller?.close();
      } catch {
        // stream already closed
      }
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
  build_id: "build-123",
  status: "queued",
  created_at: "2025-01-01T00:00:00Z",
  links: {
    self: "/api/v1/runs/run-123",
    events: "/api/v1/runs/run-123/events",
    events_stream: "/api/v1/runs/run-123/events/stream",
    events_download: "/api/v1/runs/run-123/events/download",
    logs: "/api/v1/runs/run-123/logs",
    input: "/api/v1/runs/run-123/input",
    input_download: "/api/v1/runs/run-123/input/download",
    output: "/api/v1/runs/run-123/output",
    output_download: "/api/v1/runs/run-123/output/download",
    output_metadata: "/api/v1/runs/run-123/output/metadata",
  },
} satisfies RunResource;

type CreateRunPostResponse = Awaited<
  ReturnType<typeof client.POST>
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

    const runEvent: RunStreamEvent = { event: "engine.phase.start", timestamp: "2025-01-01T00:00:00Z" };
    sse.emit(runEvent);

    const result = await pending;
    expect(result.done).toBe(false);
    expect(result.value).toMatchObject(runEvent);

    await iterator.return?.(undefined);
    sse.close();
  });

  it("closes the stream after run completion", async () => {
    const { sse } = mockSseFetch();
    const iterator = streamRunEvents("http://example.com/stream");

    const first = iterator.next();
    await Promise.resolve();

    const startEvent: RunStreamEvent = { event: "run.start", timestamp: "2025-01-01T00:00:00Z" };
    const completedEvent: RunStreamEvent = {
      event: "run.complete",
      timestamp: "2025-01-01T00:05:00Z",
      data: { status: "succeeded" },
    };

    sse.emit(startEvent);
    expect((await first).value).toMatchObject(startEvent);

    const second = iterator.next();
    sse.emit(completedEvent);
    expect((await second).value).toMatchObject(completedEvent);

    sse.close();
    const done = await iterator.next();
    expect(done.done).toBe(true);
  });
});

describe("streamRun", () => {
  it("creates a run via the typed client and streams events", async () => {
    const { sse, fetchMock } = mockSseFetch();
    const runEvent: RunStreamEvent = {
      event: "run.complete",
      timestamp: "2025-01-01T00:05:00Z",
      data: { jobId: "run-123" },
    };
    const events: RunStreamEvent[] = [];
    const postResponse = {
      data: sampleRunResource,
      response: new Response(JSON.stringify(sampleRunResource), { status: 200 }),
    } as unknown as CreateRunPostResponse;
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    const stream = streamRun("workspace-123", {
      dry_run: true,
      input_document_id: "doc-123",
      configuration_id: "config-123",
    });
    const consume = (async () => {
      for await (const event of stream) {
        events.push(event);
      }
    })();

    await Promise.resolve();
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalled();
    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/v1/runs/run-123/events/stream");
    expect(String(url)).toContain("after_sequence=0");

    sse.emit(runEvent);

    await consume;

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspace_id}/runs", {
      params: { path: { workspace_id: "workspace-123" } },
      body: {
        input_document_id: "doc-123",
        configuration_id: "config-123",
        options: {
          dry_run: true,
          validate_only: false,
          force_rebuild: false,
          debug: false,
          log_level: "INFO",
        },
      },
      signal: undefined,
    });
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject(runEvent);
    sse.close();
  });

  it("throws when run creation does not return data", async () => {
    const postResponse = {
      error: {},
      response: new Response(null, { status: 200 }),
    } as unknown as CreateRunPostResponse;
    vi.spyOn(client, "POST").mockResolvedValue(postResponse);

    await expect(streamRun("workspace-123", { input_document_id: "doc-123" }).next()).rejects.toThrow(
      "Expected run creation response.",
    );
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

    const runEvent: RunStreamEvent = { event: "run.start", timestamp: "2025-01-01T00:00:00Z" };
    sse.emit(runEvent);
    const result = await pending;
    expect(result.value).toMatchObject(runEvent);
    await iterator.return?.(undefined);
    sse.close();
  });
});
