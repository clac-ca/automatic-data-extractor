import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/page-grid.css";

export function WorkspaceConfigurationsPage(): JSX.Element {
  const { workspaceId } = useWorkspace();

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace to manage configurations."
      />
    );
  }

  return (
    <div className="page-grid">
      <PageHeader
        title="Configurations"
        description="Review configuration versions, activate updates, and maintain extraction fidelity."
        actions={
          <Button variant="primary" size="sm" disabled>
            New configuration
          </Button>
        }
        breadcrumb={<span>Workspace · Configurations</span>}
      />
      <EmptyState
        title="No configurations"
        description="Create a configuration or activate one provided by your admins."
      />
    </div>
  );
}
