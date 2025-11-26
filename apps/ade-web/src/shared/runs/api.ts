import { post } from "@shared/api";
import { client } from "@shared/api/client";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { RunSummaryV1, components } from "@schema";
import type { AdeEvent as RunStreamEvent } from "./types";

export type RunResource = components["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunOutputListing = components["schemas"]["RunOutputListing"];
export type RunCreateOptions = components["schemas"]["RunCreateOptions"];

export interface RunStreamOptions {
  readonly dry_run?: boolean;
  readonly validate_only?: boolean;
   readonly force_rebuild?: boolean;
  readonly input_document_id?: string;
  readonly input_sheet_name?: string;
  readonly input_sheet_names?: readonly string[];
}

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const path = `/configurations/${encodeURIComponent(configId)}/runs`;
  const response = await post<Response>(
    path,
    { stream: true, options },
    {
      parseJson: false,
      returnRawResponse: true,
      headers: { Accept: "application/x-ndjson" },
      signal,
    },
  );

  for await (const event of parseNdjsonStream<RunStreamEvent>(response)) {
    yield event;
  }
}

export async function fetchRunOutputs(
  runId: string,
  signal?: AbortSignal,
): Promise<RunOutputListing> {
  const { data } = await client.GET("/api/v1/runs/{run_id}/outputs", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (!data) throw new Error("Run outputs unavailable");
  return data as RunOutputListing;
}

export async function fetchRunTelemetry(
  runId: string,
  signal?: AbortSignal,
): Promise<RunStreamEvent[]> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/logfile`, {
    headers: { Accept: "application/x-ndjson" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run telemetry unavailable");
  }

  const text = await response.text();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as RunStreamEvent;
      } catch (error) {
        console.warn("Skipping invalid telemetry line", { error, line });
        return null;
      }
    })
    .filter((value): value is RunStreamEvent => Boolean(value));
}

export async function fetchRun(
  runId: string,
  signal?: AbortSignal,
): Promise<RunResource> {
  const { data } = await client.GET("/api/v1/runs/{run_id}", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (!data) throw new Error("Run not found");
  return data as RunResource;
}

export async function fetchRunSummary(runId: string, signal?: AbortSignal): Promise<RunSummaryV1 | null> {
  const run = await fetchRun(runId, signal);
  const summary = run.summary;
  if (!summary) return null;
  if (typeof summary === "string") {
    try {
      return JSON.parse(summary) as RunSummaryV1;
    } catch (error) {
      console.warn("Unable to parse run summary", { error });
      return null;
    }
  }
  return summary as RunSummaryV1;
}

export const runQueryKeys = {
  detail: (runId: string) => ["run", runId] as const,
  outputs: (runId: string) => ["run-outputs", runId] as const,
  telemetry: (runId: string) => ["run-telemetry", runId] as const,
  summary: (runId: string) => ["run-summary", runId] as const,
};
