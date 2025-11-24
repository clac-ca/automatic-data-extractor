import { post } from "@shared/api";
import { client } from "@shared/api/client";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { ArtifactV1 } from "@schema";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

import type { components } from "@schema";

import type { RunStreamEvent } from "./types";

export type RunOutputListing = components["schemas"]["RunOutputListing"];

export interface RunStreamOptions {
  readonly dry_run?: boolean;
  readonly validate_only?: boolean;
  readonly input_document_id?: string;
  readonly input_sheet_name?: string;
  readonly input_sheet_names?: readonly string[];
}

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const path = `/configs/${encodeURIComponent(configId)}/runs`;
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

export async function fetchRunArtifact(
  runId: string,
  signal?: AbortSignal,
): Promise<ArtifactV1> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/artifact`, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run artifact unavailable");
  }

  return (await response.json()) as ArtifactV1;
}

export async function fetchRunTelemetry(
  runId: string,
  signal?: AbortSignal,
): Promise<TelemetryEnvelope[]> {
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
        return JSON.parse(line) as TelemetryEnvelope;
      } catch (error) {
        console.warn("Skipping invalid telemetry line", { error, line });
        return null;
      }
    })
    .filter((value): value is TelemetryEnvelope => Boolean(value));
}
