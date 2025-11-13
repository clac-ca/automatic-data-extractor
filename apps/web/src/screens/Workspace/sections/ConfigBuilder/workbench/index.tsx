import { useEffect } from "react";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { useConfigQuery } from "@shared/configs/hooks/useConfigsQuery";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const { openSession, closeSession } = useWorkbenchWindow();
  const configId = params?.configId;
  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId });

  useEffect(() => {
    if (!configId) {
      closeSession();
      return;
    }
    const resolvedName = configQuery.data?.display_name ?? configId;
    openSession({
      workspaceId: workspace.id,
      configId,
      configName: `${workspace.name} · ${resolvedName}`,
    });
  }, [configId, configQuery.data?.display_name, workspace.id, workspace.name, openSession, closeSession]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration from the list to open the new workbench."
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col items-center justify-center px-4 py-6">
      <PageState
        variant="loading"
        title="Launching config workbench"
        description="If the editor does not appear, refresh the page."
      />
    </div>
  );
}
