import { useCallback, useMemo } from "react";

import { useSession } from "@/providers/auth/SessionContext";

export const ORG_SETTINGS_PERMISSIONS = [
  "users.read_all",
  "users.manage_all",
  "roles.read_all",
  "roles.manage_all",
  "api_keys.read_all",
  "api_keys.manage_all",
  "system.settings.read",
  "system.settings.manage",
] as const;

export function useGlobalPermissions() {
  const session = useSession();

  const permissionSet = useMemo(() => {
    const values = [
      ...(session.permissions ?? []),
      ...(session.user.permissions ?? []),
    ]
      .map((permission) => permission.trim().toLowerCase())
      .filter(Boolean);
    return new Set(values);
  }, [session.permissions, session.user.permissions]);

  const hasPermission = useCallback(
    (permission: string) => permissionSet.has(permission.toLowerCase()),
    [permissionSet],
  );

  const hasAnyPermission = useCallback(
    (permissions: readonly string[]) => permissions.some((permission) => hasPermission(permission)),
    [hasPermission],
  );

  const canAccessOrganizationSettings = hasAnyPermission(ORG_SETTINGS_PERMISSIONS);
  const canManageApiKeys = hasPermission("api_keys.manage_all");
  const canReadApiKeys = canManageApiKeys || hasPermission("api_keys.read_all");

  return {
    permissions: permissionSet,
    hasPermission,
    hasAnyPermission,
    canAccessOrganizationSettings,
    canManageApiKeys,
    canReadApiKeys,
  };
}
