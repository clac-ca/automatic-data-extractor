import { useMutation, useQueryClient } from "@tanstack/react-query";

import { uploadWorkspaceDocument } from "../api";
import { documentsKeys } from "../api/keys";

interface UploadDocumentsArgs {
  readonly files: readonly File[];
}

export function useUploadDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ files }: UploadDocumentsArgs) => {
      const uploads = Array.from(files);
      for (const file of uploads) {
        await uploadWorkspaceDocument(workspaceId, file);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: documentsKeys.workspace(workspaceId),
        refetchType: "active",
      });
    },
  });
}
