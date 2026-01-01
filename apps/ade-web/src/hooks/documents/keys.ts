import type { DocumentsFilters } from "@pages/Workspace/sections/Documents/types";

type DocumentListOptions = {
  readonly sort: string | null;
  readonly pageSize: number;
  readonly filters?: DocumentsFilters;
  readonly search?: string;
};

export const documentsKeys = {
  root: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.root(), workspaceId] as const,
  list: (workspaceId: string, options: DocumentListOptions) =>
    [...documentsKeys.workspace(workspaceId), "list", options] as const,
  members: (workspaceId: string) => [...documentsKeys.workspace(workspaceId), "members"] as const,
  document: (workspaceId: string, documentId: string) =>
    [...documentsKeys.workspace(workspaceId), "document", documentId] as const,
  runsForDocument: (workspaceId: string, documentId: string) =>
    [...documentsKeys.workspace(workspaceId), "runs", { input_document_id: documentId }] as const,
  run: (runId: string) => [...documentsKeys.root(), "run", runId] as const,
  runMetrics: (runId: string) => [...documentsKeys.run(runId), "metrics"] as const,
  workbook: (url: string) => [...documentsKeys.root(), "workbook", url] as const,
};
