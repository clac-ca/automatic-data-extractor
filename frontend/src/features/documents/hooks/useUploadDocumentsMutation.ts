import { useMutation, useQueryClient } from "@tanstack/react-query";

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
      const total = files.length;
      for (const [index, file] of files.entries()) {
        await uploadWorkspaceDocument(workspaceId, {
          file,
          metadata: input.metadata,
          expiresAt: input.expiresAt,
        });
        input.onProgress?.({ file, index, total });
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: documentKeys.lists(workspaceId),
        refetchType: "active",
      });
    },
  });
}
