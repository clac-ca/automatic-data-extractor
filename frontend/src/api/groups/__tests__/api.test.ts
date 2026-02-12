import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import {
  addGroupMember,
  addGroupOwner,
  listGroupMembers,
  listGroupOwners,
  removeGroupMember,
  removeGroupOwner,
} from "../api";

describe("groups api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("handles member endpoints", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [] },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue({
      data: { items: [] },
    } as unknown as Awaited<ReturnType<typeof client.POST>>);
    const deleteSpy = vi.spyOn(client, "DELETE").mockResolvedValue({
      data: undefined,
    } as unknown as Awaited<ReturnType<typeof client.DELETE>>);

    await listGroupMembers("g1");
    expect(getSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/members", {
      params: { path: { groupId: "g1" } },
    });

    await addGroupMember("g1", "u1");
    expect(postSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/members/$ref", {
      params: { path: { groupId: "g1" } },
      body: { memberId: "u1" },
    });

    await removeGroupMember("g1", "u1");
    expect(deleteSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/members/{memberId}/$ref", {
      params: { path: { groupId: "g1", memberId: "u1" } },
    });
  });

  it("handles owner endpoints", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [] },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue({
      data: { items: [] },
    } as unknown as Awaited<ReturnType<typeof client.POST>>);
    const deleteSpy = vi.spyOn(client, "DELETE").mockResolvedValue({
      data: undefined,
    } as unknown as Awaited<ReturnType<typeof client.DELETE>>);

    await listGroupOwners("g2");
    expect(getSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/owners", {
      params: { path: { groupId: "g2" } },
    });

    await addGroupOwner("g2", "u2");
    expect(postSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/owners/$ref", {
      params: { path: { groupId: "g2" } },
      body: { ownerId: "u2" },
    });

    await removeGroupOwner("g2", "u2");
    expect(deleteSpy).toHaveBeenCalledWith("/api/v1/groups/{groupId}/owners/{ownerId}/$ref", {
      params: { path: { groupId: "g2", ownerId: "u2" } },
    });
  });
});
