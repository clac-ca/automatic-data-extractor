import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteWorkspaceDocuments } from "../api";
import { documentKeys } from "./useWorkspaceDocumentsQuery";

export function useDeleteDocumentsMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentIds: readonly string[]) => {
      await deleteWorkspaceDocuments(workspaceId, documentIds);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: documentKeys.list(workspaceId) });
    },
  });
}
