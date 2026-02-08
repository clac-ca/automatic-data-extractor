import { client } from "@/api/client";
import type { components } from "@/types";

export type DocumentViewRecord = components["schemas"]["DocumentViewOut"];
export type DocumentViewListResponse = components["schemas"]["DocumentViewListResponse"];
export type DocumentViewCreatePayload = components["schemas"]["DocumentViewCreate"];
export type DocumentViewUpdatePayload = components["schemas"]["DocumentViewUpdate"];

export async function listDocumentViews(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<DocumentViewListResponse> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/views", {
    params: { path: { workspaceId } },
    signal,
  });
  if (!data) {
    throw new Error("Expected document views payload.");
  }
  return data;
}

export async function createDocumentView(
  workspaceId: string,
  payload: DocumentViewCreatePayload,
): Promise<DocumentViewRecord> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/views", {
    params: { path: { workspaceId } },
    body: payload,
  });
  if (!data) {
    throw new Error("Expected document view payload.");
  }
  return data;
}

export async function updateDocumentView(
  workspaceId: string,
  viewId: string,
  payload: DocumentViewUpdatePayload,
): Promise<DocumentViewRecord> {
  const { data } = await client.PATCH("/api/v1/workspaces/{workspaceId}/documents/views/{viewId}", {
    params: {
      path: {
        workspaceId,
        viewId,
      },
    },
    body: payload,
  });
  if (!data) {
    throw new Error("Expected updated document view payload.");
  }
  return data;
}

export async function deleteDocumentView(workspaceId: string, viewId: string): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspaceId}/documents/views/{viewId}", {
    params: { path: { workspaceId, viewId } },
  });
}
