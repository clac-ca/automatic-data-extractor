import { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { buildWeakEtag } from "@/api/etag";
import { mapUiError } from "@/api/uiErrors";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  useAdminPermissionsQuery,
  useAdminRolesQuery,
  useCreateAdminRoleMutation,
  useDeleteAdminRoleMutation,
  useUpdateAdminRoleMutation,
} from "@/hooks/admin";
import type { AdminPermission, AdminRole } from "@/api/admin/roles";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";
import { useOrganizationSettingsSection } from "../sectionContext";

type RoleFormValues = {
  readonly name: string;
  readonly slug: string;
  readonly description: string;
  readonly permissions: string[];
};

type FeedbackTone = "success" | "danger";
type FeedbackMessage = { tone: FeedbackTone; message: string };

type PermissionGroupKey = "users" | "roles" | "apiKeys" | "system" | "workspaces" | "other";

const PERMISSION_GROUP_ORDER: readonly PermissionGroupKey[] = [
  "users",
  "roles",
  "apiKeys",
  "system",
  "workspaces",
  "other",
] as const;

const PERMISSION_GROUP_LABELS: Record<PermissionGroupKey, string> = {
  users: "Users",
  roles: "Roles",
  apiKeys: "API keys",
  system: "System",
  workspaces: "Workspaces",
  other: "Other",
};

const EMPTY_COLLAPSE_STATE: Record<PermissionGroupKey, boolean> = {
  users: false,
  roles: false,
  apiKeys: false,
  system: false,
  workspaces: false,
  other: false,
};

export function RolesSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const { params } = useOrganizationSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageRoles = hasPermission("roles.manage_all");
  const canReadRoles = hasPermission("roles.read_all") || canManageRoles;

  const rolesQuery = useAdminRolesQuery("global");
  const permissionsQuery = useAdminPermissionsQuery("global");

  const createRole = useCreateAdminRoleMutation();
  const updateRole = useUpdateAdminRoleMutation();
  const deleteRole = useDeleteAdminRoleMutation();

  const [feedbackMessage, setFeedbackMessage] = useState<FeedbackMessage | null>(null);

  const permissions = useMemo(() => permissionsQuery.data?.items ?? [], [permissionsQuery.data]);

  const roles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? []).slice().sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const roleCount = rolesQuery.data?.meta.totalCount ?? roles.length;
  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedRoleId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedRole = roles.find((role) => role.id === selectedRoleId);

  const basePath = "/organization/access/roles";
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openCreateDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openRoleDrawer = (roleId: string) => navigate(`${basePath}/${encodeURIComponent(roleId)}${suffix}`);

  const handleCreateRole = async (values: RoleFormValues) => {
    setFeedbackMessage(null);
    await createRole.mutateAsync({
      name: values.name.trim(),
      slug: values.slug.trim() || undefined,
      description: values.description.trim() || undefined,
      permissions: values.permissions,
    });
    setFeedbackMessage({ tone: "success", message: "Role created." });
    closeDrawer();
  };

  const handleUpdateRole = async (roleId: string, values: RoleFormValues) => {
    setFeedbackMessage(null);
    const ifMatch = buildWeakEtag(roleId, selectedRole?.updated_at ?? selectedRole?.created_at ?? null);
    await updateRole.mutateAsync({
      roleId,
      payload: {
        name: values.name.trim(),
        description: values.description.trim() || undefined,
        permissions: values.permissions,
      },
      ifMatch,
    });
    setFeedbackMessage({ tone: "success", message: "Role updated." });
    closeDrawer();
  };

  const handleDeleteRole = async (role: AdminRole) => {
    setFeedbackMessage(null);
    const ifMatch = buildWeakEtag(role.id, role.updated_at ?? role.created_at ?? null);
    await deleteRole.mutateAsync({ roleId: role.id, ifMatch });
    setFeedbackMessage({ tone: "success", message: `Deleted role "${role.name}".` });
    closeDrawer();
  };

  if (!canReadRoles) {
    return <Alert tone="danger">You do not have permission to access roles.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {rolesQuery.isError ? (
        <Alert tone="danger">{mapUiError(rolesQuery.error, { fallback: "Unable to load roles." }).message}</Alert>
      ) : null}
      {permissionsQuery.isError ? (
        <Alert tone="warning">
          {mapUiError(permissionsQuery.error, { fallback: "Unable to load permission catalog." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Global roles"
        description={rolesQuery.isLoading ? "Loading roles..." : `${roleCount} role${roleCount === 1 ? "" : "s"} total`}
        actions={
          canManageRoles ? (
            <Button type="button" size="sm" onClick={openCreateDrawer}>
              New role
            </Button>
          ) : null
        }
      >
        {rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading roles...</p>
        ) : roles.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No global roles yet.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={roles}
            getItemKey={(role) => role.id}
            mobileListLabel="Global roles"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Role</TableHead>
                      <TableHead className="px-4">Slug</TableHead>
                      <TableHead className="px-4">Permissions</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {roles.map((role) => (
                      <TableRow key={role.id} className="text-sm text-foreground">
                        <TableCell className="space-y-1 px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-foreground">{role.name}</p>
                            {role.is_system ? (
                              <Badge variant="secondary" className="text-[11px] uppercase tracking-wide">
                                System
                              </Badge>
                            ) : null}
                            {!role.is_editable ? (
                              <Badge
                                variant="outline"
                                className="border-border/60 text-[11px] uppercase tracking-wide text-muted-foreground"
                              >
                                Locked
                              </Badge>
                            ) : null}
                          </div>
                          {role.is_system || !role.is_editable ? (
                            <p className="text-xs text-muted-foreground">
                              {role.is_system
                                ? "Built-in role maintained by ADE."
                                : "Locked role cannot be modified."}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell className="px-4 py-3 font-mono text-xs text-muted-foreground">{role.slug}</TableCell>
                        <TableCell className="px-4 py-3 text-muted-foreground">
                          {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => openRoleDrawer(role.id)}
                            disabled={!canManageRoles && !hasPermission("roles.read_all")}
                          >
                            {canManageRoles ? "Manage" : "View"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(role) => (
              <>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground">{role.name}</p>
                    {role.is_system ? (
                      <Badge variant="secondary" className="text-[11px] uppercase tracking-wide">
                        System
                      </Badge>
                    ) : null}
                    {!role.is_editable ? (
                      <Badge
                        variant="outline"
                        className="border-border/60 text-[11px] uppercase tracking-wide text-muted-foreground"
                      >
                        Locked
                      </Badge>
                    ) : null}
                  </div>
                  {role.is_system || !role.is_editable ? (
                    <p className="text-xs text-muted-foreground">
                      {role.is_system ? "Built-in role maintained by ADE." : "Locked role cannot be modified."}
                    </p>
                  ) : null}
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Slug</dt>
                  <dd className="font-mono text-muted-foreground">{role.slug}</dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Permissions</dt>
                  <dd className="text-muted-foreground">
                    {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => openRoleDrawer(role.id)}>
                    {canManageRoles ? "Manage" : "View"}
                  </Button>
                </div>
              </>
            )}
          />
        )}

        {!canManageRoles ? (
          <Alert tone="info">You can view roles, but you need role management permission to edit them.</Alert>
        ) : null}
      </SettingsSection>

      <RoleDrawer
        open={isCreateOpen && canManageRoles}
        mode="create"
        canManage={canManageRoles}
        permissions={permissions}
        onClose={closeDrawer}
        onSave={(values) => handleCreateRole(values)}
        isSaving={createRole.isPending}
        isDeleting={false}
      />

      <RoleDrawer
        open={Boolean(selectedRoleId)}
        mode="edit"
        canManage={canManageRoles}
        role={selectedRole}
        permissions={permissions}
        onClose={closeDrawer}
        onSave={(values) => (selectedRoleId ? handleUpdateRole(selectedRoleId, values) : Promise.resolve())}
        onDelete={selectedRole ? () => handleDeleteRole(selectedRole) : undefined}
        isSaving={updateRole.isPending}
        isDeleting={deleteRole.isPending}
      />
    </div>
  );
}

interface RoleDrawerProps {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly canManage: boolean;
  readonly role?: AdminRole;
  readonly permissions: readonly AdminPermission[];
  readonly onClose: () => void;
  readonly onSave: (values: RoleFormValues) => Promise<void>;
  readonly onDelete?: () => Promise<void>;
  readonly isSaving: boolean;
  readonly isDeleting: boolean;
}

function RoleDrawer({
  open,
  mode,
  canManage,
  role,
  permissions,
  onClose,
  onSave,
  onDelete,
  isSaving,
  isDeleting,
}: RoleDrawerProps) {
  const [values, setValues] = useState<RoleFormValues>({
    name: "",
    slug: "",
    description: "",
    permissions: [],
  });
  const [permissionFilter, setPermissionFilter] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmInput, setConfirmInput] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<PermissionGroupKey, boolean>>({
    ...EMPTY_COLLAPSE_STATE,
  });

  useEffect(() => {
    if (!open) {
      setFeedback(null);
      setPermissionFilter("");
      setSubmitAttempted(false);
      setConfirmDelete(false);
      setConfirmInput("");
      setCollapsedGroups({ ...EMPTY_COLLAPSE_STATE });
      return;
    }
    if (mode === "edit" && role) {
      setValues({
        name: role.name,
        slug: role.slug,
        description: role.description ?? "",
        permissions: role.permissions,
      });
    } else {
      setValues({
        name: "",
        slug: "",
        description: "",
        permissions: [],
      });
    }
  }, [mode, open, role]);

  const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const roleMissing = mode === "edit" && !role;
  const canEditRole = canManage && (mode === "create" || (role?.is_editable ?? false));
  const canDeleteRole =
    canManage && mode === "edit" && role && role.is_editable && !role.is_system && Boolean(onDelete);

  const trimmedName = values.name.trim();
  const trimmedSlug = values.slug.trim();
  const nameError = !trimmedName ? "Role name is required." : null;
  const slugError =
    mode === "create" && trimmedSlug.length > 0 && !slugPattern.test(trimmedSlug)
      ? "Use lowercase letters, numbers, and dashes for the role slug."
      : null;

  const filteredPermissions = useMemo(() => {
    const term = permissionFilter.trim().toLowerCase();
    if (!term) {
      return permissions;
    }
    return permissions.filter((permission) => {
      const haystack = `${permission.label} ${permission.key}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [permissionFilter, permissions]);

  const groupedPermissions = useMemo(() => {
    const grouped = new Map<PermissionGroupKey, AdminPermission[]>();
    for (const groupKey of PERMISSION_GROUP_ORDER) {
      grouped.set(groupKey, []);
    }
    for (const permission of filteredPermissions) {
      const groupKey = getPermissionGroupKey(permission.key);
      const current = grouped.get(groupKey);
      if (current) {
        current.push(permission);
      }
    }

    return PERMISSION_GROUP_ORDER.map((groupKey) => ({
      key: groupKey,
      label: PERMISSION_GROUP_LABELS[groupKey],
      items: grouped.get(groupKey) ?? [],
      selectedCount: (grouped.get(groupKey) ?? []).filter((permission) =>
        values.permissions.includes(permission.key),
      ).length,
      totalCount: grouped.get(groupKey)?.length ?? 0,
    })).filter((group) => group.totalCount > 0);
  }, [filteredPermissions, values.permissions]);

  const togglePermission = (permissionKey: string, selected: boolean) => {
    setValues((current) => ({
      ...current,
      permissions: selected
        ? Array.from(new Set([...(current.permissions ?? []), permissionKey]))
        : (current.permissions ?? []).filter((key) => key !== permissionKey),
    }));
  };

  const handleSave = async () => {
    setSubmitAttempted(true);
    setFeedback(null);

    if (roleMissing) {
      setFeedback("This role could not be found.");
      return;
    }
    if (nameError || slugError) {
      return;
    }

    try {
      await onSave({
        ...values,
        name: trimmedName,
        slug: mode === "create" ? trimmedSlug : role?.slug ?? "",
        description: values.description.trim(),
        permissions: values.permissions,
      });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: mode === "create" ? "Unable to create role." : "Unable to update role.",
      });
      setFeedback(mapped.message);
    }
  };

  const handleDelete = async () => {
    if (!onDelete || !role) {
      return;
    }
    setFeedback(null);
    try {
      await onDelete();
    } catch (error) {
      const mapped = mapUiError(error, { fallback: "Unable to delete role." });
      setFeedback(mapped.message);
    } finally {
      setConfirmDelete(false);
      setConfirmInput("");
    }
  };

  const footer = (
    <div className="flex items-center justify-between gap-2">
      <Button type="button" variant="ghost" onClick={onClose} disabled={isSaving || isDeleting}>
        Close
      </Button>
      <div className="flex items-center gap-2">
        {canDeleteRole ? (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setConfirmDelete(true)}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        ) : null}
        {canManage ? (
          <Button type="button" onClick={handleSave} disabled={roleMissing || !canEditRole || isSaving}>
            {isSaving ? "Saving..." : mode === "create" ? "Create role" : "Save changes"}
          </Button>
        ) : null}
      </div>
    </div>
  );

  const title = mode === "create" ? "New role" : role?.name ?? "Role details";

  return (
    <>
      <SettingsDrawer
        open={open}
        onClose={onClose}
        title={title}
        description={mode === "create" ? "Create a global role." : "Edit global role details and permissions."}
        footer={footer}
      >
        {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
        {mode === "edit" && role && !role.is_editable ? (
          <Alert tone="warning">This role is locked and cannot be modified.</Alert>
        ) : null}
        {!canManage && mode === "edit" ? (
          <Alert tone="info">Read-only view. You need role management permission to make changes.</Alert>
        ) : null}

        {roleMissing ? (
          <Alert tone="warning">This role could not be found.</Alert>
        ) : (
          <div className="space-y-4">
            <FormField label="Role name" required error={submitAttempted ? nameError : null}>
              <Input
                value={values.name}
                onChange={(event) => setValues((current) => ({ ...current, name: event.target.value }))}
                placeholder="Security reviewer"
                disabled={isSaving || !canEditRole}
              />
            </FormField>

            {mode === "create" ? (
              <FormField
                label="Role slug"
                hint="Lowercase, URL-friendly identifier. Leave blank to auto-generate."
                error={submitAttempted ? slugError : null}
              >
                <Input
                  value={values.slug}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, slug: event.target.value.toLowerCase() }))
                  }
                  placeholder="security-reviewer"
                  disabled={isSaving || !canEditRole}
                />
              </FormField>
            ) : (
              <FormField label="Role slug" hint="System and locked roles preserve their current slug.">
                <Input value={role?.slug ?? ""} disabled />
              </FormField>
            )}

            <FormField label="Description" hint="Optional context about what this role controls.">
              <Input
                value={values.description}
                onChange={(event) => setValues((current) => ({ ...current, description: event.target.value }))}
                placeholder="What does this role control?"
                disabled={isSaving || !canEditRole}
              />
            </FormField>

            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-foreground">Permissions</p>
                  <p className="text-xs text-muted-foreground">
                    Select permissions included with this role. {values.permissions.length} selected.
                  </p>
                </div>
                <Input
                  value={permissionFilter}
                  onChange={(event) => setPermissionFilter(event.target.value)}
                  placeholder="Filter permissions"
                  disabled={isSaving}
                  className="w-full sm:w-64"
                />
              </div>

              <div className="max-h-[26rem] space-y-2 overflow-y-auto rounded-lg border border-border bg-background p-3">
                {groupedPermissions.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No permissions match this filter.</p>
                ) : (
                  groupedPermissions.map((group) => {
                    const collapsed = collapsedGroups[group.key];
                    return (
                      <Collapsible
                        key={group.key}
                        open={!collapsed}
                        onOpenChange={(open) =>
                          setCollapsedGroups((current) => ({ ...current, [group.key]: !open }))
                        }
                        className="rounded-lg border border-border"
                      >
                        <CollapsibleTrigger asChild>
                          <button
                            type="button"
                            className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
                          >
                            <div>
                              <p className="text-sm font-semibold text-foreground">{group.label}</p>
                              <p className="text-xs text-muted-foreground">
                                {group.selectedCount} of {group.totalCount} selected
                              </p>
                            </div>
                            <ChevronDown className={`h-4 w-4 text-muted-foreground transition ${collapsed ? "-rotate-90" : "rotate-0"}`} />
                          </button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <div className="space-y-2 border-t border-border/70 px-3 py-3">
                            {group.items.map((permission) => {
                              const checkboxId = `permission-${permission.key.replaceAll(".", "-")}`;
                              return (
                                <label
                                  key={permission.key}
                                  htmlFor={checkboxId}
                                  className="flex items-start gap-3 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
                                >
                                  <input
                                    id={checkboxId}
                                    type="checkbox"
                                    aria-label={permission.label}
                                    className="mt-1 h-4 w-4 rounded border-border"
                                    checked={values.permissions.includes(permission.key)}
                                    onChange={(event) => togglePermission(permission.key, event.target.checked)}
                                    disabled={isSaving || !canEditRole}
                                  />
                                  <span>
                                    <span className="block font-semibold">{permission.label}</span>
                                    <span className="block text-xs text-muted-foreground">{permission.description}</span>
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </CollapsibleContent>
                      </Collapsible>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </SettingsDrawer>

      <ConfirmDialog
        open={confirmDelete && Boolean(role)}
        title="Delete this role?"
        description="Deleting this role removes it from users currently assigned to it."
        confirmLabel="Delete role"
        tone="danger"
        confirmDisabled={confirmInput.trim() !== (role?.slug ?? "")}
        onCancel={() => {
          setConfirmDelete(false);
          setConfirmInput("");
        }}
        onConfirm={handleDelete}
        isConfirming={isDeleting}
      >
        <FormField label="Type the role slug to confirm" required>
          <Input
            value={confirmInput}
            onChange={(event) => setConfirmInput(event.target.value)}
            placeholder={role?.slug ?? "role-slug"}
            disabled={isDeleting}
          />
        </FormField>
      </ConfirmDialog>
    </>
  );
}

function getPermissionGroupKey(permissionKey: string): PermissionGroupKey {
  if (permissionKey.startsWith("users.")) {
    return "users";
  }
  if (permissionKey.startsWith("roles.")) {
    return "roles";
  }
  if (permissionKey.startsWith("api_keys.")) {
    return "apiKeys";
  }
  if (permissionKey.startsWith("system.")) {
    return "system";
  }
  if (permissionKey.startsWith("workspace.") || permissionKey.startsWith("workspaces.")) {
    return "workspaces";
  }
  return "other";
}
