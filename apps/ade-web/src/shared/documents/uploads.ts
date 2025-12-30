import type { components } from "@schema";
import { apiFetch, client } from "@shared/api/client";
import { ApiError, type ProblemDetails } from "@shared/api/errors";
import { uploadWithProgressXHR, type UploadHandle, type UploadProgress } from "@shared/uploads/xhr";

export type DocumentUploadResponse = components["schemas"]["DocumentOut"];
export type DocumentUploadRunOptions = components["schemas"]["DocumentUploadRunOptions"];
export type DocumentUploadSessionCreateRequest =
  components["schemas"]["DocumentUploadSessionCreateRequest"];
export type DocumentUploadSessionCreateResponse =
  components["schemas"]["DocumentUploadSessionCreateResponse"];
export type DocumentUploadSessionStatusResponse =
  components["schemas"]["DocumentUploadSessionStatusResponse"];
export type DocumentUploadSessionUploadResponse =
  components["schemas"]["DocumentUploadSessionUploadResponse"];

interface UploadDocumentOptions {
  readonly onProgress?: (progress: UploadProgress) => void;
  readonly runOptions?: DocumentUploadRunOptions;
}

export function uploadWorkspaceDocument(
  workspaceId: string,
  file: File,
  options: UploadDocumentOptions = {},
): UploadHandle<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options.runOptions) {
    formData.append("run_options", JSON.stringify(options.runOptions));
  }
  return uploadWithProgressXHR<DocumentUploadResponse>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    formData,
    {
      onProgress: options.onProgress,
    },
  );
}

export async function createDocumentUploadSession(
  workspaceId: string,
  payload: DocumentUploadSessionCreateRequest,
  signal?: AbortSignal,
): Promise<DocumentUploadSessionCreateResponse> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/uploadSessions", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
    signal,
  });
  if (!data) {
    throw new Error("Expected upload session response.");
  }
  return data;
}

export async function uploadDocumentUploadSessionRange(
  workspaceId: string,
  sessionId: string,
  options: {
    start: number;
    end: number;
    total: number;
    body: Blob;
    signal?: AbortSignal;
  },
): Promise<DocumentUploadSessionUploadResponse> {
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/documents/uploadSessions/${sessionId}`,
    {
      method: "PUT",
      body: options.body,
      headers: {
        "Content-Range": `bytes ${options.start}-${options.end}/${options.total}`,
        "Content-Type": "application/octet-stream",
      },
      signal: options.signal,
    },
  );

  if (!response.ok) {
    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json().catch(() => null)) as DocumentUploadSessionUploadResponse | null;
  if (!data) {
    throw new Error("Expected upload range response.");
  }
  return data;
}

export async function getDocumentUploadSessionStatus(
  workspaceId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<DocumentUploadSessionStatusResponse> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/uploadSessions/{upload_session_id}",
    {
      params: { path: { workspace_id: workspaceId, upload_session_id: sessionId } },
      signal,
    },
  );
  if (!data) {
    throw new Error("Expected upload session status response.");
  }
  return data;
}

export async function commitDocumentUploadSession(
  workspaceId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<DocumentUploadResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/documents/uploadSessions/{upload_session_id}/commit",
    {
      params: { path: { workspace_id: workspaceId, upload_session_id: sessionId } },
      signal,
    },
  );
  if (!data) {
    throw new Error("Expected upload commit response.");
  }
  return data as DocumentUploadResponse;
}

export async function cancelDocumentUploadSession(
  workspaceId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<void> {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/documents/uploadSessions/{upload_session_id}",
    {
      params: { path: { workspace_id: workspaceId, upload_session_id: sessionId } },
      signal,
    },
  );
}

async function tryParseProblem(response: Response): Promise<ProblemDetails | undefined> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return (await response.clone().json()) as ProblemDetails;
  } catch {
    return undefined;
  }
}
