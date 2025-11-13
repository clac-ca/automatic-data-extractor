import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useConfigQuery } from "@shared/configs/hooks/useConfigsQuery";

import { Workbench } from "./Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const configId = params?.configId;
  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId });

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration from the list to open the new workbench."
      />
    );
  }

  const configName = configQuery.data?.display_name ?? configId;

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <Workbench
        workspaceId={workspace.id}
        configId={configId}
        configName={`${workspace.name} · ${configName}`}
      />
    </div>
  );
}
