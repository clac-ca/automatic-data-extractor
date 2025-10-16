import { del, get, post } from "../../shared/api/client";
import type { DocumentRecord, WorkspaceDocumentSummary } from "../../shared/types/documents";

function normaliseDocument(record: DocumentRecord): WorkspaceDocumentSummary {
  return {
    id: record.document_id,
    name: record.original_filename,
    updatedAt: record.updated_at,
    createdAt: record.created_at,
    byteSize: record.byte_size,
    contentType: record.content_type,
    metadata: record.metadata ?? {},
  };
}

export async function fetchWorkspaceDocuments(workspaceId: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ limit: "200", offset: "0" });
  const response = await get<DocumentRecord[]>(`/workspaces/${workspaceId}/documents?${params.toString()}`, {
    signal,
  });
  return response.map((record) => normaliseDocument(record));
}

interface UploadWorkspaceDocumentInput {
  readonly file: File;
  readonly metadata?: Record<string, unknown>;
  readonly expiresAt?: string;
}

export async function uploadWorkspaceDocument(
  workspaceId: string,
  input: UploadWorkspaceDocumentInput,
) {
  const formData = new FormData();
  formData.append("file", input.file);
  if (input.metadata && Object.keys(input.metadata).length > 0) {
    formData.append("metadata", JSON.stringify(input.metadata));
  }
  if (input.expiresAt) {
    formData.append("expires_at", input.expiresAt);
  }

  const response = await post<DocumentRecord>(`/workspaces/${workspaceId}/documents`, formData);
  return normaliseDocument(response);
}

export async function deleteWorkspaceDocuments(workspaceId: string, documentIds: readonly string[]) {
  for (const documentId of documentIds) {
    await del(`/workspaces/${workspaceId}/documents/${documentId}`, { parseJson: false });
  }
}

export async function downloadWorkspaceDocument(workspaceId: string, documentId: string) {
  const response = await get<Response>(`/workspaces/${workspaceId}/documents/${documentId}/download`, {
    parseJson: false,
    returnRawResponse: true,
  });
  const blob = await response.blob();
  const filename =
    extractFilename(response.headers.get("content-disposition")) ?? `document-${documentId}`;
  return { blob, filename };
}

function extractFilename(header: string | null) {
  if (!header) {
    return null;
  }
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^";]+)"?/i);
  if (filenameMatch?.[1]) {
    return filenameMatch[1];
  }
  return null;
}
