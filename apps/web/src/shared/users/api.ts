import { post } from "@shared/api";
import { client } from "@shared/api/client";
import type { components, paths } from "@openapi";

export interface FetchUsersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly search?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchUsers(options: FetchUsersOptions = {}): Promise<UserListPage> {
  const { page, pageSize, search, includeTotal, signal } = options;
  const query: ListUsersQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }
  const trimmedSearch = search?.trim();
  if (trimmedSearch) {
    query.q = trimmedSearch;
  }

  const { data } = await client.GET("/api/v1/users", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected user page payload.");
  }

  return data;
}

export interface InviteUserPayload {
  readonly email: string;
  readonly display_name?: string | null;
}

export function inviteUser(payload: InviteUserPayload) {
  return post<UserProfile>("/users/invitations", payload);
}

type ListUsersQuery = paths["/api/v1/users"]["get"]["parameters"]["query"];
type UserListPage = components["schemas"]["UserPage"];
type UserSummary = UserListPage["items"][number];
type UserProfile = components["schemas"]["UserProfile"];

export type { UserListPage, UserSummary };
