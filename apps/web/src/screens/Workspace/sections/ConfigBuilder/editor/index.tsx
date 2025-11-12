import { useMemo } from "react";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { DemoMemoryAdapter } from "@screens/Workspace/sections/ConfigBuilder/api/adapters/DemoMemoryAdapter";
import { Workbench } from "@screens/Workspace/sections/ConfigBuilder/components/Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const configId = params?.configId;

  if (!configId) {
    return <PageState variant="error" title="Missing configuration" description="Select a configuration to open the editor." />;
  }

  const adapter = useMemo(() => new DemoMemoryAdapter({ workspaceId: workspace.id, configId }), [workspace.id, configId]);
  const storageKey = useMemo(
    () => `ade.ui.workspace.${workspace.id}.config.${configId}.editor`,
    [workspace.id, configId],
  );

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <Workbench adapter={adapter} storageKey={storageKey} />
    </div>
  );
}
