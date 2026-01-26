import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { createRun, runEventsUrl, streamRunEvents, streamRunEventsForRun } from "@/api/runs/api";
import type { RunResource } from "@/api/runs/api";
import type { RunStreamEvent } from "@/types/runs";

function mockNdjsonFetch(body: string) {
  const response = new Response(body, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson" },
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
  return { fetchMock };
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
    events_download: "/api/v1/runs/run-123/events/download",
    logs: "/api/v1/runs/run-123/events/download",
    input: "/api/v1/runs/run-123/input",
    input_download: "/api/v1/runs/run-123/input/download",
    output: "/api/v1/runs/run-123/output/download",
    output_download: "/api/v1/runs/run-123/output/download",
    output_metadata: "/api/v1/runs/run-123/output",
  },
} satisfies RunResource;

type CreateRunPostResponse = Awaited<
  ReturnType<typeof client.POST>
>;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamRunEvents", () => {
  it("parses NDJSON event streams", async () => {
    const runEvent: RunStreamEvent = { event: "engine.phase.start", timestamp: "2025-01-01T00:00:00Z" };
    const completedEvent: RunStreamEvent = {
      event: "run.complete",
      timestamp: "2025-01-01T00:05:00Z",
      data: { status: "succeeded" },
    };
    const payload = `${JSON.stringify(runEvent)}\n${JSON.stringify(completedEvent)}\n`;
    mockNdjsonFetch(payload);
    const iterator = streamRunEvents("http://example.com/stream");

    const events = [];
    for await (const evt of iterator) {
      events.push(evt);
    }

    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject(runEvent);
    expect(events[1]).toMatchObject(completedEvent);
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
  it("builds event download URLs", () => {
    const url = runEventsUrl(sampleRunResource, { afterSequence: 42 });
    expect(url).toContain("/api/v1/runs/run-123/events/download");
  });

  it("streams events for a completed run resource", async () => {
    const completedRun = { ...sampleRunResource, status: "succeeded" } satisfies RunResource;
    const runEvent: RunStreamEvent = { event: "run.start", timestamp: "2025-01-01T00:00:00Z" };
    const payload = `${JSON.stringify(runEvent)}\n`;
    const { fetchMock } = mockNdjsonFetch(payload);

    const iterator = streamRunEventsForRun(completedRun, { afterSequence: 3 });
    const result = await iterator.next();

    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/v1/runs/run-123/events/download");
    expect(result.value).toMatchObject(runEvent);
    await iterator.return?.(undefined);
  });
});
