import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteWorkspaceDocuments } from "../api/client";
import { documentsKeys } from "../api/keys";

interface DeleteDocumentsArgs {
  readonly documentIds: readonly string[];
}

export function useDeleteDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ documentIds }: DeleteDocumentsArgs) => {
      if (documentIds.length === 0) {
        return;
      }
      await deleteWorkspaceDocuments(workspaceId, documentIds);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: documentsKeys.workspace(workspaceId),
        refetchType: "active",
      });
    },
  });
}
