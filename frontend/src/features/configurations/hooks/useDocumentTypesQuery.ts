import { useQuery } from "@tanstack/react-query";

import { listActiveConfigurations } from "@api/configurations";
import { useApiClient } from "@hooks/useApiClient";

import { mapConfigurationsToDocumentTypes, type DocumentTypeOption } from "@features/workspaces/types";

interface DocumentTypesResult {
  readonly documentTypes: DocumentTypeOption[];
}

export function useDocumentTypesQuery(workspaceId: string | null) {
  const client = useApiClient();

  return useQuery<DocumentTypesResult, Error>({
    queryKey: ["workspace-document-types", workspaceId],
    enabled: Boolean(workspaceId),
    queryFn: async () => {
      if (!workspaceId) {
        return { documentTypes: [] };
      }

      const configurations = await listActiveConfigurations(client, workspaceId);
      return {
        documentTypes: mapConfigurationsToDocumentTypes(configurations)
      };
    }
  });
}
