import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { LoadingState } from "@/components/layout";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import type { WorkspacePrincipalType, WorkspaceProfile } from "@/types/workspaces";

import {
  normalizeSettingsError,
  useCreateWorkspacePrincipalMutation,
  useGroupsLookupQuery,
  useRemoveWorkspacePrincipalMutation,
  useUpdateWorkspacePrincipalMutation,
  useUsersLookupQuery,
  useWorkspacePrincipalDetailQuery,
  useWorkspacePrincipalsListQuery,
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
  SettingsListLayout,
  SettingsStickyActionBar,
  useSettingsListState,
} from "../../shared";

function hasWorkspacePermission(workspace: WorkspaceProfile, permission: string) {
  return workspace.permissions.some((entry) => entry.toLowerCase() === permission.toLowerCase());
}

function workspaceBreadcrumbs(workspace: WorkspaceProfile, section: string) {
  return [
    { label: "Settings", href: settingsPaths.home },
    { label: "Workspaces", href: settingsPaths.workspaces.list },
    { label: workspace.name, href: settingsPaths.workspaces.general(workspace.id) },
    { label: section },
  ] as const;
}

function principalLabel(principal: {
  principal_display_name?: string | null;
  principal_email?: string | null;
  principal_slug?: string | null;
  principal_id: string;
}) {
  return (
    principal.principal_display_name ||
    principal.principal_email ||
    principal.principal_slug ||
    principal.principal_id
  );
}

const WORKSPACE_PRINCIPAL_CREATE_SECTIONS = [
  { id: "principal", label: "Principal" },
  { id: "role-assignments", label: "Role assignments" },
] as const;

const WORKSPACE_PRINCIPAL_DETAIL_SECTIONS = [
  { id: "principal-identity", label: "Principal identity" },
  { id: "role-assignments", label: "Role assignments" },
  { id: "lifecycle", label: "Lifecycle", tone: "danger" as const },
] as const;

export function WorkspacePrincipalsListPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState({
    defaults: { sort: "principal", order: "asc", pageSize: 25 },
    filterKeys: ["principalType"],
  });
  const principalTypeFilter = (listState.state.filters.principalType as "all" | WorkspacePrincipalType | undefined) ?? "all";

  const query = useWorkspacePrincipalsListQuery(workspace.id);
  const canView =
    hasWorkspacePermission(workspace, "workspace.members.read") ||
    hasWorkspacePermission(workspace, "workspace.members.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.members.manage");

  const filteredPrincipals = useMemo(() => {
    const principals = query.data?.items ?? [];
    const term = listState.state.q.trim().toLowerCase();
    return principals.filter((principal) => {
      if (principalTypeFilter !== "all" && principal.principal_type !== principalTypeFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      return `${principalLabel(principal)} ${principal.principal_id}`.toLowerCase().includes(term);
    });
  }, [listState.state.q, principalTypeFilter, query.data?.items]);

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  return (
    <SettingsListLayout
      title="Principals"
      subtitle="Manage direct user and group access assignments in this workspace."
      breadcrumbs={workspaceBreadcrumbs(workspace, "Principals")}
      actions={
        canManage ? (
          <Button asChild>
            <Link to={listState.withCurrentSearch(settingsPaths.workspaces.principalsCreate(workspace.id))}>
              Add principal
            </Link>
          </Button>
        ) : null
      }
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search principals"
          controls={
            <Select
              value={principalTypeFilter}
              onValueChange={(value) =>
                listState.setFilter("principalType", value === "all" ? null : value)
              }
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="user">Users</SelectItem>
                <SelectItem value="group">Groups</SelectItem>
              </SelectContent>
            </Select>
          }
        />
      }
    >
      {query.isLoading ? <LoadingState title="Loading principals" className="min-h-[220px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load principals"
          message={normalizeSettingsError(query.error, "Unable to load workspace principals.").message}
        />
      ) : null}
      {query.isSuccess && filteredPrincipals.length === 0 ? (
        <SettingsEmptyState
          title="No principals"
          description="Add a user or group to grant direct workspace access."
          action={
            canManage ? (
              <Button asChild size="sm">
                <Link to={listState.withCurrentSearch(settingsPaths.workspaces.principalsCreate(workspace.id))}>Add principal</Link>
              </Button>
            ) : null
          }
        />
      ) : null}
      {query.isSuccess && filteredPrincipals.length > 0 ? (
        <SettingsDataTable
          rows={filteredPrincipals}
          columns={[
            {
              id: "principal",
              header: "Principal",
              cell: (principal) => (
                <>
                  <p className="font-medium text-foreground">{principalLabel(principal)}</p>
                  <p className="text-xs text-muted-foreground">{principal.principal_id}</p>
                </>
              ),
            },
            {
              id: "type",
              header: "Type",
              cell: (principal) => (
                <Badge variant="outline" className="capitalize">
                  {principal.principal_type}
                </Badge>
              ),
            },
            {
              id: "roles",
              header: "Roles",
              cell: (principal) => (
                <p className="text-muted-foreground">{principal.role_slugs.join(", ") || "No roles"}</p>
              ),
            },
          ]}
          getRowId={(principal) => `${principal.principal_type}:${principal.principal_id}`}
          onRowOpen={(principal) =>
            navigate(
              listState.withCurrentSearch(
                settingsPaths.workspaces.principalDetail(
                  workspace.id,
                  principal.principal_type,
                  principal.principal_id,
                ),
              ),
            )
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={filteredPrincipals.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey={`settings-workspace-principals-${workspace.id}`}
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function WorkspacePrincipalCreatePage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState();
  const canManage = hasWorkspacePermission(workspace, "workspace.members.manage");

  const rolesQuery = useWorkspaceRolesListQuery(workspace.id);
  const createMutation = useCreateWorkspacePrincipalMutation(workspace.id);

  const [principalType, setPrincipalType] = useState<WorkspacePrincipalType>("user");
  const [search, setSearch] = useState("");
  const [selectedPrincipalId, setSelectedPrincipalId] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const usersQuery = useUsersLookupQuery(search, principalType === "user");
  const groupsQuery = useGroupsLookupQuery(search, principalType === "group");

  const candidateOptions = principalType === "user" ? usersQuery.data?.items ?? [] : groupsQuery.data?.items ?? [];

  useUnsavedChangesGuard({
    isDirty: selectedPrincipalId.length > 0 || selectedRoleIds.length > 0 || search.trim().length > 0,
    message: "You have unsaved principal changes.",
    shouldBypassNavigation: () => createMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.principals(workspace.id)} />;
  }

  return (
    <SettingsDetailLayout
      title="Add principal"
      subtitle="Grant a user or group direct workspace access and role assignments."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Principals"),
        { label: "Create" },
      ]}
      actions={
        <Button
          variant="outline"
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.principals(workspace.id)))}
        >
          Cancel
        </Button>
      }
      sections={WORKSPACE_PRINCIPAL_CREATE_SECTIONS}
      defaultSectionId="principal"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}

      <SettingsDetailSection id="principal" title="Principal">
        <FormField label="Principal type" required>
          <Select
            value={principalType}
            onValueChange={(value) => {
              setPrincipalType(value as WorkspacePrincipalType);
              setSelectedPrincipalId("");
              setSearch("");
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="user">User</SelectItem>
              <SelectItem value="group">Group</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField label={principalType === "user" ? "Find user" : "Find group"}>
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={principalType === "user" ? "Search users" : "Search groups"}
          />
        </FormField>

        <FormField label={principalType === "user" ? "User" : "Group"} required>
          <Select value={selectedPrincipalId} onValueChange={setSelectedPrincipalId}>
            <SelectTrigger>
              <SelectValue placeholder={principalType === "user" ? "Select user" : "Select group"} />
            </SelectTrigger>
            <SelectContent>
              {candidateOptions.map((candidate) => (
                <SelectItem key={candidate.id} value={candidate.id}>
                  {"email" in candidate ? candidate.display_name || candidate.email : candidate.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="role-assignments" title="Role assignments">
        {rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading workspace roles...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {(rolesQuery.data?.items ?? []).map((role) => {
              const checked = selectedRoleIds.includes(role.id);
              const checkboxId = `workspace-principal-create-role-${role.id}`;
              return (
                <div key={role.id} className="flex items-start gap-2 text-sm">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => {
                      const nextChecked = event.target.checked;
                      setSelectedRoleIds((current) => {
                        if (nextChecked) {
                          return current.includes(role.id) ? current : [...current, role.id];
                        }
                        return current.filter((value) => value !== role.id);
                      });
                    }}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{role.name}</span>
                    <span className="block text-xs text-muted-foreground">{role.description || role.slug}</span>
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
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.principals(workspace.id)))}
        >
          Cancel
        </Button>
        <Button
          disabled={createMutation.isPending}
          onClick={async () => {
            setErrorMessage(null);
            if (!selectedPrincipalId) {
              setErrorMessage("Select a principal.");
              return;
            }
            if (selectedRoleIds.length === 0) {
              setErrorMessage("Select at least one role.");
              return;
            }
            try {
              const created = await createMutation.mutateAsync({
                principalType,
                principalId: selectedPrincipalId,
                roleIds: selectedRoleIds,
              });
              navigate(
                listState.withCurrentSearch(
                  settingsPaths.workspaces.principalDetail(
                    workspace.id,
                    created.principal_type,
                    created.principal_id,
                  ),
                ),
                { replace: true },
              );
            } catch (error) {
              setErrorMessage(normalizeSettingsError(error, "Unable to add principal.").message);
            }
          }}
        >
          {createMutation.isPending ? "Adding..." : "Add principal"}
        </Button>
      </div>
    </SettingsDetailLayout>
  );
}

export function WorkspacePrincipalDetailPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const { principalType, principalId } = useParams<{ principalType: WorkspacePrincipalType; principalId: string }>();
  const navigate = useNavigate();
  const listState = useSettingsListState();

  const canView =
    hasWorkspacePermission(workspace, "workspace.members.read") ||
    hasWorkspacePermission(workspace, "workspace.members.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.members.manage");

  const principalQuery = useWorkspacePrincipalDetailQuery(workspace.id, (principalType as WorkspacePrincipalType | undefined) ?? null, principalId ?? null);
  const rolesQuery = useWorkspaceRolesListQuery(workspace.id);
  const updateMutation = useUpdateWorkspacePrincipalMutation(workspace.id);
  const removeMutation = useRemoveWorkspacePrincipalMutation(workspace.id);

  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);

  useEffect(() => {
    if (!principalQuery.data) {
      return;
    }
    setSelectedRoleIds(principalQuery.data.role_ids);
  }, [principalQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!principalQuery.data) return false;
    if (principalQuery.data.role_ids.length !== selectedRoleIds.length) return true;
    return principalQuery.data.role_ids.some((roleId: string) => !selectedRoleIds.includes(roleId));
  }, [principalQuery.data, selectedRoleIds]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved principal role changes.",
    shouldBypassNavigation: () => updateMutation.isPending,
  });

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.principals(workspace.id)} />;
  }

  if (principalQuery.isLoading) {
    return <LoadingState title="Loading principal" className="min-h-[300px]" />;
  }

  if (principalQuery.isError || !principalQuery.data) {
    return (
      <SettingsErrorState
        title="Principal unavailable"
        message={normalizeSettingsError(principalQuery.error, "Unable to load principal details.").message}
      />
    );
  }

  const principal = principalQuery.data;

  const saveChanges = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateMutation.mutateAsync({
        principalType: principal.principal_type,
        principalId: principal.principal_id,
        roleIds: selectedRoleIds,
      });
      setSuccessMessage("Principal roles updated.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to update principal roles.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title={principalLabel(principal)}
      subtitle="Manage role assignments for this principal."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Principals"),
        { label: principal.principal_id },
      ]}
      actions={<Badge variant="outline" className="capitalize">{principal.principal_type}</Badge>}
      sections={WORKSPACE_PRINCIPAL_DETAIL_SECTIONS}
      defaultSectionId="principal-identity"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="principal-identity" title="Principal identity">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Display</p>
            <p className="text-sm text-foreground">{principalLabel(principal)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Principal ID</p>
            <p className="text-sm text-foreground">{principal.principal_id}</p>
          </div>
        </div>
      </SettingsDetailSection>

      <SettingsDetailSection id="role-assignments" title="Role assignments">
        {rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading workspace roles...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {(rolesQuery.data?.items ?? []).map((role) => {
              const checked = selectedRoleIds.includes(role.id);
              const checkboxId = `workspace-principal-detail-role-${role.id}`;
              return (
                <div key={role.id} className="flex items-start gap-2 text-sm">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    checked={checked}
                    disabled={!canManage || updateMutation.isPending}
                    onChange={(event) => {
                      const nextChecked = event.target.checked;
                      setSelectedRoleIds((current) => {
                        if (nextChecked) {
                          return current.includes(role.id) ? current : [...current, role.id];
                        }
                        return current.filter((value) => value !== role.id);
                      });
                    }}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{role.name}</span>
                    <span className="block text-xs text-muted-foreground">{role.description || role.slug}</span>
                  </label>
                </div>
              );
            })}
          </div>
        )}
      </SettingsDetailSection>

      <SettingsDetailSection id="lifecycle" title="Lifecycle" tone="danger">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Removing a principal revokes all direct access assignments.</p>
          <Button variant="destructive" disabled={!canManage || removeMutation.isPending} onClick={() => setConfirmRemoveOpen(true)}>
            {removeMutation.isPending ? "Removing..." : "Remove principal"}
          </Button>
        </div>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canManage}
        disabledReason={canManage ? undefined : "You do not have permission to update principal roles."}
        isSaving={updateMutation.isPending}
        onSave={() => {
          void saveChanges();
        }}
        onDiscard={() => {
          setSelectedRoleIds(principal.role_ids);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Principal changes are pending"
      />

      <ConfirmDialog
        open={confirmRemoveOpen}
        title="Remove principal?"
        description="This principal will lose direct access to the workspace."
        confirmLabel="Remove principal"
        tone="danger"
        onCancel={() => setConfirmRemoveOpen(false)}
        onConfirm={async () => {
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await removeMutation.mutateAsync({
              principalType: principal.principal_type,
              principalId: principal.principal_id,
            });
            navigate(listState.withCurrentSearch(settingsPaths.workspaces.principals(workspace.id)), {
              replace: true,
            });
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to remove principal.").message);
          }
        }}
        isConfirming={removeMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
