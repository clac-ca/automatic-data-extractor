import { client } from "@api/client";
import { buildListQuery } from "@api/listing";
import type { components } from "@schema";

export interface FetchUsersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly search?: string;
  readonly sort?: string;
  readonly signal?: AbortSignal;
}

export async function fetchUsers(options: FetchUsersOptions = {}): Promise<UserListPage> {
  const { page, pageSize, search, signal } = options;
  const trimmedSearch = search?.trim();
  const query = buildListQuery({
    page,
    perPage: pageSize,
    sort: options.sort ?? null,
    q: trimmedSearch ?? null,
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

export type { UserListPage, UserSummary, User };
