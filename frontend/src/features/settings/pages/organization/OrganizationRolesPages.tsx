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
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";

import {
  normalizeSettingsError,
  useCreateOrganizationRoleMutation,
  useDeleteOrganizationRoleMutation,
  useOrganizationPermissionsQuery,
  useOrganizationRoleDetailQuery,
  useOrganizationRolesListQuery,
  useUpdateOrganizationRoleMutation,
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

function canViewRoles(permissions: ReadonlySet<string>) {
  return permissions.has("roles.read_all") || permissions.has("roles.manage_all");
}

function canManageRoles(permissions: ReadonlySet<string>) {
  return permissions.has("roles.manage_all");
}

function sortByLabel<T extends { name?: string; label?: string; key?: string }>(items: readonly T[]) {
  const collator = new Intl.Collator("en", { sensitivity: "base" });
  return [...items].sort((a, b) =>
    collator.compare(a.name || a.label || a.key || "", b.name || b.label || b.key || ""),
  );
}

const ORGANIZATION_ROLE_CREATE_SECTIONS = [
  { id: "role-details", label: "Role details" },
  { id: "permissions", label: "Permissions" },
] as const;

const ORGANIZATION_ROLE_DETAIL_SECTIONS = [
  { id: "role-details", label: "Role details" },
  { id: "permissions", label: "Permissions" },
  { id: "lifecycle", label: "Lifecycle", tone: "danger" as const },
] as const;

export function OrganizationRolesListPage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState({
    defaults: { sort: "name", order: "asc", pageSize: 25 },
  });
  const query = useOrganizationRolesListQuery();

  const filteredRoles = useMemo(() => {
    const term = listState.state.q.trim().toLowerCase();
    const roles = query.data?.items ?? [];
    if (!term) return roles;
    return roles.filter((role) => `${role.name} ${role.slug} ${role.description ?? ""}`.toLowerCase().includes(term));
  }, [listState.state.q, query.data?.items]);

  if (!canViewRoles(permissions)) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  return (
    <SettingsListLayout
      title="Roles"
      subtitle="Define and maintain global role definitions for organization-wide access."
      breadcrumbs={[{ label: "Settings", href: settingsPaths.home }, { label: "Organization" }, { label: "Roles" }]}
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search roles"
          primaryAction={
            canManageRoles(permissions) ? (
              <Button asChild>
                <Link to={listState.withCurrentSearch(settingsPaths.organization.rolesCreate)}>Create role</Link>
              </Button>
            ) : null
          }
        />
      }
    >
      {query.isLoading ? <LoadingState title="Loading roles" className="min-h-[200px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load roles"
          message={normalizeSettingsError(query.error, "Unable to load roles.").message}
        />
      ) : null}
      {query.isSuccess && filteredRoles.length === 0 ? (
        <SettingsEmptyState
          title="No roles found"
          description="Create a role to define reusable permission bundles."
          action={
            canManageRoles(permissions) ? (
              <Button asChild size="sm">
                <Link to={settingsPaths.organization.rolesCreate}>Create role</Link>
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
              cell: (role) => <p className="text-sm text-muted-foreground">{role.permissions.length}</p>,
            },
            {
              id: "system",
              header: "System",
              cell: (role) => (
                <Badge variant={role.is_system ? "secondary" : "outline"}>
                  {role.is_system ? "System" : "Custom"}
                </Badge>
              ),
            },
          ]}
          getRowId={(role) => role.id}
          onRowOpen={(role) =>
            navigate(listState.withCurrentSearch(settingsPaths.organization.roleDetail(role.id)))
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={filteredRoles.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey="settings-organization-roles-list-row"
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function OrganizationRoleCreatePage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const canManage = canManageRoles(permissions);
  const listState = useSettingsListState();

  const permissionsQuery = useOrganizationPermissionsQuery("global");
  const createMutation = useCreateOrganizationRoleMutation();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [permissionSearch, setPermissionSearch] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const errorSummary = useSettingsErrorSummary({
    fieldIdByKey: {
      name: "create-role-name",
      slug: "create-role-slug",
      description: "create-role-description",
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
    message: "You have unsaved role changes.",
    shouldBypassNavigation: () => createMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.organization.roles} />;
  }

  return (
    <SettingsDetailLayout
      title="Create role"
      subtitle="Create a custom global role and choose allowed permissions."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Roles", href: listState.withCurrentSearch(settingsPaths.organization.roles) },
        { label: "Create" },
      ]}
      actions={
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.roles))}>
          Cancel
        </Button>
      }
      sections={ORGANIZATION_ROLE_CREATE_SECTIONS}
      defaultSectionId="role-details"
    >
      <SettingsFormErrorSummary summary={errorSummary.summary} />
      <SettingsFeedbackRegion
        messages={errorMessage ? [{ tone: "danger", message: errorMessage }] : []}
      />

      <SettingsDetailSection id="role-details" title="Role details">
        <FormField label="Name" required error={errorSummary.getFieldError("name")}>
          <Input
            id="create-role-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Security Auditor"
          />
        </FormField>
        <FormField label="Slug" hint="Optional URL-friendly identifier." error={errorSummary.getFieldError("slug")}>
          <Input
            id="create-role-slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="security-auditor"
          />
        </FormField>
        <FormField label="Description" error={errorSummary.getFieldError("description")}>
          <Input
            id="create-role-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Read-only access for compliance."
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
              const checkboxId = `org-role-create-perm-${permission.key}`;
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
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.roles))}>
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
              navigate(listState.withCurrentSearch(settingsPaths.organization.roleDetail(created.id)), { replace: true });
            } catch (error) {
              const normalized = normalizeSettingsError(error, "Unable to create role.");
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

export function OrganizationRoleDetailPage() {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState();

  const canView = canViewRoles(permissions);
  const canManage = canManageRoles(permissions);

  const roleQuery = useOrganizationRoleDetailQuery(roleId ?? null);
  const permissionsQuery = useOrganizationPermissionsQuery("global");
  const updateMutation = useUpdateOrganizationRoleMutation();
  const deleteMutation = useDeleteOrganizationRoleMutation();

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
    message: "You have unsaved role changes.",
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
    return <SettingsAccessDenied returnHref={settingsPaths.organization.roles} />;
  }

  if (roleQuery.isLoading) {
    return <LoadingState title="Loading role" className="min-h-[300px]" />;
  }

  if (roleQuery.isError || !roleQuery.data) {
    return (
      <SettingsErrorState
        title="Role unavailable"
        message={normalizeSettingsError(roleQuery.error, "Unable to load role details.").message}
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
      setSuccessMessage("Role updated.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to update role.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title={role.name}
      subtitle="Update role metadata and permission assignments."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Roles", href: listState.withCurrentSearch(settingsPaths.organization.roles) },
        { label: role.slug },
      ]}
      actions={
        <div className="flex items-center gap-2">
          {role.is_system ? <Badge variant="secondary">System</Badge> : null}
          {!role.is_editable ? <Badge variant="outline">Locked</Badge> : null}
        </div>
      }
      sections={ORGANIZATION_ROLE_DETAIL_SECTIONS}
      defaultSectionId="role-details"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      {!canEdit ? (
        <Alert tone="info">This role is read-only for your account or system policy.</Alert>
      ) : null}

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
        <Input
          value={permissionSearch}
          onChange={(event) => setPermissionSearch(event.target.value)}
          placeholder="Filter permissions"
          disabled={!canEdit}
        />
        {permissionsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading permissions...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {filteredPermissions.map((permission) => {
              const checked = selectedPermissions.includes(permission.key);
              const checkboxId = `org-role-detail-perm-${permission.key}`;
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
          <p className="text-sm text-muted-foreground">Delete this custom role if it is no longer needed.</p>
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
        message="Role changes are pending"
      />

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete role?"
        description={`Delete ${role.name}. Existing assignments will lose this role.`}
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
            navigate(listState.withCurrentSearch(settingsPaths.organization.roles), { replace: true });
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to delete role.").message);
          }
        }}
        isConfirming={deleteMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
