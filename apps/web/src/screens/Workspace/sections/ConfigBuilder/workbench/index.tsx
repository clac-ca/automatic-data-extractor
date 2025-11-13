import { useEffect } from "react";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { useConfigQuery } from "@shared/configs/hooks/useConfigsQuery";

import { Workbench } from "./Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const {
    session,
    focusMode,
    openSession,
    closeSession,
    setFocusMode,
    dockSession,
    shouldBypassUnsavedGuard,
  } = useWorkbenchWindow();
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
        description="Choose a configuration from the list to open the workbench."
      />
    );
  }

  const activeSession = session && session.configId === configId ? session : null;
  const isDocked = Boolean(activeSession && focusMode === "docked");
  const showWorkbenchInline = Boolean(activeSession && focusMode === "balanced");
  const showImmersiveNotice = Boolean(activeSession && focusMode === "immersive");

  if (showWorkbenchInline && activeSession) {
    return (
      <div className="flex h-full min-h-0 flex-1 flex-col">
        <Workbench
          workspaceId={workspace.id}
          configId={activeSession.configId}
          configName={activeSession.configName}
          focusMode={focusMode}
          onChangeFocusMode={setFocusMode}
          onDockWorkbench={dockSession}
          onCloseWorkbench={closeSession}
          shouldBypassUnsavedGuard={shouldBypassUnsavedGuard}
        />
      </div>
    );
  }

  if (showImmersiveNotice) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="info"
          title="Immersive focus active"
          description="Exit immersive mode from the workbench focus menu to return here."
        />
      </div>
    );
  }

  if (isDocked) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="info"
          title="Workbench docked"
          description="Use the dock at the bottom of the screen to resume editing."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
      <PageState
        variant="loading"
        title="Launching config workbench"
        description="If the editor does not appear, refresh the page."
      />
    </div>
  );
}
