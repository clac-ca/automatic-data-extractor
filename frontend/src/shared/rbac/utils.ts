export type PermissionList = readonly string[] | undefined | null;

export function hasPermission(permissions: PermissionList, required: string): boolean {
  if (!required) {
    return true;
  }

  if (!permissions || permissions.length === 0) {
    return false;
  }

  return permissions.includes(required);
}

export function hasAnyPermission(permissions: PermissionList, required: readonly string[]): boolean {
  if (!permissions || permissions.length === 0) {
    return false;
  }

  return required.some((permission) => permissions.includes(permission));
}
