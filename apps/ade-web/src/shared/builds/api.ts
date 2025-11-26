import { post } from "@shared/api";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { BuildEvent } from "./types";

export interface BuildStreamOptions {
  readonly force?: boolean;
  readonly wait?: boolean;
}

export async function* streamBuild(
  workspaceId: string,
  configId: string,
  options: BuildStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<BuildEvent> {
  const path = `/workspaces/${encodeURIComponent(workspaceId)}/configurations/${encodeURIComponent(configId)}/builds`;
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

  for await (const event of parseNdjsonStream<BuildEvent>(response)) {
    yield event;
  }
}
