import { createContext, useContext, useMemo } from "react";
import type { ReactNode } from "react";

import type { WorkspaceProfile } from "@shared/workspaces";

interface WorkspaceContextValue {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: WorkspaceProfile[];
  readonly permissions: readonly string[];
  hasPermission(permission: string): boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

interface WorkspaceProviderProps {
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
        const normalized = permission.toLowerCase();
        return permissions.includes(permission) || permissions.includes(normalized);
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
