import { API_BASE_URL } from "./client";
import { ApiError } from "./errors";

export interface WorkspaceProfile {
  workspace_id: string;
  name: string;
  slug: string;
  role: string;
  permissions: string[];
  is_default: boolean;
}

export interface WorkspaceContext {
  workspace: WorkspaceProfile;
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

export async function fetchWorkspaces(token: string): Promise<WorkspaceProfile[]> {
  const response = await fetch(`${API_BASE_URL}/workspaces`, {
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
        : response.statusText) || "Failed to load workspaces";
    throw new ApiError(message, response.status, payload);
  }

  const payload = await parseJson(response);
  if (!Array.isArray(payload)) {
    throw new ApiError("Unexpected workspace response", response.status, payload);
  }
  return payload as WorkspaceProfile[];
}

export async function fetchWorkspaceContext(
  token: string,
  workspaceId: string,
): Promise<WorkspaceContext> {
  const response = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}`, {
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
        : response.statusText) || "Failed to load workspace";
    throw new ApiError(message, response.status, payload);
  }

  const payload = await parseJson(response);
  if (!payload || typeof payload !== "object" || !("workspace" in payload)) {
    throw new ApiError("Unexpected workspace response", response.status, payload);
  }
  return payload as WorkspaceContext;
}
