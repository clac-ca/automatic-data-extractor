import { client } from "@/api/client";
import { buildListQuery } from "@/api/listing";
import type { components } from "@/types";

export interface FetchUsersOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly search?: string;
  readonly sort?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchUsers(options: FetchUsersOptions = {}): Promise<UserListPage> {
  const { limit, cursor, search, signal, includeTotal } = options;
  const trimmedSearch = search?.trim();
  const query = buildListQuery({
    limit,
    cursor: cursor ?? null,
    sort: options.sort ?? null,
    q: trimmedSearch ?? null,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/users", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected user page payload.");
  }

  return data;
}

type UserListPage = components["schemas"]["UserPage"];
type UserSummary = UserListPage["items"][number];
type User = components["schemas"]["UserOut"];
type BatchRequest = components["schemas"]["BatchRequest"];
type BatchResponse = components["schemas"]["BatchResponse"];
type BatchSubrequest = components["schemas"]["BatchSubrequest"];

const USER_BATCH_MAX_REQUESTS = 20;

export async function executeUserBatch(payload: BatchRequest): Promise<BatchResponse> {
  const { data } = await client.POST("/api/v1/$batch", {
    body: payload,
  });
  if (!data) {
    throw new Error("Expected batch response payload.");
  }
  return data as BatchResponse;
}

export function chunkUserBatchRequests(
  requests: readonly BatchSubrequest[],
  chunkSize = USER_BATCH_MAX_REQUESTS,
): BatchSubrequest[][] {
  const size = Number.isFinite(chunkSize) ? Math.max(1, Math.floor(chunkSize)) : USER_BATCH_MAX_REQUESTS;
  const chunks: BatchSubrequest[][] = [];
  for (let i = 0; i < requests.length; i += size) {
    chunks.push([...requests.slice(i, i + size)]);
  }
  return chunks;
}

export async function executeUserBatchChunked(
  requests: readonly BatchSubrequest[],
  chunkSize = USER_BATCH_MAX_REQUESTS,
): Promise<BatchResponse> {
  const chunks = chunkUserBatchRequests(requests, chunkSize);
  const responses: BatchResponse["responses"] = [];
  for (const chunk of chunks) {
    const result = await executeUserBatch({ requests: chunk });
    responses.push(...result.responses);
  }
  return { responses };
}

export type { BatchRequest, BatchResponse, BatchSubrequest, User, UserListPage, UserSummary };
