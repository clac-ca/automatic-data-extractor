import { matchPath } from "react-router-dom";

import type { WorkspaceProfile } from "@/types/workspaces";
import { settingsPaths, type PermissionRequirement, type SettingsRouteContext } from "./contracts";

export function normalizePermissionSet(values: readonly string[]): Set<string> {
  return new Set(values.map((value) => value.trim().toLowerCase()).filter(Boolean));
}

export function hasRequiredGlobalPermission(
  requirement: PermissionRequirement | undefined,
  globalPermissions: ReadonlySet<string>,
) {
  const globalAny = requirement?.globalAny ?? [];
  if (globalAny.length === 0) {
    return true;
  }
  return globalAny.some((permission) => globalPermissions.has(permission.toLowerCase()));
}

export function hasRequiredWorkspacePermission(
  requirement: PermissionRequirement | undefined,
  workspace: WorkspaceProfile | null,
) {
  const workspaceAny = requirement?.workspaceAny ?? [];
  if (workspaceAny.length === 0) {
    return true;
  }
  if (!workspace) {
    return false;
  }

  const workspacePermissions = new Set(
    (workspace.permissions ?? []).map((permission) => permission.trim().toLowerCase()),
  );
  return workspaceAny.some((permission) => workspacePermissions.has(permission.toLowerCase()));
}

export function parseSettingsRouteContext(pathname: string): SettingsRouteContext {
  if (pathname === "/settings") {
    return { scope: "home", section: "home" };
  }

  if (pathname === settingsPaths.organization.usersCreate) {
    return { scope: "organization", section: "users.create" };
  }

  if (pathname === settingsPaths.organization.groupsCreate) {
    return { scope: "organization", section: "groups.create" };
  }

  if (pathname === settingsPaths.organization.rolesCreate) {
    return { scope: "organization", section: "roles.create" };
  }

  const workspacePrincipalCreate = matchPath(
    "/settings/workspaces/:workspaceId/access/principals/create",
    pathname,
  );
  if (workspacePrincipalCreate) {
    return {
      scope: "workspaces",
      section: "principals.create",
      workspaceId: decodeURIComponent(workspacePrincipalCreate.params.workspaceId ?? ""),
    };
  }

  const workspaceRoleCreate = matchPath(
    "/settings/workspaces/:workspaceId/access/roles/create",
    pathname,
  );
  if (workspaceRoleCreate) {
    return {
      scope: "workspaces",
      section: "roles.create",
      workspaceId: decodeURIComponent(workspaceRoleCreate.params.workspaceId ?? ""),
    };
  }

  const workspaceInvitationCreate = matchPath(
    "/settings/workspaces/:workspaceId/access/invitations/create",
    pathname,
  );
  if (workspaceInvitationCreate) {
    return {
      scope: "workspaces",
      section: "invitations.create",
      workspaceId: decodeURIComponent(workspaceInvitationCreate.params.workspaceId ?? ""),
    };
  }

  const orgUserDetail = matchPath("/settings/organization/users/:userId", pathname);
  if (orgUserDetail) {
    return {
      scope: "organization",
      section: "users.detail",
      entityType: "organizationUser",
      entityId: decodeURIComponent(orgUserDetail.params.userId ?? ""),
    };
  }

  const orgGroupDetail = matchPath("/settings/organization/groups/:groupId", pathname);
  if (orgGroupDetail) {
    return {
      scope: "organization",
      section: "groups.detail",
      entityType: "organizationGroup",
      entityId: decodeURIComponent(orgGroupDetail.params.groupId ?? ""),
    };
  }

  const orgRoleDetail = matchPath("/settings/organization/roles/:roleId", pathname);
  if (orgRoleDetail) {
    return {
      scope: "organization",
      section: "roles.detail",
      entityType: "organizationRole",
      entityId: decodeURIComponent(orgRoleDetail.params.roleId ?? ""),
    };
  }

  const workspacePrincipalDetail = matchPath(
    "/settings/workspaces/:workspaceId/access/principals/:principalType/:principalId",
    pathname,
  );
  if (workspacePrincipalDetail) {
    return {
      scope: "workspaces",
      section: "principals.detail",
      entityType: "workspacePrincipal",
      entityId: decodeURIComponent(workspacePrincipalDetail.params.principalId ?? ""),
      workspaceId: decodeURIComponent(workspacePrincipalDetail.params.workspaceId ?? ""),
    };
  }

  const workspaceRoleDetail = matchPath(
    "/settings/workspaces/:workspaceId/access/roles/:roleId",
    pathname,
  );
  if (workspaceRoleDetail) {
    return {
      scope: "workspaces",
      section: "roles.detail",
      entityType: "workspaceRole",
      entityId: decodeURIComponent(workspaceRoleDetail.params.roleId ?? ""),
      workspaceId: decodeURIComponent(workspaceRoleDetail.params.workspaceId ?? ""),
    };
  }

  const workspaceInvitationDetail = matchPath(
    "/settings/workspaces/:workspaceId/access/invitations/:invitationId",
    pathname,
  );
  if (workspaceInvitationDetail) {
    return {
      scope: "workspaces",
      section: "invitations.detail",
      entityType: "workspaceInvitation",
      entityId: decodeURIComponent(workspaceInvitationDetail.params.invitationId ?? ""),
      workspaceId: decodeURIComponent(workspaceInvitationDetail.params.workspaceId ?? ""),
    };
  }

  if (pathname.startsWith("/settings/organization/")) {
    return { scope: "organization", section: pathname.replace("/settings/organization/", "") };
  }

  const workspaceMatch = matchPath("/settings/workspaces/:workspaceId/*", pathname);
  if (workspaceMatch) {
    const workspaceId = decodeURIComponent(workspaceMatch.params.workspaceId ?? "");
    const segment = pathname.replace(`/settings/workspaces/${workspaceMatch.params.workspaceId ?? ""}/`, "");
    return { scope: "workspaces", workspaceId, section: segment || "general" };
  }

  if (pathname === "/settings/workspaces") {
    return { scope: "workspaces", section: "list" };
  }

  return { scope: "home", section: "home" };
}
