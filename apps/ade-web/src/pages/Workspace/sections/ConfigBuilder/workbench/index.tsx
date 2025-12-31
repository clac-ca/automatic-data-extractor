import { useEffect } from "react";

import { PageState } from "@components/PageState";

import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { useWorkbenchWindow } from "@pages/Workspace/context/WorkbenchWindowContext";
import { useConfigurationQuery } from "@hooks/configurations";

import { Workbench } from "./Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const {
    session,
    windowState,
    openSession,
    closeSession,
    minimizeWindow,
    maximizeWindow,
    restoreWindow,
    shouldBypassUnsavedGuard,
  } = useWorkbenchWindow();
  const configId = params?.configId;
  const configQuery = useConfigurationQuery({ workspaceId: workspace.id, configurationId: configId });

  useEffect(() => {
    if (configId) {
      return;
    }
    closeSession();
  }, [configId, closeSession]);

  useEffect(() => {
    if (!configId) {
      return;
    }
    if (configQuery.isError) {
      return;
    }
    const resolvedName = configQuery.data?.display_name ?? configId;
    openSession({
      workspaceId: workspace.id,
      configId,
      configName: `${workspace.name} · ${resolvedName}`,
      configDisplayName: resolvedName,
    });
  }, [configId, configQuery.data?.display_name, configQuery.isError, workspace.id, workspace.name, openSession]);

  useEffect(() => {
    if (!configId) {
      return;
    }
    if (configQuery.isError || (configQuery.isSuccess && !configQuery.data)) {
      closeSession();
    }
  }, [closeSession, configId, configQuery.data, configQuery.isError, configQuery.isSuccess]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration from the list to open the workbench."
      />
    );
  }

  if (configQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details before opening the workbench."
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

  const activeSession = session && session.configId === configId ? session : null;
  const isDocked = Boolean(activeSession && windowState === "minimized");
  const showWorkbenchInline = Boolean(activeSession && windowState === "restored");
  const showMaximizedNotice = Boolean(activeSession && windowState === "maximized");

  if (showWorkbenchInline && activeSession) {
    return (
      <div className="flex h-full min-h-0 flex-1 flex-col">
        <Workbench
          workspaceId={workspace.id}
          configId={activeSession.configId}
          configName={activeSession.configName}
          configDisplayName={configQuery.data.display_name ?? activeSession.configId}
          windowState="restored"
          onMinimizeWindow={minimizeWindow}
          onMaximizeWindow={maximizeWindow}
          onRestoreWindow={restoreWindow}
          onCloseWorkbench={closeSession}
          shouldBypassUnsavedGuard={shouldBypassUnsavedGuard}
        />
      </div>
    );
  }

  if (showMaximizedNotice) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="empty"
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
          variant="empty"
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
