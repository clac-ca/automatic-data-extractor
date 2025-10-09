import type { ReactNode } from "react";
import { Navigate, useOutletContext, useParams } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../../features/workspaces/components/WorkspaceLayout";

interface RequirePermissionProps {
  needed: string;
  children: ReactNode;
}

export function RequirePermission({ needed, children }: RequirePermissionProps) {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();
  const { workspaceId } = useParams();
  const permissions = workspace?.permissions ?? [];
  const allowed = !needed || permissions.includes(needed);

  if (!allowed) {
    const destination = workspaceId ? `/workspaces/${workspaceId}` : "/workspaces";
    return <Navigate to={destination} replace />;
  }

  return <>{children}</>;
}
