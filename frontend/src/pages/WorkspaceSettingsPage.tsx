import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/page-grid.css";

export function WorkspaceSettingsPage(): JSX.Element {
  const { workspaceId } = useWorkspace();

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace to update its settings."
      />
    );
  }

  return (
    <div className="page-grid">
      <PageHeader
        title="Workspace settings"
        description="Manage workspace metadata, memberships, and defaults."
        breadcrumb={<span>Workspace · Settings</span>}
        actions={
          <Button variant="primary" size="sm" disabled>
            Save changes
          </Button>
        }
      />
      <EmptyState
        title="Settings editor coming soon"
        description="Workspace admins will be able to edit metadata and membership from here."
      />
    </div>
  );
}
