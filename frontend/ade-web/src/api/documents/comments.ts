import { buildListQuery } from "@/api/listing";
import { client } from "@/api/client";
import type { components } from "@/types";

export type DocumentComment = components["schemas"]["DocumentCommentOut"];
export type DocumentCommentCreate = components["schemas"]["DocumentCommentCreate"];
export type DocumentCommentPage = components["schemas"]["DocumentCommentPage"];

export async function listDocumentComments(
  workspaceId: string,
  documentId: string,
  options: {
    limit?: number;
    cursor?: string | null;
    includeTotal?: boolean;
  } = {},
  signal?: AbortSignal,
): Promise<DocumentCommentPage> {
  const query = buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments", {
    params: { path: { workspaceId, documentId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document comments payload.");
  }

  return data;
}

export async function createDocumentComment(
  workspaceId: string,
  documentId: string,
  payload: DocumentCommentCreate,
): Promise<DocumentComment> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments", {
    params: { path: { workspaceId, documentId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected document comment payload.");
  }

  return data;
}
