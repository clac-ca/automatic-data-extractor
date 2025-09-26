import { ApiClient } from "@api/client";

export interface WorkspaceProfile {
  readonly workspaceId: string;
  readonly name: string;
  readonly slug: string;
  readonly role: string;
  readonly permissions: string[];
  readonly isDefault: boolean;
}

interface WorkspaceProfileResponse {
  readonly workspace_id: string;
  readonly name: string;
  readonly slug: string;
  readonly role: string;
  readonly permissions: string[];
  readonly is_default: boolean;
}

interface WorkspaceContextResponse {
  readonly workspace: WorkspaceProfileResponse;
}

export async function listWorkspaces(client: ApiClient): Promise<WorkspaceProfile[]> {
  const response = await client.get<WorkspaceProfileResponse[]>("/workspaces");
  return response.map(transformWorkspaceProfile);
}

export async function getWorkspaceContext(
  client: ApiClient,
  workspaceId: string
): Promise<WorkspaceProfile> {
  const response = await client.get<WorkspaceContextResponse>(`/workspaces/${workspaceId}`);
  return transformWorkspaceProfile(response.workspace);
}

function transformWorkspaceProfile(record: WorkspaceProfileResponse): WorkspaceProfile {
  return {
    workspaceId: record.workspace_id,
    name: record.name,
    slug: record.slug,
    role: record.role,
    permissions: [...record.permissions],
    isDefault: record.is_default
  };
}
