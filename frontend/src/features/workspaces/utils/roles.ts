export function formatRoleSlug(slug: string): string {
  return slug
    .split("-")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatRoleList(roles: readonly string[] | null | undefined): string {
  if (!roles || roles.length === 0) {
    return "";
  }

  return roles.map(formatRoleSlug).join(", ");
}
