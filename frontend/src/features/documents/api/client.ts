import { del, get, post } from "../../../shared/api/client";
import type {
  DocumentListResponse,
  DocumentRecord,
  DocumentStatus,
} from "../../../shared/types/documents";

export type StatusFilterInput = DocumentStatus | readonly DocumentStatus[] | null | undefined;

export function normaliseStatusFilter(status: StatusFilterInput) {
  if (status == null) {
    return undefined;
  }
  if (Array.isArray(status)) {
    const filtered = (status as readonly DocumentStatus[]).filter(
      (value): value is DocumentStatus => Boolean(value),
    );
    return filtered.length > 0 ? filtered : undefined;
  }
  return [status as DocumentStatus];
}

export interface ListWorkspaceDocumentsOptions {
  readonly status?: StatusFilterInput;
  readonly search?: string | null;
  readonly sort?: string | null;
}

export async function listWorkspaceDocuments(
  workspaceId: string,
  options: ListWorkspaceDocumentsOptions = {},
  signal?: AbortSignal,
) {
  const search = new URLSearchParams();
  const statuses = normaliseStatusFilter(options.status);

  for (const value of statuses ?? []) {
    search.append("status", value);
  }

  if (options.search && options.search.trim().length > 0) {
    search.set("q", options.search.trim());
  }

  if (options.sort && options.sort.trim().length > 0) {
    search.set("sort", options.sort.trim());
  }

  const query = search.toString();
  const path =
    query.length > 0 ? `/workspaces/${workspaceId}/documents?${query}` : `/workspaces/${workspaceId}/documents`;

  return get<DocumentListResponse>(path, { signal });
}

export async function uploadWorkspaceDocument(workspaceId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
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
