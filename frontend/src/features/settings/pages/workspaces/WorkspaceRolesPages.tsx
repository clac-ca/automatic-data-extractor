import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { buildWeakEtag } from "@/api/etag";
import { LoadingState } from "@/components/layout";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import type { WorkspaceProfile } from "@/types/workspaces";

import {
  normalizeSettingsError,
  useCreateWorkspaceRoleMutation,
  useDeleteWorkspaceRoleMutation,
  useUpdateWorkspaceRoleMutation,
  useWorkspaceRoleDetailQuery,
  useWorkspaceRolePermissionsQuery,
  useWorkspaceRolesListQuery,
} from "../../data";
import { settingsPaths } from "../../routing/contracts";
import {
  SettingsAccessDenied,
  SettingsCommandBar,
  SettingsDataTable,
  SettingsDetailLayout,
  SettingsDetailSection,
  SettingsEmptyState,
  SettingsErrorState,
  SettingsFeedbackRegion,
  SettingsFormErrorSummary,
  SettingsListLayout,
  SettingsStickyActionBar,
  useSettingsErrorSummary,
  useSettingsListState,
} from "../../shared";

function hasWorkspacePermission(workspace: WorkspaceProfile, permission: string) {
  return workspace.permissions.some((entry) => entry.toLowerCase() === permission.toLowerCase());
}

function sortByLabel<T extends { name?: string; label?: string; key?: string }>(items: readonly T[]) {
  const collator = new Intl.Collator("en", { sensitivity: "base" });
  return [...items].sort((a, b) =>
    collator.compare(a.name || a.label || a.key || "", b.name || b.label || b.key || ""),
  );
}

function workspaceBreadcrumbs(workspace: WorkspaceProfile, section: string) {
  return [
    { label: "Settings", href: settingsPaths.home },
    { label: "Workspaces", href: settingsPaths.workspaces.list },
    { label: workspace.name, href: settingsPaths.workspaces.general(workspace.id) },
    { label: section },
  ] as const;
}

const WORKSPACE_ROLE_CREATE_SECTIONS = [
  { id: "role-details", label: "Role details" },
  { id: "permissions", label: "Permissions" },
] as const;

const WORKSPACE_ROLE_DETAIL_SECTIONS = [
  { id: "role-details", label: "Role details" },
  { id: "permissions", label: "Permissions" },
  { id: "lifecycle", label: "Lifecycle", tone: "danger" as const },
] as const;

export function WorkspaceRolesListPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState({
    defaults: { sort: "name", order: "asc", pageSize: 25 },
  });
  const query = useWorkspaceRolesListQuery(workspace.id);
  const canView =
    hasWorkspacePermission(workspace, "workspace.roles.read") ||
    hasWorkspacePermission(workspace, "workspace.roles.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.roles.manage");

  const filteredRoles = useMemo(() => {
    const term = listState.state.q.trim().toLowerCase();
    const roles = query.data?.items ?? [];
    if (!term) return roles;
    return roles.filter((role) => `${role.name} ${role.slug} ${role.description ?? ""}`.toLowerCase().includes(term));
  }, [listState.state.q, query.data?.items]);

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  return (
    <SettingsListLayout
      title="Roles"
      subtitle="Workspace-specific roles and permission bundles for this workspace."
      breadcrumbs={workspaceBreadcrumbs(workspace, "Roles")}
      actions={
        canManage ? (
          <Button asChild>
            <Link to={listState.withCurrentSearch(settingsPaths.workspaces.rolesCreate(workspace.id))}>
              Create role
            </Link>
          </Button>
        ) : null
      }
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search workspace roles"
        />
      }
    >
      {query.isLoading ? <LoadingState title="Loading roles" className="min-h-[200px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load workspace roles"
          message={normalizeSettingsError(query.error, "Unable to load workspace roles.").message}
        />
      ) : null}
      {query.isSuccess && filteredRoles.length === 0 ? (
        <SettingsEmptyState
          title="No roles found"
          description="Create a role to define workspace-level access profiles."
          action={
            canManage ? (
              <Button asChild size="sm">
                <Link to={listState.withCurrentSearch(settingsPaths.workspaces.rolesCreate(workspace.id))}>Create role</Link>
              </Button>
            ) : null
          }
        />
      ) : null}
      {query.isSuccess && filteredRoles.length > 0 ? (
        <SettingsDataTable
          rows={filteredRoles}
          columns={[
            {
              id: "role",
              header: "Role",
              cell: (role) => (
                <>
                  <p className="font-medium text-foreground">{role.name}</p>
                  <p className="text-xs text-muted-foreground">{role.slug}</p>
                </>
              ),
            },
            {
              id: "permissions",
              header: "Permissions",
              cell: (role) => <p className="text-muted-foreground">{role.permissions.length}</p>,
            },
            {
              id: "type",
              header: "Type",
              cell: (role) => (
                <Badge variant={role.is_system ? "secondary" : "outline"}>
                  {role.is_system ? "System" : "Custom"}
                </Badge>
              ),
            },
          ]}
          getRowId={(role) => role.id}
          onRowOpen={(role) =>
            navigate(listState.withCurrentSearch(settingsPaths.workspaces.roleDetail(workspace.id, role.id)))
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={filteredRoles.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey={`settings-workspace-roles-${workspace.id}`}
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function WorkspaceRoleCreatePage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState();
  const canManage = hasWorkspacePermission(workspace, "workspace.roles.manage");
  const permissionsQuery = useWorkspaceRolePermissionsQuery();
  const createMutation = useCreateWorkspaceRoleMutation(workspace.id);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [permissionSearch, setPermissionSearch] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const errorSummary = useSettingsErrorSummary({
    fieldIdByKey: {
      name: "workspace-role-create-name",
      slug: "workspace-role-create-slug",
      description: "workspace-role-create-description",
    },
    fieldLabelByKey: {
      name: "Name",
      slug: "Slug",
      description: "Description",
    },
  });

  const filteredPermissions = useMemo(() => {
    const allPermissions = permissionsQuery.data?.items ?? [];
    const term = permissionSearch.trim().toLowerCase();
    if (!term) return sortByLabel(allPermissions);
    return sortByLabel(
      allPermissions.filter((permission) =>
        `${permission.label} ${permission.key}`.toLowerCase().includes(term),
      ),
    );
  }, [permissionSearch, permissionsQuery.data?.items]);

  useUnsavedChangesGuard({
    isDirty:
      name.trim().length > 0 ||
      slug.trim().length > 0 ||
      description.trim().length > 0 ||
      selectedPermissions.length > 0,
    message: "You have unsaved workspace role changes.",
    shouldBypassNavigation: () => createMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.roles(workspace.id)} />;
  }

  return (
    <SettingsDetailLayout
      title="Create workspace role"
      subtitle="Create a custom role scoped to this workspace."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Roles"),
        { label: "Create" },
      ]}
      actions={
        <Button
          variant="outline"
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.roles(workspace.id)))}
        >
          Cancel
        </Button>
      }
      sections={WORKSPACE_ROLE_CREATE_SECTIONS}
      defaultSectionId="role-details"
    >
      <SettingsFormErrorSummary summary={errorSummary.summary} />
      <SettingsFeedbackRegion
        messages={errorMessage ? [{ tone: "danger", message: errorMessage }] : []}
      />

      <SettingsDetailSection id="role-details" title="Role details">
        <FormField label="Name" required error={errorSummary.getFieldError("name")}>
          <Input
            id="workspace-role-create-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Data Steward"
          />
        </FormField>
        <FormField label="Slug" hint="Optional URL-friendly identifier." error={errorSummary.getFieldError("slug")}>
          <Input
            id="workspace-role-create-slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="data-steward"
          />
        </FormField>
        <FormField label="Description" error={errorSummary.getFieldError("description")}>
          <Input
            id="workspace-role-create-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Manages review queues and corrections."
          />
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="permissions" title="Permissions">
        <Input value={permissionSearch} onChange={(event) => setPermissionSearch(event.target.value)} placeholder="Filter permissions" />
        {permissionsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading permissions...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {filteredPermissions.map((permission) => {
              const checked = selectedPermissions.includes(permission.key);
              const checkboxId = `workspace-role-create-perm-${permission.key}`;
              return (
                <div key={permission.key} className="flex items-start gap-2 text-sm">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => {
                      const nextChecked = event.target.checked;
                      setSelectedPermissions((current) => {
                        if (nextChecked) {
                          return current.includes(permission.key)
                            ? current
                            : [...current, permission.key];
                        }
                        return current.filter((value) => value !== permission.key);
                      });
                    }}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{permission.label}</span>
                    <span className="block text-xs text-muted-foreground">{permission.key}</span>
                  </label>
                </div>
              );
            })}
          </div>
        )}
      </SettingsDetailSection>

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.roles(workspace.id)))}
        >
          Cancel
        </Button>
        <Button
          disabled={createMutation.isPending}
          onClick={async () => {
            setErrorMessage(null);
            errorSummary.clearErrors();
            if (!name.trim()) {
              errorSummary.setClientErrors({ name: "Role name is required." });
              setErrorMessage("Please review the highlighted fields.");
              return;
            }
            try {
              const created = await createMutation.mutateAsync({
                name: name.trim(),
                slug: slug.trim() || null,
                description: description.trim() || null,
                permissions: selectedPermissions,
              });
              navigate(
                listState.withCurrentSearch(settingsPaths.workspaces.roleDetail(workspace.id, created.id)),
                { replace: true },
              );
            } catch (error) {
              const normalized = normalizeSettingsError(error, "Unable to create workspace role.");
              setErrorMessage(normalized.message);
              errorSummary.setProblemErrors(normalized.fieldErrors);
            }
          }}
        >
          {createMutation.isPending ? "Creating..." : "Create role"}
        </Button>
      </div>
    </SettingsDetailLayout>
  );
}

export function WorkspaceRoleDetailPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  const listState = useSettingsListState();

  const canView =
    hasWorkspacePermission(workspace, "workspace.roles.read") ||
    hasWorkspacePermission(workspace, "workspace.roles.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.roles.manage");

  const roleQuery = useWorkspaceRoleDetailQuery(workspace.id, roleId ?? null);
  const permissionsQuery = useWorkspaceRolePermissionsQuery();
  const updateMutation = useUpdateWorkspaceRoleMutation(workspace.id);
  const deleteMutation = useDeleteWorkspaceRoleMutation(workspace.id);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [permissionSearch, setPermissionSearch] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (!roleQuery.data) {
      return;
    }
    setName(roleQuery.data.name);
    setDescription(roleQuery.data.description || "");
    setSelectedPermissions(roleQuery.data.permissions);
  }, [roleQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!roleQuery.data) return false;
    if (roleQuery.data.name !== name) return true;
    if ((roleQuery.data.description || "") !== description) return true;
    if (roleQuery.data.permissions.length !== selectedPermissions.length) return true;
    return roleQuery.data.permissions.some((permission) => !selectedPermissions.includes(permission));
  }, [description, name, roleQuery.data, selectedPermissions]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved workspace role changes.",
    shouldBypassNavigation: () => updateMutation.isPending,
  });

  const filteredPermissions = useMemo(() => {
    const allPermissions = permissionsQuery.data?.items ?? [];
    const term = permissionSearch.trim().toLowerCase();
    if (!term) return sortByLabel(allPermissions);
    return sortByLabel(
      allPermissions.filter((permission) =>
        `${permission.label} ${permission.key}`.toLowerCase().includes(term),
      ),
    );
  }, [permissionSearch, permissionsQuery.data?.items]);

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  if (roleQuery.isLoading) {
    return <LoadingState title="Loading workspace role" className="min-h-[300px]" />;
  }

  if (roleQuery.isError || !roleQuery.data) {
    return (
      <SettingsErrorState
        title="Workspace role unavailable"
        message={normalizeSettingsError(roleQuery.error, "Unable to load workspace role.").message}
      />
    );
  }

  const role = roleQuery.data;
  const canEdit = canManage && role.is_editable;
  const canDelete = canEdit && !role.is_system;

  const saveChanges = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateMutation.mutateAsync({
        roleId: role.id,
        payload: {
          name: name.trim() || null,
          description: description.trim() || null,
          permissions: selectedPermissions,
        },
        ifMatch: buildWeakEtag(role.id, role.updated_at ?? role.created_at),
      });
      setSuccessMessage("Workspace role updated.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to update workspace role.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title={role.name}
      subtitle="Update this workspace role and its permission set."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Roles"),
        { label: role.slug },
      ]}
      actions={
        <div className="flex items-center gap-2">
          {role.is_system ? <Badge variant="secondary">System</Badge> : null}
          {!role.is_editable ? <Badge variant="outline">Locked</Badge> : null}
        </div>
      }
      sections={WORKSPACE_ROLE_DETAIL_SECTIONS}
      defaultSectionId="role-details"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      {!canEdit ? <Alert tone="info">This role is read-only.</Alert> : null}

      <SettingsDetailSection id="role-details" title="Role details">
        <FormField label="Name" required>
          <Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canEdit || updateMutation.isPending} />
        </FormField>
        <FormField label="Slug">
          <Input value={role.slug} disabled />
        </FormField>
        <FormField label="Description">
          <Input value={description} onChange={(event) => setDescription(event.target.value)} disabled={!canEdit || updateMutation.isPending} />
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="permissions" title="Permissions">
        <Input value={permissionSearch} onChange={(event) => setPermissionSearch(event.target.value)} placeholder="Filter permissions" disabled={!canEdit} />
        {permissionsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading permissions...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {filteredPermissions.map((permission) => {
              const checked = selectedPermissions.includes(permission.key);
              const checkboxId = `workspace-role-detail-perm-${permission.key}`;
              return (
                <div key={permission.key} className="flex items-start gap-2 text-sm">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    checked={checked}
                    disabled={!canEdit || updateMutation.isPending}
                    onChange={(event) => {
                      const nextChecked = event.target.checked;
                      setSelectedPermissions((current) => {
                        if (nextChecked) {
                          return current.includes(permission.key)
                            ? current
                            : [...current, permission.key];
                        }
                        return current.filter((value) => value !== permission.key);
                      });
                    }}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{permission.label}</span>
                    <span className="block text-xs text-muted-foreground">{permission.key}</span>
                  </label>
                </div>
              );
            })}
          </div>
        )}
      </SettingsDetailSection>

      <SettingsDetailSection id="lifecycle" title="Lifecycle" tone="danger">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Delete this custom workspace role when no longer needed.</p>
          <Button variant="destructive" disabled={!canDelete || deleteMutation.isPending} onClick={() => setConfirmDeleteOpen(true)}>
            {deleteMutation.isPending ? "Deleting..." : "Delete role"}
          </Button>
        </div>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canEdit}
        disabledReason={canEdit ? undefined : "This role is locked and cannot be edited."}
        isSaving={updateMutation.isPending}
        onSave={() => {
          void saveChanges();
        }}
        onDiscard={() => {
          setName(role.name);
          setDescription(role.description || "");
          setSelectedPermissions(role.permissions);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Workspace role changes are pending"
      />

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete workspace role?"
        description={`Delete ${role.name}. Existing role assignments will be removed.`}
        confirmLabel="Delete role"
        tone="danger"
        onCancel={() => setConfirmDeleteOpen(false)}
        onConfirm={async () => {
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await deleteMutation.mutateAsync({
              roleId: role.id,
              ifMatch: buildWeakEtag(role.id, role.updated_at ?? role.created_at),
            });
            navigate(listState.withCurrentSearch(settingsPaths.workspaces.roles(workspace.id)), {
              replace: true,
            });
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to delete workspace role.").message);
          }
        }}
        isConfirming={deleteMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
