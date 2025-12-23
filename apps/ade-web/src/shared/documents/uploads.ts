import type { components } from "@schema";
import { uploadWithProgressXHR, type UploadHandle, type UploadProgress } from "@shared/uploads/xhr";

export type DocumentUploadResponse = components["schemas"]["DocumentOut"];

interface UploadDocumentOptions {
  readonly onProgress?: (progress: UploadProgress) => void;
}

export function uploadWorkspaceDocument(
  workspaceId: string,
  file: File,
  options: UploadDocumentOptions = {},
): UploadHandle<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return uploadWithProgressXHR<DocumentUploadResponse>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    formData,
    {
      onProgress: options.onProgress,
    },
  );
}
