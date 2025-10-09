import type { ReactNode } from "react";
import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../../features/workspaces/components/WorkspaceLayout";
import { hasAnyPermission } from "./utils";

interface RequirePermissionProps {
  needed: string | readonly string[];
  mode?: "any" | "all";
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequirePermission({ needed, mode = "any", children, fallback = null }: RequirePermissionProps) {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();
  const permissions = workspace?.permissions ?? [];
  const required = Array.isArray(needed) ? needed : [needed];

  const allowed =
    required.length === 0 ||
    (mode === "all"
      ? required.every((permission) => permissions.includes(permission))
      : hasAnyPermission(permissions, required));

  if (!allowed) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
