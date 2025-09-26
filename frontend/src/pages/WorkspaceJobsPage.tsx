import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/page-grid.css";

export function WorkspaceJobsPage(): JSX.Element {
  const { workspaceId } = useWorkspace();

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace to inspect its extraction jobs."
      />
    );
  }

  return (
    <div className="page-grid">
      <PageHeader
        title="Jobs"
        description="Track job processing status, retry failed runs, and review outputs."
        actions={
          <Button variant="primary" size="sm" disabled>
            New job
          </Button>
        }
        breadcrumb={<span>Workspace · Jobs</span>}
      />
      <EmptyState
        title="No jobs yet"
        description="Submit a job to transform uploaded documents into structured tables."
        action={
          <Button variant="secondary" size="sm" disabled>
            Create job
          </Button>
        }
      />
    </div>
  );
}
