import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { createRun, runEventsUrl, streamRunEvents, streamRunEventsForRun } from "@/api/runs/api";
import type { RunResource } from "@/api/runs/api";
import type { RunStreamEvent } from "@/types/runs";

const encoder = new TextEncoder();

function createSseStream(lineEnding = "\n") {
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
      const payload = `event: ${event.event}${lineEnding}data: ${JSON.stringify(event)}${lineEnding}${lineEnding}`;
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

function mockSseFetch(lineEnding?: string) {
  const sse = createSseStream(lineEnding);
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

  it("parses CRLF-delimited SSE events", async () => {
    const { sse } = mockSseFetch("\r\n");
    const iterator = streamRunEvents("http://example.com/stream");

    const pending = iterator.next();
    await Promise.resolve();

    const runEvent: RunStreamEvent = { event: "run.start", timestamp: "2025-01-01T00:00:00Z" };
    sse.emit(runEvent);

    const result = await pending;
    expect(result.done).toBe(false);
    expect(result.value).toMatchObject(runEvent);

    await iterator.return?.(undefined);
    sse.close();
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
      "idem-run-1",
    );

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/runs", {
      params: { path: { workspaceId: "workspace-123" } },
      body: {
        input_document_id: "doc-123",
        configuration_id: "config-123",
        options: {
          dry_run: true,
          validate_only: false,
          log_level: "INFO",
          active_sheet_only: false,
        },
      },
      headers: { "Idempotency-Key": "idem-run-1" },
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

    await expect(
      createRun("workspace-123", { input_document_id: "doc-123" }, undefined, "idem-run-2"),
    ).rejects.toThrow("Expected run creation response.");
  });
});

describe("runEventsUrl helpers", () => {
  it("builds streaming event URLs with sequence parameters", () => {
    const url = runEventsUrl(sampleRunResource, { afterSequence: 42 });
    expect(url).toContain("/api/v1/runs/run-123/events/stream");
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
