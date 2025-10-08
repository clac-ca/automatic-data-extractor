import { get, post } from "../../shared/api/client";
import type {
  CreateWorkspacePayload,
  DocumentTypeDetailResponse,
  WorkspaceListResponse,
  WorkspaceSummary,
} from "../../shared/api/types";

export async function fetchWorkspaces() {
  return get<WorkspaceListResponse>("/workspaces");
}

export async function fetchDocumentType(workspaceId: string, documentTypeId: string) {
  return get<DocumentTypeDetailResponse>(`/workspaces/${workspaceId}/document-types/${documentTypeId}`);
}

export async function createWorkspace(payload: CreateWorkspacePayload) {
  return post<WorkspaceSummary>("/workspaces", payload);
}
