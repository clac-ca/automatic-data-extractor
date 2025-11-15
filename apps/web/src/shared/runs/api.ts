import { post } from "@shared/api";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { RunStreamEvent } from "./types";

export interface RunStreamOptions {
  readonly dry_run?: boolean;
  readonly validate_only?: boolean;
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
