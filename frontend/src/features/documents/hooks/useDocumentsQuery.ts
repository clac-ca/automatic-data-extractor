import { useQuery } from "@tanstack/react-query";

import type { WorkspaceDocumentsQueryOptions } from "../api/queries";
import { workspaceDocumentsQueryOptions } from "../api/queries";
import type { DocumentListResponse } from "../../../shared/types/documents";

export function useDocumentsQuery(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  return useQuery<DocumentListResponse>(workspaceDocumentsQueryOptions(workspaceId, options));
}

