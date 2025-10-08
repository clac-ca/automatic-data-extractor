import { get } from "../../shared/api/client";
import type { DocumentTypeDetailResponse, WorkspaceListResponse } from "../../shared/api/types";

export async function fetchWorkspaces() {
  return get<WorkspaceListResponse>("/workspaces");
}

export async function fetchDocumentType(workspaceId: string, documentTypeId: string) {
  return get<DocumentTypeDetailResponse>(`/workspaces/${workspaceId}/document-types/${documentTypeId}`);
}
