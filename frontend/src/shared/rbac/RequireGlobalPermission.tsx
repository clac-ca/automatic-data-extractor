import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";

interface RequireGlobalPermissionProps {
  needed: string;
  children: ReactNode;
}

export function RequireGlobalPermission({ needed, children }: RequireGlobalPermissionProps) {
  const { data, isLoading, error } = useSessionQuery();

  if (isLoading) {
    return <div className="text-sm text-slate-300">Checking permissions…</div>;
  }

  if (error || !data) {
    return <Navigate to="/login" replace />;
  }

  const permissions = data.user.permissions ?? [];
  const allowed = !needed || permissions.includes(needed);

  if (!allowed) {
    return <Navigate to="/workspaces" replace />;
  }

  return <>{children}</>;
}
