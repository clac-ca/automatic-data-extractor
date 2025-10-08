import { get, post } from "../../shared/api/client";
import type {
  CreateWorkspacePayload,
  DocumentTypeDetailResponse,
  WorkspaceProfile,
  WorkspaceRole,
} from "../../shared/api/types";

interface WorkspaceProfileResponse {
  workspace_id: string;
  name: string;
  slug: string;
  role: WorkspaceRole;
  permissions: string[];
  is_default: boolean;
}

function mapWorkspaceProfile(payload: WorkspaceProfileResponse): WorkspaceProfile {
  return {
    id: payload.workspace_id,
    name: payload.name,
    slug: payload.slug,
    role: payload.role,
    permissions: payload.permissions ?? [],
    is_default: payload.is_default,
  } satisfies WorkspaceProfile;
}

export async function fetchWorkspaces() {
  const response = await get<WorkspaceProfileResponse[]>("/workspaces");
  return response.map(mapWorkspaceProfile);
}

export async function fetchDocumentType(workspaceId: string, documentTypeId: string) {
  return get<DocumentTypeDetailResponse>(`/workspaces/${workspaceId}/document-types/${documentTypeId}`);
}

export async function createWorkspace(payload: CreateWorkspacePayload) {
  const response = await post<WorkspaceProfileResponse>("/workspaces", payload);
  return mapWorkspaceProfile(response);
}
