import { useQuery } from "@tanstack/react-query";

import { fetchDocumentType } from "../api";
import { workspaceKeys } from "./workspaceKeys";

export function useDocumentTypeQuery(workspaceId: string, documentTypeId: string) {
  return useQuery({
    queryKey: workspaceKeys.documentType(workspaceId, documentTypeId),
    queryFn: () => fetchDocumentType(workspaceId, documentTypeId),
    staleTime: 30_000,
  });
}
