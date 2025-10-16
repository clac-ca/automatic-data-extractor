/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo } from "react";
import type { ReactNode } from "react";

import type { WorkspaceProfile } from "../../../shared/types/workspaces";

export interface WorkspaceContextValue {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: WorkspaceProfile[];
  readonly permissions: readonly string[];
  hasPermission(permission: string): boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export interface WorkspaceProviderProps {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: WorkspaceProfile[];
  readonly children: ReactNode;
}

export function WorkspaceProvider({ workspace, workspaces, children }: WorkspaceProviderProps) {
  const value = useMemo<WorkspaceContextValue>(() => {
    const permissions = workspace.permissions;
    return {
      workspace,
      workspaces,
      permissions,
      hasPermission(permission: string) {
        return permissions.includes(permission);
      },
    };
  }, [workspace, workspaces]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspaceContext(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspaceContext must be used within a WorkspaceProvider");
  }
  return context;
}
