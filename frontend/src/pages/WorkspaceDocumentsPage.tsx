import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/page-grid.css";

export function WorkspaceDocumentsPage(): JSX.Element {
  const { workspaceId, documentType } = useWorkspace();

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace to view its document library."
      />
    );
  }

  return (
    <div className="page-grid">
      <PageHeader
        title="Documents"
        description="Upload documents, manage metadata, and monitor extraction readiness."
        actions={
          <Button variant="primary" size="sm" disabled>
            Upload documents
          </Button>
        }
        breadcrumb={<span>Workspace · Documents</span>}
      />
      <EmptyState
        title="No documents match the current filters"
        description={
          documentType
            ? `There are no documents tagged with the selected document type.`
            : "Upload a document to begin extraction."
        }
        action={
          <Button variant="secondary" size="sm" disabled>
            Upload document
          </Button>
        }
      />
    </div>
  );
}
