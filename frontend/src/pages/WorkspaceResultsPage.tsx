import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/page-grid.css";

export function WorkspaceResultsPage(): JSX.Element {
  const { workspaceId, documentType } = useWorkspace();

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace to browse extraction results."
      />
    );
  }

  return (
    <div className="page-grid">
      <PageHeader
        title="Results"
        description="Review extracted tables, compare runs, and export clean datasets."
        breadcrumb={<span>Workspace · Results</span>}
        actions={
          <Button variant="secondary" size="sm" disabled>
            Export tables
          </Button>
        }
      />
      <EmptyState
        title="No results available"
        description={
          documentType
            ? "Run a job for this document type to see results here."
            : "Once jobs complete, their tables will appear in the results explorer."
        }
      />
    </div>
  );
}
