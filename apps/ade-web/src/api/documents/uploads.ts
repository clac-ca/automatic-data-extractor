import type { components } from "@schema";
import { createIdempotencyKey } from "@api/idempotency";
import { uploadWithProgressXHR, type UploadHandle, type UploadProgress } from "@lib/uploads/xhr";

export type DocumentUploadResponse = components["schemas"]["DocumentOut"];
export type DocumentUploadRunOptions = components["schemas"]["DocumentUploadRunOptions"];

interface UploadDocumentOptions {
  readonly onProgress?: (progress: UploadProgress) => void;
  readonly idempotencyKey?: string;
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
      headers: {
        "Idempotency-Key": options.idempotencyKey ?? createIdempotencyKey("document-upload"),
      },
      onProgress: options.onProgress,
    },
  );
}
