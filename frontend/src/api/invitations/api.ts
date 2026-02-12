import { client } from "@/api/client";
import type { components } from "@/types";

export type Invitation = components["schemas"]["InvitationOut"];
export type InvitationList = components["schemas"]["InvitationListResponse"];
export type InvitationCreateRequest = components["schemas"]["InvitationCreate"];

export interface ListInvitationsOptions {
  readonly workspaceId?: string;
  readonly status?: components["schemas"]["InvitationStatus"] | null;
  readonly signal?: AbortSignal;
}

export async function listInvitations(options: ListInvitationsOptions = {}): Promise<InvitationList> {
  const { data } = await client.GET("/api/v1/invitations", {
    params: {
      query: {
        workspace_id: options.workspaceId ?? null,
        invitation_status: options.status ?? null,
      },
    },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected invitation list payload.");
  }
  return data as InvitationList;
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

export async function cancelInvitation(invitationId: string): Promise<Invitation> {
  const { data } = await client.POST("/api/v1/invitations/{invitationId}/cancel", {
    params: { path: { invitationId } },
  });
  if (!data) {
    throw new Error("Expected invitation payload.");
  }
  return data as Invitation;
}
