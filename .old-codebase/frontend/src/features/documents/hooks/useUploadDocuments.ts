import { useMutation, useQueryClient } from "@tanstack/react-query";

import { uploadWorkspaceDocument, documentsKeys } from "../api";

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
