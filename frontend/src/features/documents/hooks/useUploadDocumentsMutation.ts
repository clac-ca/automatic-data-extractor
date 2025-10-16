import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { WorkspaceDocumentSummary } from "../../../shared/types/documents";
import { uploadWorkspaceDocument } from "../api";
import { documentKeys } from "./useWorkspaceDocumentsQuery";

interface UploadProgressUpdate {
  readonly file: File;
  readonly index: number;
  readonly total: number;
}

interface UploadDocumentsInput {
  readonly files: readonly File[];
  readonly metadata?: Record<string, unknown>;
  readonly expiresAt?: string;
  readonly onProgress?: (update: UploadProgressUpdate) => void;
}

export function useUploadDocumentsMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: UploadDocumentsInput) => {
      const files = Array.from(input.files);
      const results: WorkspaceDocumentSummary[] = [];
      const total = files.length;
      for (const [index, file] of files.entries()) {
        const document = await uploadWorkspaceDocument(workspaceId, {
          file,
          metadata: input.metadata,
          expiresAt: input.expiresAt,
        });
        results.push(document);
        input.onProgress?.({ file, index, total });
      }
      return results;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: documentKeys.list(workspaceId),
        refetchType: "active",
      });
    },
  });
}
