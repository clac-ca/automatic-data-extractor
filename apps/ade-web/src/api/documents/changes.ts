import { ApiError, tryParseProblemDetails } from "@api/errors";
import { buildApiHeaders, client, resolveApiUrl } from "@api/client";
import type { FilterItem, FilterJoinOperator } from "@api/listing";
import { encodeFilters } from "@api/listing";

import type { components } from "@schema";

export type DocumentChangeEntry = components["schemas"]["DocumentChangeEntry"];
export type DocumentChangesPage = components["schemas"]["DocumentChangesPage"];
type DocumentChangesQuery = {
  cursor: string;
  limit?: number;
  sort?: string;
  filters?: FilterItem[];
  joinOperator?: FilterJoinOperator;
  q?: string;
};

export async function listDocumentChanges(
  workspaceId: string,
  options: DocumentChangesQuery,
  signal?: AbortSignal,
): Promise<DocumentChangesPage> {
  const query = {
    cursor: options.cursor,
    limit: options.limit,
    sort: options.sort,
    q: options.q,
    joinOperator: options.joinOperator,
    filters: encodeFilters(options.filters),
  };
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/changes", {
    params: { path: { workspaceId }, query },
    signal,
  });
  if (!data) {
    throw new Error("Expected document change feed payload.");
  }
  return data;
}

export function documentChangesStreamUrl(
  workspaceId: string,
  options: Omit<DocumentChangesQuery, "cursor"> & { cursor?: string } = {},
): string {
  const params = new URLSearchParams();
  if (options.cursor) params.set("cursor", options.cursor);
  if (typeof options.limit === "number") params.set("limit", String(options.limit));
  if (options.sort) params.set("sort", options.sort);
  if (options.q) params.set("q", options.q);
  if (options.joinOperator) params.set("joinOperator", options.joinOperator);
  const encodedFilters = encodeFilters(options.filters);
  if (encodedFilters) params.set("filters", encodedFilters);
  const query = params.toString();
  return resolveApiUrl(
    `/api/v1/workspaces/${workspaceId}/documents/changes/stream${query ? `?${query}` : ""}`,
  );
}

export async function* streamDocumentChanges(
  url: string,
  signal?: AbortSignal,
): AsyncGenerator<DocumentChangeEntry> {
  const abortError =
    typeof DOMException !== "undefined"
      ? new DOMException("Aborted", "AbortError")
      : Object.assign(new Error("Aborted"), { name: "AbortError" });
  const controller = new AbortController();
  const abortHandler = () => controller.abort();
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

  if (signal?.aborted) {
    controller.abort();
  } else if (signal) {
    signal.addEventListener("abort", abortHandler);
  }

  try {
    const headers = buildApiHeaders("GET", { Accept: "text/event-stream" });
    const response = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const problem = await tryParseProblemDetails(response);
      const message = problem?.title ?? `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, problem);
    }
    if (!response.body) {
      throw new Error("Document change stream unavailable.");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      while (true) {
        const match = buffer.match(/\r?\n\r?\n/);
        if (!match || match.index === undefined) break;
        const rawEvent = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const event = parseSseEvent(rawEvent);
        if (event) {
          yield event;
        }
      }

      if (done) {
        const finalEvent = parseSseEvent(buffer);
        if (finalEvent) {
          yield finalEvent;
        }
        return;
      }
    }
  } catch (error) {
    if (controller.signal.aborted) {
      throw abortError;
    }
    throw error;
  } finally {
    if (signal) {
      signal.removeEventListener("abort", abortHandler);
    }
    if (reader) {
      try {
        await reader.cancel();
      } catch {
        // ignore cancellation failures
      }
    }
    if (!controller.signal.aborted) {
      controller.abort();
    }
  }
}

function parseSseEvent(rawEvent: string): DocumentChangeEntry | null {
  const dataLines: string[] = [];
  let eventType: string | null = null;
  let eventId: string | null = null;

  for (const line of rawEvent.split(/\r?\n/)) {
    if (line.startsWith("data:")) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
      continue;
    }
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("id:")) {
      eventId = line.slice(3).trim();
    }
  }

  if (!dataLines.length) {
    return null;
  }

  const payload = dataLines.join("\n");
  if (!payload.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(payload) as Partial<DocumentChangeEntry>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const type = typeof parsed.type === "string" ? parsed.type : eventType ?? "";
    const cursor = typeof parsed.cursor === "string" ? parsed.cursor : eventId ?? "";
    if (!type || !cursor) {
      return null;
    }
    return {
      ...parsed,
      type,
      cursor,
      matchesFilters: typeof parsed.matchesFilters === "boolean" ? parsed.matchesFilters : false,
      requiresRefresh: typeof parsed.requiresRefresh === "boolean" ? parsed.requiresRefresh : false,
    } as DocumentChangeEntry;
  } catch (error) {
    console.warn("Skipping malformed document change event", error, payload);
    return null;
  }
}
