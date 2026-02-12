import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { MAX_PAGE_SIZE } from "@/api/pagination";
import { getInvitation, listInvitations } from "../api";

describe("invitations api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests invitations with cursor query params and status filters", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        items: [],
        meta: {
          limit: MAX_PAGE_SIZE,
          hasMore: false,
          nextCursor: null,
          totalIncluded: true,
          totalCount: 0,
          changesCursor: "0",
        },
        facets: null,
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listInvitations({
      workspaceId: "ws-123",
      status: "expired",
      limit: 999,
      cursor: "cursor-1",
      sort: JSON.stringify([{ id: "createdAt", desc: true }]),
      q: "invitee@example.com",
      includeTotal: true,
    });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/invitations", {
      params: {
        query: {
          limit: MAX_PAGE_SIZE,
          cursor: "cursor-1",
          sort: JSON.stringify([{ id: "createdAt", desc: true }]),
          q: "invitee@example.com",
          includeTotal: true,
          workspace_id: "ws-123",
          status: "expired",
        },
      },
      signal: undefined,
    });
  });

  it("fetches invitation detail by id", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        id: "inv-123",
        email_normalized: "invitee@example.com",
        invited_user_id: null,
        invited_by_user_id: "user-123",
        workspace_id: "ws-123",
        status: "pending",
        expires_at: "2026-02-20T00:00:00Z",
        redeemed_at: null,
        workspaceContext: {
          workspaceId: "ws-123",
          roleAssignments: [{ roleId: "role-123" }],
        },
        created_at: "2026-02-12T00:00:00Z",
        updated_at: "2026-02-12T00:00:00Z",
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    const invitation = await getInvitation("inv-123");

    expect(getSpy).toHaveBeenCalledWith("/api/v1/invitations/{invitationId}", {
      params: { path: { invitationId: "inv-123" } },
    });
    expect(invitation.id).toBe("inv-123");
  });
});

