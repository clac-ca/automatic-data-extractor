import { client } from "@/api/client";
import type { components } from "@/types";

export type Group = components["schemas"]["GroupOut"];
export type GroupList = components["schemas"]["GroupListResponse"];
export type GroupMembers = components["schemas"]["GroupMembersResponse"];
export type GroupOwners = components["schemas"]["GroupOwnersResponse"];
export type GroupCreateRequest = components["schemas"]["GroupCreate"];
export type GroupUpdateRequest = components["schemas"]["GroupUpdate"];

export async function listGroups(options: { q?: string; signal?: AbortSignal } = {}): Promise<GroupList> {
  const { data } = await client.GET("/api/v1/groups", {
    params: { query: { q: options.q ?? null } },
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected group list payload.");
  }
  return data as GroupList;
}

export async function createGroup(payload: GroupCreateRequest): Promise<Group> {
  const { data } = await client.POST("/api/v1/groups", { body: payload });
  if (!data) {
    throw new Error("Expected group payload.");
  }
  return data as Group;
}

export async function updateGroup(groupId: string, payload: GroupUpdateRequest): Promise<Group> {
  const { data } = await client.PATCH("/api/v1/groups/{groupId}", {
    params: { path: { groupId } },
    body: payload,
  });
  if (!data) {
    throw new Error("Expected group payload.");
  }
  return data as Group;
}

export async function deleteGroup(groupId: string): Promise<void> {
  await client.DELETE("/api/v1/groups/{groupId}", {
    params: { path: { groupId } },
  });
}

export async function listGroupMembers(groupId: string): Promise<GroupMembers> {
  const { data } = await client.GET("/api/v1/groups/{groupId}/members", {
    params: { path: { groupId } },
  });
  if (!data) {
    throw new Error("Expected group members payload.");
  }
  return data as GroupMembers;
}

export async function addGroupMember(groupId: string, memberId: string): Promise<GroupMembers> {
  const { data } = await client.POST("/api/v1/groups/{groupId}/members/$ref", {
    params: { path: { groupId } },
    body: { memberId },
  });
  if (!data) {
    throw new Error("Expected group members payload.");
  }
  return data as GroupMembers;
}

export async function removeGroupMember(groupId: string, memberId: string): Promise<void> {
  await client.DELETE("/api/v1/groups/{groupId}/members/{memberId}/$ref", {
    params: { path: { groupId, memberId } },
  });
}

export async function listGroupOwners(groupId: string): Promise<GroupOwners> {
  const { data } = await client.GET("/api/v1/groups/{groupId}/owners", {
    params: { path: { groupId } },
  });
  if (!data) {
    throw new Error("Expected group owners payload.");
  }
  return data as GroupOwners;
}

export async function addGroupOwner(groupId: string, ownerId: string): Promise<GroupOwners> {
  const { data } = await client.POST("/api/v1/groups/{groupId}/owners/$ref", {
    params: { path: { groupId } },
    body: { ownerId },
  });
  if (!data) {
    throw new Error("Expected group owners payload.");
  }
  return data as GroupOwners;
}

export async function removeGroupOwner(groupId: string, ownerId: string): Promise<void> {
  await client.DELETE("/api/v1/groups/{groupId}/owners/{ownerId}/$ref", {
    params: { path: { groupId, ownerId } },
  });
}
