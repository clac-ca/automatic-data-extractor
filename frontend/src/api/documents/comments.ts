import { client } from "@/api/client";
import type { components } from "@/types";

export type DocumentComment = components["schemas"]["DocumentCommentOut"];
export type DocumentActivityResponse = components["schemas"]["DocumentActivityResponse"];
export type DocumentActivityThreadCreate = components["schemas"]["DocumentActivityThreadCreate"];
export type DocumentActivityCommentCreate = components["schemas"]["DocumentActivityCommentCreate"];
export type DocumentActivityThread = components["schemas"]["DocumentActivityThreadOut"];
export type DocumentActivityDocumentItem = components["schemas"]["DocumentActivityDocumentItemOut"];
export type DocumentActivityRunItem = components["schemas"]["DocumentActivityRunItemOut"];
export type DocumentActivityNoteItem = components["schemas"]["DocumentActivityNoteItemOut"];
export type DocumentActivityRun = components["schemas"]["DocumentActivityRunOut"];
export type DocumentCommentUpdate = components["schemas"]["DocumentCommentUpdate"];
export type DocumentCommentMentionIn = components["schemas"]["DocumentCommentMentionIn"];
export type DocumentCommentMentionOut = components["schemas"]["DocumentCommentMentionOut"];

export async function getDocumentActivity(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentActivityResponse> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}/activity", {
    params: { path: { workspaceId, documentId } },
    signal,
  });

  if (!data) {
    throw new Error("Expected document activity payload.");
  }

  return data;
}

export async function createDocumentActivityThread(
  workspaceId: string,
  documentId: string,
  payload: DocumentActivityThreadCreate,
): Promise<DocumentActivityThread> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/threads", {
    params: { path: { workspaceId, documentId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected document activity thread payload.");
  }

  return data;
}

export async function createDocumentActivityComment(
  workspaceId: string,
  documentId: string,
  threadId: string,
  payload: DocumentActivityCommentCreate,
): Promise<DocumentComment> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/threads/{threadId}/comments",
    {
      params: { path: { workspaceId, documentId, threadId } },
      body: payload,
    },
  );

  if (!data) {
    throw new Error("Expected document activity comment payload.");
  }

  return data;
}

export async function updateDocumentComment(
  workspaceId: string,
  documentId: string,
  commentId: string,
  payload: DocumentCommentUpdate,
): Promise<DocumentComment> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments/{commentId}",
    {
      params: { path: { workspaceId, documentId, commentId } },
      body: payload,
    },
  );

  if (!data) {
    throw new Error("Expected updated document comment payload.");
  }

  return data;
}

export async function deleteDocumentComment(
  workspaceId: string,
  documentId: string,
  commentId: string,
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments/{commentId}", {
    params: { path: { workspaceId, documentId, commentId } },
  });
}
