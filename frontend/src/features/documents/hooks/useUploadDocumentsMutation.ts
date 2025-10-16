import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { WorkspaceDocumentSummary } from "../../../shared/types/documents";
import { uploadWorkspaceDocument } from "../api";
import { documentKeys } from "./useWorkspaceDocumentsQuery";

interface UploadDocumentsInput {
  readonly files: File[];
  readonly metadata?: Record<string, unknown>;
  readonly expiresAt?: string;
}

export function useUploadDocumentsMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: UploadDocumentsInput) => {
      const results: WorkspaceDocumentSummary[] = [];
      for (const file of input.files) {
        const document = await uploadWorkspaceDocument(workspaceId, {
          file,
          metadata: input.metadata,
          expiresAt: input.expiresAt,
        });
        results.push(document);
      }
      return results;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: documentKeys.list(workspaceId) });
    },
  });
}
