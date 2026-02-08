import { useNavigate } from "react-router-dom";

import { PageState } from "@/components/layout";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useConfigurationQuery } from "@/pages/Workspace/hooks/configurations";

import { buildConfigurationsPath } from "../paths";
import { Workbench } from "./Workbench";

interface ConfigurationEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigurationEditorWorkbenchRoute({
  params,
}: ConfigurationEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const configId = params?.configId;
  const configQuery = useConfigurationQuery({ workspaceId: workspace.id, configurationId: configId });
  const awaitingFreshConfigSnapshot = Boolean(configId) && !configQuery.isError && !configQuery.isFetchedAfterMount;

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration to open the editor."
      />
    );
  }

  if (configQuery.isLoading || awaitingFreshConfigSnapshot) {
    return (
      <PageState
        variant="loading"
        title="Refreshing configuration"
        description="Checking the latest configuration status before opening the editor."
      />
    );
  }

  if (configQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration"
        description="Try refreshing the page or pick a different configuration."
      />
    );
  }

  if (!configQuery.data) {
    return (
      <PageState
        variant="error"
        title="Configuration unavailable"
        description="The selected configuration could not be found. It may have been deleted."
      />
    );
  }

  const configDisplayName = configQuery.data.display_name ?? configId;

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <Workbench
        workspaceId={workspace.id}
        configId={configId}
        configDisplayName={configDisplayName}
        onCloseWorkbench={() => navigate(buildConfigurationsPath(workspace.id))}
      />
    </div>
  );
}
