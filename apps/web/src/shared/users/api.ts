import { get, post } from "@shared/api";
import { normalizePaginatedResponse, type PaginatedResult } from "@shared/api/pagination";
import type { components } from "@openapi";

export interface FetchUsersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly search?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export function fetchUsers(options: FetchUsersOptions = {}): Promise<UserListPage> {
  const { page, pageSize, search, includeTotal, signal } = options;
  const params = new URLSearchParams();

  if (typeof page === "number" && page > 0) {
    params.set("page", String(page));
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    params.set("page_size", String(pageSize));
  }
  if (includeTotal) {
    params.set("include_total", "true");
  }
  if (search && search.trim().length > 0) {
    params.set("q", search.trim());
  }

  const query = params.toString();
  const path = query.length > 0 ? `/users?${query}` : "/users";

  return get<UserListResponseWire>(path, { signal }).then((response) =>
    normalizePaginatedResponse<UserSummary>(response),
  );
}

export interface InviteUserPayload {
  readonly email: string;
  readonly display_name?: string | null;
}

export function inviteUser(payload: InviteUserPayload) {
  return post<UserProfile>("/users/invitations", payload);
}

type UserSummary = components["schemas"]["UserSummary"];
type UserListResponseWire = components["schemas"]["UserListResponse"];
type UserProfile = components["schemas"]["UserProfile"];

export type UserListPage = PaginatedResult<UserSummary>;
