import { useQuery } from "@tanstack/react-query";

import type { WorkspaceDocumentsQueryOptions } from "../api";
import { workspaceDocumentsQueryOptions } from "../api";
import type { DocumentListResponse } from "@shared/types/documents";

export function useDocumentsQuery(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  return useQuery<DocumentListResponse>(workspaceDocumentsQueryOptions(workspaceId, options));
}

