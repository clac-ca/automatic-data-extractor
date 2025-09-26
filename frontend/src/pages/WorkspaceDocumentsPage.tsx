import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { useDocumentTypeSelection } from "../app/document-types/useDocumentTypeSelection";
import { useWorkspaceContextQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";
import { useActiveConfigurationsQuery, useWorkspaceDocumentsQuery } from "../app/documents/hooks";
import { buildDocumentDownloadUrl } from "../api/documents";
import { DocumentUploadPanel } from "../features/documents/components/DocumentUploadPanel";
import { formatByteSize, formatDateTime } from "../utils/format";

export function WorkspaceDocumentsPage() {
  const params = useParams();
  const routeWorkspaceId = params.workspaceId ?? null;
  const { setSelectedWorkspaceId } = useWorkspaceSelection();

  const { data: workspaceContext } = useWorkspaceContextQuery(routeWorkspaceId);
  const workspace = workspaceContext?.workspace;
  const workspaceId = workspace?.workspace_id ?? null;

  useEffect(() => {
    if (workspaceId) {
      setSelectedWorkspaceId(workspaceId);
    }
  }, [workspaceId, setSelectedWorkspaceId]);

  const { data: configurations = [] } = useActiveConfigurationsQuery(workspaceId);
  const { documentType } = useDocumentTypeSelection(workspaceId, configurations);

  const { data: documents = [], isLoading } = useWorkspaceDocumentsQuery(
    workspaceId,
    documentType,
  );

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-subtitle">
            {workspace ? workspace.name : "Select a workspace to manage documents."}
          </p>
        </div>
      </div>
      <section className="card document-library">
        <h2 className="card-title">Library</h2>
        {isLoading ? (
          <div className="empty-state">Loading documents…</div>
        ) : documents.length === 0 ? (
          <div className="empty-state">No documents found for this document type yet.</div>
        ) : (
          <div className="card-section">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Filename</th>
                  <th scope="col">Uploaded</th>
                  <th scope="col">Size</th>
                  <th scope="col">Expires</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td>{document.filename}</td>
                    <td>{formatDateTime(document.createdAt)}</td>
                    <td>{formatByteSize(document.byteSize)}</td>
                    <td>{document.expiresAt ? formatDateTime(document.expiresAt) : "—"}</td>
                    <td>
                      {workspaceId ? (
                        <a
                          className="button-ghost"
                          href={buildDocumentDownloadUrl(workspaceId, document.id)}
                        >
                          Download
                        </a>
                      ) : (
                        <span className="muted">Download</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {workspaceId ? (
        <DocumentUploadPanel
          workspaceId={workspaceId}
          documentType={documentType}
          configurations={configurations}
        />
      ) : (
        <section className="card document-upload">
          <h2 className="card-title">Upload documents</h2>
          <div className="empty-state">
            Choose a workspace to start uploading documents.
          </div>
        </section>
      )}
    </div>
  );
}
