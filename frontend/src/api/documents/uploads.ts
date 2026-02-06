import type { components } from "@/types";
import { uploadWithProgressXHR, type UploadHandle, type UploadProgress } from "@/lib/uploads/xhr";

export type DocumentUploadResponse = components["schemas"]["DocumentOut"];
export type DocumentUploadRunOptions = components["schemas"]["RunCreateOptionsBase"];
export type DocumentConflictMode = components["schemas"]["DocumentConflictMode"];

interface UploadDocumentOptions {
  readonly onProgress?: (progress: UploadProgress) => void;
  readonly runOptions?: DocumentUploadRunOptions;
  readonly conflictMode?: DocumentConflictMode;
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
  if (options.conflictMode) {
    formData.append("conflictMode", options.conflictMode);
  }
  return uploadWithProgressXHR<DocumentUploadResponse>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    formData,
    {
      onProgress: options.onProgress,
    },
  );
}
