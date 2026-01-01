import { useEffect, useMemo, useState } from "react";

import { useLocation, useNavigate } from "@app/navigation/history";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { useSettingsSection } from "../sectionContext";
import { buildWeakEtag } from "@api/etag";
import {
  useCreateWorkspaceRoleMutation,
  useDeleteWorkspaceRoleMutation,
  usePermissionsQuery,
  useUpdateWorkspaceRoleMutation,
  useWorkspaceRolesQuery,
} from "../hooks/useWorkspaceRoles";
import type { PermissionDefinition, RoleDefinition } from "@schema/workspaces";
import { Alert } from "@components/ui/alert";
import { ConfirmDialog } from "@components/ui/confirm-dialog";
import { FormField } from "@components/ui/form-field";
import { Button } from "@components/tablecn/ui/button";
import { Input } from "@components/tablecn/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@components/tablecn/ui/table";
import { Badge } from "@components/tablecn/ui/badge";
import { SettingsPanel } from "../components/SettingsPanel";

type RoleFormValues = {
  readonly name: string;
  readonly slug: string;
  readonly description: string;
  readonly permissions: string[];
};

export function RolesSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const { params } = useSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageRoles = hasPermission("workspace.roles.manage");

  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const permissionsQuery = usePermissionsQuery();

  const createRole = useCreateWorkspaceRoleMutation(workspace.id);
  const updateRole = useUpdateWorkspaceRoleMutation(workspace.id);
  const deleteRole = useDeleteWorkspaceRoleMutation(workspace.id);

  const [roleSearch, setRoleSearch] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const permissions = useMemo(
    () => (permissionsQuery.data?.items ?? []).filter((permission) => permission.scope_type === "workspace"),
    [permissionsQuery.data],
  );

  const roles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? []).slice().sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const roleCount = rolesQuery.data?.total ?? roles.length;
  const normalizedRoleSearch = roleSearch.trim().toLowerCase();
  const filteredRoles = useMemo(() => {
    if (!normalizedRoleSearch) {
      return roles;
    }
    return roles.filter((role) => {
      const haystack = `${role.name} ${role.slug ?? ""}`.toLowerCase();
      return haystack.includes(normalizedRoleSearch);
    });
  }, [normalizedRoleSearch, roles]);

  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedRoleId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedRole = roles.find((role) => role.id === selectedRoleId);

  const basePath = `/workspaces/${workspace.id}/settings/access/roles`;
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openCreateDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openRoleDrawer = (roleId: string) =>
    navigate(`${basePath}/${encodeURIComponent(roleId)}${suffix}`);

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
    const ifMatch = buildWeakEtag(roleId, selectedRole?.updatedAt ?? selectedRole?.createdAt ?? null);
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

  const handleDeleteRole = async (role: RoleDefinition) => {
    setFeedbackMessage(null);
    const ifMatch = buildWeakEtag(role.id, role.updatedAt ?? role.createdAt ?? null);
    await deleteRole.mutateAsync({ roleId: role.id, ifMatch });
    setFeedbackMessage({ tone: "success", message: `Deleted role "${role.name}".` });
    closeDrawer();
  };

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {rolesQuery.isError ? (
        <Alert tone="danger">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}
      {permissionsQuery.isError ? (
        <Alert tone="warning">
          {permissionsQuery.error instanceof Error ? permissionsQuery.error.message : "Unable to load permission catalog."}
        </Alert>
      ) : null}

      <SettingsPanel
        title="Workspace roles"
        description={rolesQuery.isLoading ? "Loading roles…" : `${roleCount} role${roleCount === 1 ? "" : "s"} total`}
        actions={
          canManageRoles ? (
            <Button type="button" size="sm" onClick={openCreateDrawer}>
              New role
            </Button>
          ) : null
        }
      >
        <FormField label="Search roles" className="max-w-xs">
          <Input
            value={roleSearch}
            onChange={(event) => setRoleSearch(event.target.value)}
            placeholder="Search by name or slug"
            disabled={rolesQuery.isLoading}
          />
        </FormField>

        {rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading roles…</p>
        ) : filteredRoles.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            {roleSearch ? `No roles match "${roleSearch}".` : "No workspace roles yet. Create one to tailor permissions."}
          </p>
        ) : (
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
                {filteredRoles.map((role) => (
                  <TableRow key={role.id} className="text-sm text-foreground">
                    <TableCell className="px-4 py-3">
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
                            className="border-warning-200 text-[11px] uppercase tracking-wide text-warning-700"
                          >
                            Locked
                          </Badge>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 text-muted-foreground">{role.slug}</TableCell>
                    <TableCell className="px-4 py-3 text-muted-foreground">
                      {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => openRoleDrawer(role.id)}
                        disabled={!canManageRoles}
                      >
                        Manage
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {!canManageRoles ? (
          <Alert tone="info">You do not have permission to manage workspace roles.</Alert>
        ) : null}
      </SettingsPanel>

      <RoleDrawer
        open={isCreateOpen && canManageRoles}
        mode="create"
        permissions={permissions}
        onClose={closeDrawer}
        onSave={(values) => handleCreateRole(values)}
        isSaving={createRole.isPending}
        isDeleting={false}
      />

      <RoleDrawer
        open={Boolean(selectedRoleId) && canManageRoles}
        mode="edit"
        role={selectedRole}
        permissions={permissions}
        onClose={closeDrawer}
        onSave={(values) => (selectedRoleId ? handleUpdateRole(selectedRoleId, values) : Promise.resolve())}
        onDelete={
          selectedRole ? () => handleDeleteRole(selectedRole) : undefined
        }
        isSaving={updateRole.isPending}
        isDeleting={deleteRole.isPending}
      />
    </div>
  );
}

interface RoleDrawerProps {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly role?: RoleDefinition;
  readonly permissions: readonly PermissionDefinition[];
  readonly onClose: () => void;
  readonly onSave: (values: RoleFormValues) => Promise<void>;
  readonly onDelete?: () => Promise<void>;
  readonly isSaving: boolean;
  readonly isDeleting: boolean;
}

function RoleDrawer({
  open,
  mode,
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
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmInput, setConfirmInput] = useState("");

  useEffect(() => {
    if (!open) {
      setFeedback(null);
      setPermissionFilter("");
      setConfirmDelete(false);
      setConfirmInput("");
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
  const canEditRole = mode === "create" || (role?.is_editable ?? false);
  const canDeleteRole = mode === "edit" && role && role.is_editable && !role.is_system && onDelete;

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

  const togglePermission = (permissionKey: string, selected: boolean) => {
    setValues((current) => ({
      ...current,
      permissions: selected
        ? Array.from(new Set([...(current.permissions ?? []), permissionKey]))
        : (current.permissions ?? []).filter((key) => key !== permissionKey),
    }));
  };

  const handleSave = async () => {
    setFeedback(null);
    if (!values.name.trim()) {
      setFeedback("Role name is required.");
      return;
    }
    if (mode === "create" && values.slug && !slugPattern.test(values.slug)) {
      setFeedback("Use lowercase letters, numbers, and dashes for the role slug.");
      return;
    }
    try {
      await onSave({
        ...values,
        name: values.name.trim(),
        slug: mode === "create" ? values.slug.trim() : role?.slug ?? "",
        description: values.description.trim(),
        permissions: values.permissions,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save role.";
      setFeedback(message);
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
      const message = error instanceof Error ? error.message : "Unable to delete role.";
      setFeedback(message);
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
        <Button type="button" onClick={handleSave} disabled={!canEditRole || isSaving}>
          {isSaving ? "Saving..." : mode === "create" ? "Create role" : "Save changes"}
        </Button>
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
        description={mode === "create" ? "Create a workspace-scoped role." : "Edit workspace role details and permissions."}
        footer={footer}
      >
        {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
        {mode === "edit" && role && !role.is_editable ? (
          <Alert tone="warning">This role is locked and cannot be modified.</Alert>
        ) : null}

        <div className="space-y-4">
          <FormField label="Role name" required>
            <Input
              value={values.name}
              onChange={(event) => setValues((current) => ({ ...current, name: event.target.value }))}
              placeholder="Data reviewer"
              disabled={isSaving || !canEditRole}
            />
          </FormField>

          {mode === "create" ? (
            <FormField label="Role slug" hint="Lowercase, URL-friendly identifier. Leave blank to auto-generate.">
              <Input
                value={values.slug}
                onChange={(event) => setValues((current) => ({ ...current, slug: event.target.value }))}
                placeholder="data-reviewer"
                disabled={isSaving || !canEditRole}
              />
            </FormField>
          ) : (
            <FormField label="Role slug">
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
                  Select the permissions included with this role. {values.permissions.length} selected.
                </p>
              </div>
              <Input
                value={permissionFilter}
                onChange={(event) => setPermissionFilter(event.target.value)}
                placeholder="Filter permissions"
                disabled={isSaving}
              />
            </div>

            <div className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
              {filteredPermissions.length === 0 ? (
                <p className="text-xs text-muted-foreground">No permissions match this filter.</p>
              ) : (
                filteredPermissions.map((permission) => {
                  const checkboxId = `permission-${permission.key.replaceAll(".", "-")}`;
                  return (
                    <label
                      key={permission.key}
                      htmlFor={checkboxId}
                      aria-label={permission.label}
                      className="flex items-start gap-3 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                    >
                      <input
                        id={checkboxId}
                        type="checkbox"
                        className="mt-1 h-4 w-4 rounded border-border-strong"
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
                })
              )}
            </div>
          </div>
        </div>
      </SettingsDrawer>

      <ConfirmDialog
        open={confirmDelete && Boolean(role)}
        title="Delete this role?"
        description="Deleting this role will remove it from any members assigned to it."
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
