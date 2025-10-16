import { del, get, post } from "../../shared/api/client";
import type { DocumentListResponse, DocumentRecord } from "../../shared/types/documents";

export interface DocumentsQueryParams {
  readonly status?: readonly string[];
  readonly source?: readonly string[];
  readonly tag?: readonly string[];
  readonly uploader?: string;
  readonly uploader_id?: readonly string[];
  readonly q?: string;
  readonly created_from?: string;
  readonly created_to?: string;
  readonly last_run_from?: string;
  readonly last_run_to?: string;
  readonly byte_size_min?: number;
  readonly byte_size_max?: number;
  readonly sort?: string;
  readonly page?: number;
  readonly per_page?: number;
  readonly include_total?: boolean;
}

export function buildDocumentsSearchParams(params: DocumentsQueryParams) {
  const search = new URLSearchParams();

  const appendMany = (key: string, values: readonly string[] | undefined) => {
    if (!values) {
      return;
    }
    for (const value of values) {
      if (value) {
        search.append(key, value);
      }
    }
  };

  appendMany("status", params.status);
  appendMany("source", params.source);
  appendMany("tag", params.tag);
  appendMany("uploader_id", params.uploader_id);

  if (params.uploader) {
    search.set("uploader", params.uploader);
  }
  if (params.q) {
    search.set("q", params.q);
  }
  if (params.created_from) {
    search.set("created_from", params.created_from);
  }
  if (params.created_to) {
    search.set("created_to", params.created_to);
  }
  if (params.last_run_from) {
    search.set("last_run_from", params.last_run_from);
  }
  if (params.last_run_to) {
    search.set("last_run_to", params.last_run_to);
  }
  if (typeof params.byte_size_min === "number") {
    search.set("byte_size_min", params.byte_size_min.toString());
  }
  if (typeof params.byte_size_max === "number") {
    search.set("byte_size_max", params.byte_size_max.toString());
  }
  if (params.sort) {
    search.set("sort", params.sort);
  }
  if (typeof params.page === "number") {
    search.set("page", params.page.toString());
  }
  if (typeof params.per_page === "number") {
    search.set("per_page", params.per_page.toString());
  }
  if (params.include_total) {
    search.set("include_total", "true");
  }

  return search;
}

export async function fetchWorkspaceDocuments(
  workspaceId: string,
  params: DocumentsQueryParams,
  signal?: AbortSignal,
) {
  const search = buildDocumentsSearchParams(params);
  const response = await get<DocumentListResponse>(
    `/workspaces/${workspaceId}/documents?${search.toString()}`,
    { signal },
  );
  return response;
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

  return post<DocumentRecord>(`/workspaces/${workspaceId}/documents`, formData);
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
