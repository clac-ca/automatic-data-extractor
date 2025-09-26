import { API_BASE_URL } from "./client";
import { ApiError } from "./errors";

export interface DocumentRecord {
  document_id: string;
  original_filename: string;
  content_type: string | null;
  byte_size: number;
  sha256: string;
  stored_uri: string;
  metadata: Record<string, unknown>;
  expires_at: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  deleted_by: string | null;
  delete_reason: string | null;
}

export type DocumentStatus = "active" | "deleted";

export interface WorkspaceDocument {
  id: string;
  filename: string;
  contentType: string | null;
  byteSize: number;
  sha256: string;
  storedUri: string;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
  deletedAt: string | null;
  deletedBy: string | null;
  deleteReason: string | null;
  status: DocumentStatus;
  documentType: string | null;
}

export interface FetchDocumentsOptions {
  limit?: number;
  offset?: number;
}

export interface DeleteDocumentOptions {
  reason?: string | null;
}

export interface DocumentUploadOptions {
  documentType: string;
  expiresAt?: string | null;
  metadata?: Record<string, unknown>;
  configurationIds?: string[];
}

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new ApiError("Invalid response from server", response.status, text);
  }
}

export function normaliseDocument(record: DocumentRecord): WorkspaceDocument {
  const metadata = record.metadata ?? {};
  const documentType =
    typeof metadata.document_type === "string"
      ? metadata.document_type
      : typeof metadata.documentType === "string"
        ? metadata.documentType
        : null;

  return {
    id: record.document_id,
    filename: record.original_filename,
    contentType: record.content_type,
    byteSize: record.byte_size,
    sha256: record.sha256,
    storedUri: record.stored_uri,
    metadata,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    expiresAt: record.expires_at,
    deletedAt: record.deleted_at,
    deletedBy: record.deleted_by,
    deleteReason: record.delete_reason,
    status: record.deleted_at ? "deleted" : "active",
    documentType,
  };
}

export async function fetchWorkspaceDocuments(
  token: string,
  workspaceId: string,
  options: FetchDocumentsOptions = {},
): Promise<DocumentRecord[]> {
  const url = new URL(
    `${API_BASE_URL}/workspaces/${workspaceId}/documents`,
    window.location.origin,
  );

  if (typeof options.limit === "number") {
    url.searchParams.set("limit", options.limit.toString());
  }
  if (typeof options.offset === "number") {
    url.searchParams.set("offset", options.offset.toString());
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = await parseJson(response).catch(() => null);
    const message =
      (payload && typeof payload.detail === "string"
        ? payload.detail
        : response.statusText) || "Failed to load documents";
    throw new ApiError(message, response.status, payload);
  }

  const payload = await parseJson(response);
  if (!Array.isArray(payload)) {
    throw new ApiError(
      "Unexpected documents response",
      response.status,
      payload,
    );
  }

  return payload as DocumentRecord[];
}

export async function deleteWorkspaceDocument(
  token: string,
  workspaceId: string,
  documentId: string,
  options: DeleteDocumentOptions = {},
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/documents/${documentId}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: options.reason ? JSON.stringify({ reason: options.reason }) : null,
    },
  );

  if (!response.ok) {
    const payload = await parseJson(response).catch(() => null);
    const message =
      (payload && typeof payload.detail === "string"
        ? payload.detail
        : response.statusText) || "Failed to delete document";
    throw new ApiError(message, response.status, payload);
  }
}

export async function uploadWorkspaceDocument(
  token: string,
  workspaceId: string,
  file: File,
  options: DocumentUploadOptions,
): Promise<DocumentRecord> {
  const metadata: Record<string, unknown> = {
    document_type: options.documentType,
    ...(options.metadata ?? {}),
  };

  if (options.configurationIds && options.configurationIds.length > 0) {
    metadata.target_configuration_ids = options.configurationIds;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("metadata", JSON.stringify(metadata));
  if (options.expiresAt) {
    formData.append("expires_at", options.expiresAt);
  }

  const response = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/documents`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    },
  );

  if (!response.ok) {
    const payload = await parseJson(response).catch(() => null);
    const message =
      (payload && typeof payload.detail === "string"
        ? payload.detail
        : response.statusText) || "Failed to upload document";
    throw new ApiError(message, response.status, payload);
  }

  const payload = await parseJson(response);
  if (!payload || typeof payload !== "object") {
    throw new ApiError(
      "Unexpected upload response",
      response.status,
      payload,
    );
  }

  return payload as DocumentRecord;
}

export function buildDocumentDownloadUrl(
  workspaceId: string,
  documentId: string,
): string {
  return `${API_BASE_URL}/workspaces/${workspaceId}/documents/${documentId}/download`;
}
