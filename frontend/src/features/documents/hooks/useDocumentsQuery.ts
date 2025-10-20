import { useQuery } from "@tanstack/react-query";

import {
  workspaceDocumentsQueryOptions,
  type DocumentListResponse,
  type WorkspaceDocumentsQueryOptions,
} from "../api";

export function useDocumentsQuery(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  return useQuery<DocumentListResponse>(workspaceDocumentsQueryOptions(workspaceId, options));
}
