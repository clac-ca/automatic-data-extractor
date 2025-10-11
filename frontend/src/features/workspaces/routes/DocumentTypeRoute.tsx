import { useOutletContext, useParams } from "react-router-dom";

import { useDocumentTypeQuery } from "../hooks/useDocumentTypeQuery";
import { DocumentTypeDetailProvider, DocumentTypeDetailView } from "../documentTypes";
import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";

export function DocumentTypeRoute() {
  const params = useParams<{ workspaceId: string; documentTypeId: string }>();
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Select a workspace document to view its details.
      </div>
    );
  }

  const workspaceId = params.workspaceId ?? workspace.id;
  const documentTypeId = params.documentTypeId;

  if (!workspaceId || !documentTypeId) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Select a document type to view its details.
      </div>
    );
  }

  const {
    data,
    isLoading,
    error,
  } = useDocumentTypeQuery(workspaceId, documentTypeId);

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-300">
        Loading document type…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-200">
        We were unable to load this document type.
      </div>
    );
  }

  const workspaceName = workspace.name ?? workspaceId ?? "Workspace";

  return (
    <DocumentTypeDetailProvider documentType={data} workspaceName={workspaceName}>
      <DocumentTypeDetailView />
    </DocumentTypeDetailProvider>
  );
}
