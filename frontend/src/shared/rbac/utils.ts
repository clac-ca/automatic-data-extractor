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

