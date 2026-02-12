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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";

import {
  normalizeSettingsError,
  useAddOrganizationUserMemberOfMutation,
  useAssignOrganizationUserRoleMutation,
  useCreateOrganizationUserApiKeyMutation,
  useCreateOrganizationUserMutation,
  useDeactivateOrganizationUserMutation,
  useOrganizationGroupsListQuery,
  useOrganizationRolesListQuery,
  useOrganizationUserApiKeysQuery,
  useOrganizationUserDetailQuery,
  useOrganizationUserMemberOfQuery,
  useOrganizationUserRolesQuery,
  useOrganizationUsersListQuery,
  useRemoveOrganizationUserMemberOfMutation,
  useRemoveOrganizationUserRoleMutation,
  useRevokeOrganizationUserApiKeyMutation,
  useUpdateOrganizationUserMutation,
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

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function hasUserSettingsAccess(permissions: ReadonlySet<string>) {
  return permissions.has("users.read_all") || permissions.has("users.manage_all");
}

function canManageUsers(permissions: ReadonlySet<string>) {
  return permissions.has("users.manage_all");
}

const USER_CREATE_SECTIONS = [
  { id: "identity", label: "Identity" },
  { id: "password-provisioning", label: "Password provisioning" },
  { id: "organization-roles", label: "Organization roles" },
] as const;

const USER_DETAIL_SECTIONS = [
  { id: "profile", label: "Profile" },
  { id: "organization-roles", label: "Organization roles" },
  { id: "group-memberships", label: "Group memberships" },
  { id: "user-api-keys", label: "User API keys" },
  { id: "lifecycle", label: "Lifecycle", tone: "danger" as const },
] as const;

export function OrganizationUsersListPage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState({
    defaults: { sort: "created", order: "desc", pageSize: 25 },
  });

  const query = useOrganizationUsersListQuery(listState.state.q);

  if (!hasUserSettingsAccess(permissions)) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  return (
    <SettingsListLayout
      title="Users"
      subtitle="Manage organization identities, role assignments, group memberships, and API keys."
      breadcrumbs={[{ label: "Settings", href: settingsPaths.home }, { label: "Organization" }, { label: "Users" }]}
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search users by name or email"
          primaryAction={
            canManageUsers(permissions) ? (
              <Button asChild>
                <Link to={listState.withCurrentSearch(settingsPaths.organization.usersCreate)}>Create user</Link>
              </Button>
            ) : null
          }
        />
      }
    >
      {query.isLoading ? <LoadingState title="Loading users" className="min-h-[200px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load users"
          message={normalizeSettingsError(query.error, "Unable to load users.").message}
        />
      ) : null}
      {query.isSuccess && query.data.items.length === 0 ? (
        <SettingsEmptyState
          title="No users found"
          description="Create a user to start assigning organization and workspace access."
          action={
            canManageUsers(permissions) ? (
              <Button asChild size="sm">
                <Link to={settingsPaths.organization.usersCreate}>Create user</Link>
              </Button>
            ) : null
          }
        />
      ) : null}
      {query.isSuccess && query.data.items.length > 0 ? (
        <SettingsDataTable
          rows={query.data.items}
          columns={[
            {
              id: "user",
              header: "User",
              cell: (user) => (
                <>
                  <p className="font-medium text-foreground">{user.display_name || user.email}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </>
              ),
            },
            {
              id: "status",
              header: "Status",
              cell: (user) => (
                <Badge variant={user.is_active ? "secondary" : "outline"}>
                  {user.is_active ? "Active" : "Inactive"}
                </Badge>
              ),
            },
            {
              id: "created",
              header: "Created",
              cell: (user) => <p className="text-sm text-muted-foreground">{formatDateTime(user.created_at)}</p>,
            },
          ]}
          getRowId={(user) => user.id}
          onRowOpen={(user) =>
            navigate(listState.withCurrentSearch(settingsPaths.organization.userDetail(user.id)))
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={query.data.items.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey="settings-organization-users-list-row"
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function OrganizationUserCreatePage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const canManage = canManageUsers(permissions);
  const listState = useSettingsListState();

  const rolesQuery = useOrganizationRolesListQuery();
  const createUserMutation = useCreateOrganizationUserMutation();
  const assignRoleMutation = useAssignOrganizationUserRoleMutation();

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [passwordMode, setPasswordMode] = useState<"auto_generate" | "explicit">("auto_generate");
  const [password, setPassword] = useState("");
  const [forcePasswordReset, setForcePasswordReset] = useState(true);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [provisionedPassword, setProvisionedPassword] = useState<string | null>(null);
  const errorSummary = useSettingsErrorSummary({
    fieldIdByKey: {
      email: "create-user-email",
      password: "create-user-password",
      display_name: "create-user-display-name",
    },
    fieldLabelByKey: {
      email: "Email",
      password: "Password",
      display_name: "Display name",
    },
  });

  const hasUnsavedChanges = useMemo(
    () =>
      email.trim().length > 0 ||
      displayName.trim().length > 0 ||
      password.trim().length > 0 ||
      selectedRoleIds.length > 0 ||
      passwordMode !== "auto_generate" ||
      forcePasswordReset !== true,
    [displayName, email, forcePasswordReset, password, passwordMode, selectedRoleIds.length],
  );

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved changes for the new user.",
    shouldBypassNavigation: () => createUserMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.organization.users} />;
  }

  const handleCreate = async () => {
    setErrorMessage(null);
    setProvisionedPassword(null);
    errorSummary.clearErrors();

    const clientErrors: Record<string, string> = {};
    if (!email.trim()) {
      clientErrors.email = "Email is required.";
    }

    if (passwordMode === "explicit" && !password.trim()) {
      clientErrors.password = "Password is required when explicit mode is selected.";
    }

    if (Object.keys(clientErrors).length > 0) {
      errorSummary.setClientErrors(clientErrors);
      setErrorMessage("Please review the highlighted fields.");
      return;
    }

    try {
      const created = await createUserMutation.mutateAsync({
        email: email.trim().toLowerCase(),
        displayName: displayName.trim() || null,
        passwordProfile: {
          mode: passwordMode,
          password: passwordMode === "explicit" ? password : null,
          forceChangeOnNextSignIn: forcePasswordReset,
        },
      });

      await Promise.all(
        selectedRoleIds.map((roleId) =>
          assignRoleMutation.mutateAsync({ userId: created.user.id, roleId }),
        ),
      );

      if (created.passwordProvisioning.initialPassword) {
        setProvisionedPassword(created.passwordProvisioning.initialPassword);
      }

      navigate(listState.withCurrentSearch(settingsPaths.organization.userDetail(created.user.id)), { replace: true });
    } catch (error) {
      const normalized = normalizeSettingsError(error, "Unable to create user.");
      setErrorMessage(normalized.message);
      errorSummary.setProblemErrors(normalized.fieldErrors);
    }
  };

  return (
    <SettingsDetailLayout
      title="Create user"
      subtitle="Provision a new user account and optionally assign organization roles."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Users", href: listState.withCurrentSearch(settingsPaths.organization.users) },
        { label: "Create" },
      ]}
      actions={
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.users))}>
          Cancel
        </Button>
      }
      sections={USER_CREATE_SECTIONS}
      defaultSectionId="identity"
    >
      <SettingsFormErrorSummary summary={errorSummary.summary} />
      <SettingsFeedbackRegion
        messages={[
          ...(errorMessage ? [{ tone: "danger" as const, message: errorMessage }] : []),
          ...(provisionedPassword
            ? [
                {
                  tone: "success" as const,
                  heading: "One-time password generated",
                  message: `Copy this password now: ${provisionedPassword}`,
                },
              ]
            : []),
        ]}
      />

      <SettingsDetailSection id="identity" title="Identity">
        <FormField label="Email" required error={errorSummary.getFieldError("email")}>
          <Input
            id="create-user-email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="user@example.com"
            disabled={createUserMutation.isPending}
          />
        </FormField>
        <FormField label="Display name" error={errorSummary.getFieldError("display_name")}>
          <Input
            id="create-user-display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Alex Morgan"
            disabled={createUserMutation.isPending}
          />
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="password-provisioning" title="Password provisioning">
        <FormField label="Provisioning mode" required>
          <Select
            value={passwordMode}
            onValueChange={(value) => setPasswordMode(value as "auto_generate" | "explicit")}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto_generate">Auto generate one-time password</SelectItem>
              <SelectItem value="explicit">Set explicit password</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        {passwordMode === "explicit" ? (
          <FormField label="Password" required error={errorSummary.getFieldError("password")}>
            <Input
              id="create-user-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={createUserMutation.isPending}
            />
          </FormField>
        ) : null}

        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={forcePasswordReset}
            onChange={(event) => setForcePasswordReset(event.target.checked)}
            disabled={createUserMutation.isPending}
          />
          Force password change on next sign in
        </label>
      </SettingsDetailSection>

      <SettingsDetailSection
        id="organization-roles"
        title="Organization roles"
        description="Optional initial global role assignments."
      >
        {rolesQuery.data?.items.length ? (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {rolesQuery.data.items.map((role) => {
              const checked = selectedRoleIds.includes(role.id);
              const checkboxId = `create-user-role-${role.id}`;
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
                    disabled={createUserMutation.isPending || assignRoleMutation.isPending}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{role.name}</span>
                    <span className="block text-xs text-muted-foreground">{role.description || role.slug}</span>
                  </label>
                </div>
              );
            })}
          </div>
        ) : rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading roles...</p>
        ) : (
          <p className="text-sm text-muted-foreground">No organization roles available.</p>
        )}
      </SettingsDetailSection>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.users))}>
          Cancel
        </Button>
        <Button onClick={handleCreate} disabled={createUserMutation.isPending || assignRoleMutation.isPending}>
          {createUserMutation.isPending || assignRoleMutation.isPending ? "Creating..." : "Create user"}
        </Button>
      </div>
    </SettingsDetailLayout>
  );
}

export function OrganizationUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState();

  const canView = hasUserSettingsAccess(permissions);
  const canManage = canManageUsers(permissions);
  const canReadRoles = permissions.has("roles.read_all") || permissions.has("roles.manage_all");
  const canManageRoles = permissions.has("roles.manage_all") && canManage;
  const canReadGroups = permissions.has("groups.read_all") || permissions.has("groups.manage_all");
  const canManageGroups = permissions.has("groups.manage_all") && canManage;
  const canReadApiKeys = permissions.has("api_keys.read_all") || permissions.has("api_keys.manage_all");
  const canManageApiKeys = permissions.has("api_keys.manage_all") && canManage;

  const detailQuery = useOrganizationUserDetailQuery(userId ?? null);
  const userRolesQuery = useOrganizationUserRolesQuery(userId ?? null);
  const rolesQuery = useOrganizationRolesListQuery();
  const memberOfQuery = useOrganizationUserMemberOfQuery(userId ?? null);
  const groupsQuery = useOrganizationGroupsListQuery("");
  const apiKeysQuery = useOrganizationUserApiKeysQuery(canReadApiKeys ? userId ?? null : null);

  const updateMutation = useUpdateOrganizationUserMutation();
  const deactivateMutation = useDeactivateOrganizationUserMutation();
  const assignRoleMutation = useAssignOrganizationUserRoleMutation();
  const removeRoleMutation = useRemoveOrganizationUserRoleMutation();
  const addMemberOfMutation = useAddOrganizationUserMemberOfMutation();
  const removeMemberOfMutation = useRemoveOrganizationUserMemberOfMutation();
  const createApiKeyMutation = useCreateOrganizationUserApiKeyMutation();
  const revokeApiKeyMutation = useRevokeOrganizationUserApiKeyMutation();

  const [displayName, setDisplayName] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [groupToAdd, setGroupToAdd] = useState<string>("");
  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyTtlDays, setApiKeyTtlDays] = useState("");
  const [createdApiSecret, setCreatedApiSecret] = useState<string | null>(null);
  const [confirmDeactivateOpen, setConfirmDeactivateOpen] = useState(false);

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }
    setDisplayName(detailQuery.data.display_name || "");
  }, [detailQuery.data]);

  useEffect(() => {
    if (!userRolesQuery.data) {
      return;
    }
    setSelectedRoleIds(userRolesQuery.data.roles.map((role) => role.role_id));
  }, [userRolesQuery.data]);

  const hasUnsavedProfile = useMemo(() => {
    if (!detailQuery.data) return false;
    return (detailQuery.data.display_name || "") !== displayName;
  }, [detailQuery.data, displayName]);

  const hasUnsavedRoleChanges = useMemo(() => {
    const current = userRolesQuery.data?.roles.map((role) => role.role_id) ?? [];
    if (current.length !== selectedRoleIds.length) return true;
    return current.some((roleId) => !selectedRoleIds.includes(roleId));
  }, [selectedRoleIds, userRolesQuery.data?.roles]);

  const hasUnsavedChanges = hasUnsavedProfile || hasUnsavedRoleChanges;

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved user changes.",
    shouldBypassNavigation: () =>
      updateMutation.isPending ||
      assignRoleMutation.isPending ||
      removeRoleMutation.isPending,
  });

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.organization.users} />;
  }

  if (detailQuery.isLoading) {
    return <LoadingState title="Loading user" className="min-h-[300px]" />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <SettingsErrorState
        title="User unavailable"
        message={
          normalizeSettingsError(detailQuery.error, "Unable to load user details.").message
        }
      />
    );
  }

  const user = detailQuery.data;
  const currentRoleIds = userRolesQuery.data?.roles.map((role) => role.role_id) ?? [];
  const availableGroups = groupsQuery.data?.items ?? [];
  const memberOfItems = memberOfQuery.data?.items ?? [];
  const availableGroupOptions = availableGroups.filter(
    (group) => !memberOfItems.some((memberOf) => memberOf.group_id === group.id),
  );

  const saveChanges = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      if (hasUnsavedProfile) {
        await updateMutation.mutateAsync({
          userId: user.id,
          payload: { display_name: displayName.trim() || null },
        });
      }

      if (hasUnsavedRoleChanges && canManageRoles) {
        const toAssign = selectedRoleIds.filter((roleId) => !currentRoleIds.includes(roleId));
        const toRemove = currentRoleIds.filter((roleId) => !selectedRoleIds.includes(roleId));

        await Promise.all([
          ...toAssign.map((roleId) => assignRoleMutation.mutateAsync({ userId: user.id, roleId })),
          ...toRemove.map((roleId) => removeRoleMutation.mutateAsync({ userId: user.id, roleId })),
        ]);
      }

      setSuccessMessage("User settings saved.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to save user settings.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title={user.display_name || user.email}
      subtitle="Edit user profile, organization access assignments, and API keys."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Users", href: listState.withCurrentSearch(settingsPaths.organization.users) },
        { label: user.email },
      ]}
      actions={<Badge variant={user.is_active ? "secondary" : "outline"}>{user.is_active ? "Active" : "Inactive"}</Badge>}
      sections={USER_DETAIL_SECTIONS}
      defaultSectionId="profile"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}
      {createdApiSecret ? (
        <Alert tone="success" heading="New API key generated">
          Copy this secret now: <strong>{createdApiSecret}</strong>
        </Alert>
      ) : null}

      <SettingsDetailSection id="profile" title="Profile">
        <FormField label="Email">
          <Input value={user.email} disabled />
        </FormField>
        <FormField label="Display name">
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            disabled={!canManage || updateMutation.isPending}
          />
        </FormField>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Created</p>
            <p className="text-sm text-foreground">{formatDateTime(user.created_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Updated</p>
            <p className="text-sm text-foreground">{formatDateTime(user.updated_at)}</p>
          </div>
        </div>
      </SettingsDetailSection>

      <SettingsDetailSection
        id="organization-roles"
        title="Organization roles"
        description="Role assignment controls global access."
      >
        {!canReadRoles ? (
          <Alert tone="info">You do not have permission to read organization roles.</Alert>
        ) : rolesQuery.isLoading || userRolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading roles...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {rolesQuery.data?.items.map((role) => {
              const checked = selectedRoleIds.includes(role.id);
              const checkboxId = `detail-user-role-${role.id}`;
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
                    disabled={!canManageRoles || assignRoleMutation.isPending || removeRoleMutation.isPending}
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

      <SettingsDetailSection id="group-memberships" title="Group memberships">
        {!canReadGroups ? (
          <Alert tone="info">You do not have permission to read groups.</Alert>
        ) : (
          <>
            {memberOfItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">This user is not a member of any groups.</p>
            ) : (
              <div className="overflow-hidden rounded-xl border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Group</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {memberOfItems.map((memberOf) => (
                      <TableRow key={memberOf.group_id}>
                        <TableCell>
                          <p className="font-medium text-foreground">{memberOf.display_name}</p>
                          <p className="text-xs text-muted-foreground">{memberOf.slug}</p>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{memberOf.source}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={!canManageGroups || removeMemberOfMutation.isPending}
                            onClick={async () => {
                              setErrorMessage(null);
                              setSuccessMessage(null);
                              try {
                                await removeMemberOfMutation.mutateAsync({ userId: user.id, groupId: memberOf.group_id });
                                setSuccessMessage("Group membership removed.");
                              } catch (error) {
                                setErrorMessage(normalizeSettingsError(error, "Unable to remove membership.").message);
                              }
                            }}
                          >
                            Remove
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {canManageGroups ? (
              <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
                <FormField label="Add to group">
                  <Select value={groupToAdd} onValueChange={setGroupToAdd}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select group" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableGroupOptions.map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.display_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
                <Button
                  disabled={!groupToAdd || addMemberOfMutation.isPending}
                  onClick={async () => {
                    setErrorMessage(null);
                    setSuccessMessage(null);
                    try {
                      await addMemberOfMutation.mutateAsync({ userId: user.id, groupId: groupToAdd });
                      setGroupToAdd("");
                      setSuccessMessage("Group membership added.");
                    } catch (error) {
                      setErrorMessage(normalizeSettingsError(error, "Unable to add membership.").message);
                    }
                  }}
                >
                  Add group
                </Button>
              </div>
            ) : null}
          </>
        )}
      </SettingsDetailSection>

      <SettingsDetailSection id="user-api-keys" title="User API keys">
        {!canReadApiKeys ? (
          <Alert tone="info">You do not have permission to read API keys.</Alert>
        ) : apiKeysQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading API keys...</p>
        ) : (
          <>
            {(apiKeysQuery.data?.items.length ?? 0) > 0 ? (
              <div className="overflow-hidden rounded-xl border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Prefix</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeysQuery.data?.items.map((apiKey) => (
                      <TableRow key={apiKey.id}>
                        <TableCell>{apiKey.name || "Untitled key"}</TableCell>
                        <TableCell>{apiKey.prefix}</TableCell>
                        <TableCell>{formatDateTime(apiKey.created_at)}</TableCell>
                        <TableCell>
                          <Badge variant={apiKey.revoked_at ? "outline" : "secondary"}>
                            {apiKey.revoked_at ? "Revoked" : "Active"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={!canManageApiKeys || Boolean(apiKey.revoked_at) || revokeApiKeyMutation.isPending}
                            onClick={async () => {
                              setErrorMessage(null);
                              setSuccessMessage(null);
                              try {
                                await revokeApiKeyMutation.mutateAsync({
                                  userId: user.id,
                                  apiKeyId: apiKey.id,
                                  ifMatch: buildWeakEtag(apiKey.id, apiKey.revoked_at ?? apiKey.created_at),
                                });
                                setSuccessMessage("API key revoked.");
                              } catch (error) {
                                setErrorMessage(normalizeSettingsError(error, "Unable to revoke API key.").message);
                              }
                            }}
                          >
                            Revoke
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No API keys for this user.</p>
            )}

            {canManageApiKeys ? (
              <div className="grid gap-2 sm:grid-cols-[1fr_160px_auto] sm:items-end">
                <FormField label="Key name">
                  <Input value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} placeholder="Automation key" />
                </FormField>
                <FormField label="TTL days">
                  <Input value={apiKeyTtlDays} onChange={(event) => setApiKeyTtlDays(event.target.value)} placeholder="Optional" />
                </FormField>
                <Button
                  disabled={createApiKeyMutation.isPending}
                  onClick={async () => {
                    setErrorMessage(null);
                    setSuccessMessage(null);
                    setCreatedApiSecret(null);
                    try {
                      const created = await createApiKeyMutation.mutateAsync({
                        userId: user.id,
                        payload: {
                          name: apiKeyName.trim() || null,
                          expires_in_days: apiKeyTtlDays.trim() ? Number(apiKeyTtlDays) : null,
                        },
                      });
                      setApiKeyName("");
                      setApiKeyTtlDays("");
                      setCreatedApiSecret(created.secret);
                      setSuccessMessage("API key created.");
                    } catch (error) {
                      setErrorMessage(normalizeSettingsError(error, "Unable to create API key.").message);
                    }
                  }}
                >
                  Create key
                </Button>
              </div>
            ) : null}
          </>
        )}
      </SettingsDetailSection>

      <SettingsDetailSection id="lifecycle" title="Lifecycle" tone="danger">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Deactivate this user account to stop sign in and access.</p>
          <Button
            variant="destructive"
            disabled={!canManage || !user.is_active || deactivateMutation.isPending}
            onClick={() => setConfirmDeactivateOpen(true)}
          >
            {deactivateMutation.isPending ? "Deactivating..." : "Deactivate user"}
          </Button>
        </div>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        isSaving={updateMutation.isPending || assignRoleMutation.isPending || removeRoleMutation.isPending}
        canSave={canManage && (!hasUnsavedRoleChanges || canManageRoles)}
        disabledReason={
          canManage && (!hasUnsavedRoleChanges || canManageRoles)
            ? undefined
            : "You do not have permission to save role changes."
        }
        onDiscard={() => {
          setDisplayName(user.display_name || "");
          setSelectedRoleIds(currentRoleIds);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        onSave={() => {
          void saveChanges();
        }}
        message="User changes are pending"
      />

      <ConfirmDialog
        open={confirmDeactivateOpen}
        title="Deactivate user?"
        description={`Deactivate ${user.email}. This blocks sign in and managed access.`}
        confirmLabel="Deactivate"
        tone="danger"
        onCancel={() => setConfirmDeactivateOpen(false)}
        onConfirm={async () => {
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await deactivateMutation.mutateAsync(user.id);
            setConfirmDeactivateOpen(false);
            setSuccessMessage("User deactivated.");
            void detailQuery.refetch();
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to deactivate user.").message);
          }
        }}
        isConfirming={deactivateMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
