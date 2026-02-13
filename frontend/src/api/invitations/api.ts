import { buildListQuery } from "@/api/listing";
import { clampPageSize, DEFAULT_PAGE_SIZE } from "@/api/pagination";
import { client } from "@/api/client";
import type { components } from "@/types";

export type Invitation = components["schemas"]["InvitationOut"];
export type InvitationPage = components["schemas"]["InvitationPage"];
export type InvitationCreateRequest = components["schemas"]["InvitationCreate"];

export interface ListInvitationsOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly q?: string;
  readonly includeTotal?: boolean;
  readonly workspaceId?: string;
  readonly status?: components["schemas"]["InvitationLifecycleStatus"] | null;
  readonly signal?: AbortSignal;
}

export async function listInvitations(options: ListInvitationsOptions = {}): Promise<InvitationPage> {
  const query = buildListQuery({
    limit: clampPageSize(options.limit ?? DEFAULT_PAGE_SIZE),
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.q ?? null,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/invitations", {
    params: {
      query: {
        ...query,
        workspace_id: options.workspaceId ?? null,
        status: options.status ?? null,
      },
    },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected invitation page payload.");
  }
  return data as InvitationPage;
}

export async function createInvitation(payload: InvitationCreateRequest): Promise<Invitation> {
  const { data } = await client.POST("/api/v1/invitations", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected invitation payload.");
  }
  return data as Invitation;
}

export async function resendInvitation(invitationId: string): Promise<Invitation> {
  const { data } = await client.POST("/api/v1/invitations/{invitationId}/resend", {
    params: { path: { invitationId } },
  });
  if (!data) {
    throw new Error("Expected invitation payload.");
  }
  return data as Invitation;
}

export async function getInvitation(invitationId: string): Promise<Invitation> {
  const { data } = await client.GET("/api/v1/invitations/{invitationId}", {
    params: { path: { invitationId } },
  });
  if (!data) {
    throw new Error("Expected invitation payload.");
  }
  return data as Invitation;
}

export async function cancelInvitation(invitationId: string): Promise<Invitation> {
  const { data } = await client.POST("/api/v1/invitations/{invitationId}/cancel", {
    params: { path: { invitationId } },
  });
  if (!data) {
    throw new Error("Expected invitation payload.");
  }
  return data as Invitation;
}
