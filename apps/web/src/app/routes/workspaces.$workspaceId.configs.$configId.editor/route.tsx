import { useMemo } from "react";
import { useParams } from "react-router";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import { DemoMemoryAdapter } from "./adapters/DemoMemoryAdapter";
import { Workbench } from "./components/Workbench";

export default function ConfigEditorWorkbenchRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId;

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
