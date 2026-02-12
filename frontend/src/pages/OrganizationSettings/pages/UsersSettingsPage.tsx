import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { buildWeakEtag } from "@/api/etag";
import { mapUiError } from "@/api/uiErrors";
import { collectAllPages, MAX_PAGE_SIZE } from "@/api/pagination";
import { executeUserBatchChunked, type BatchSubrequest } from "@/api/users/api";
import {
  addAdminUserMemberOf,
  listAdminUserMemberOf,
  removeAdminUserMemberOf,
} from "@/api/admin/users";
import { listGroups, type Group } from "@/api/groups/api";
import { createWorkspaceRoleAssignment, listWorkspaceRoles } from "@/api/workspaces/api";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  useAdminRolesQuery,
  useAdminUserApiKeysQuery,
  useAdminUserRolesQuery,
  useAdminUsersQuery,
  useAssignAdminUserRoleMutation,
  useCreateAdminUserApiKeyMutation,
  useCreateAdminUserMutation,
  useDeactivateAdminUserMutation,
  useRemoveAdminUserRoleMutation,
  useRevokeAdminUserApiKeyMutation,
  useUpdateAdminUserMutation,
} from "@/hooks/admin";
import { useWorkspacesQuery } from "@/hooks/workspaces";
import { useSession } from "@/providers/auth/SessionContext";
import {
  AccessCommandBar,
  AssignmentChips,
  BatchResultPanel,
  resolveAccessActionState,
  type BatchResultSummary,
  PrincipalIdentityCell,
} from "@/pages/SharedAccess/components";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import type { ApiKeySummary } from "@/types";
import type { RoleDefinition, WorkspaceProfile } from "@/types/workspaces";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";
import { useOrganizationSettingsSection } from "../sectionContext";

type FeedbackMessage = { tone: "success" | "danger"; message: string };

type KeyReveal = {
  readonly id: string;
  readonly prefix: string;
  readonly secret: string;
};

type ProvisionedPassword = {
  readonly email: string;
  readonly secret: string;
};

type CreateUserInput = {
  readonly email: string;
  readonly displayName: string;
  readonly properties: {
    readonly givenName: string;
    readonly surname: string;
    readonly jobTitle: string;
    readonly department: string;
    readonly officeLocation: string;
    readonly mobilePhone: string;
    readonly businessPhones: string;
    readonly employeeId: string;
  };
  readonly organizationRoleIds: string[];
  readonly workspaceSeed:
    | {
        readonly workspaceId: string;
        readonly roleIds: string[];
      }
    | null;
  readonly passwordProfile: {
    readonly mode: "auto_generate" | "explicit";
    readonly password?: string;
    readonly forceChangeOnNextSignIn: boolean;
  };
};

const SIMPLE_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function UsersSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const { params } = useOrganizationSettingsSection();
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageUsers = hasPermission("users.manage_all");
  const canReadUsers = hasPermission("users.read_all") || canManageUsers;
  const canReadGroups = hasPermission("groups.read_all") || hasPermission("groups.manage_all");
  const canReadGroupMembers =
    hasPermission("groups.members.read_all") ||
    hasPermission("groups.members.manage_all") ||
    hasPermission("groups.manage_all");
  const canManageGroupMembers =
    hasPermission("groups.members.manage_all") || hasPermission("groups.manage_all");
  const canReadUserMemberOf = canReadUsers && canReadGroupMembers;
  const canManageUserMemberOf = canManageUsers && canManageGroupMembers;

  const [searchValue, setSearchValue] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [bulkResult, setBulkResult] = useState<BatchResultSummary | null>(null);
  const [isRetryingBulk, setIsRetryingBulk] = useState(false);
  const [confirmBulkDeactivateOpen, setConfirmBulkDeactivateOpen] = useState(false);

  const usersQuery = useAdminUsersQuery({
    enabled: canReadUsers,
    pageSize: 100,
    search: searchValue,
  });
  const rolesQuery = useAdminRolesQuery("global");
  const workspacesQuery = useWorkspacesQuery();
  const groupsQuery = useQuery({
    queryKey: ["organization", "groups", "user-member-of"],
    queryFn: ({ signal }) => listGroups({ signal }),
    enabled: canReadGroups,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
  const workspaceRoleCatalogQuery = useQuery({
    queryKey: ["roles", "workspace", "catalog"],
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listWorkspaceRoles({
          limit: MAX_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    enabled: canManageUsers,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });

  const createUser = useCreateAdminUserMutation();
  const updateUser = useUpdateAdminUserMutation();
  const deactivateUser = useDeactivateAdminUserMutation();
  const assignRole = useAssignAdminUserRoleMutation();
  const removeRole = useRemoveAdminUserRoleMutation();
  const createUserApiKey = useCreateAdminUserApiKeyMutation();
  const revokeUserApiKey = useRevokeAdminUserApiKeyMutation();

  const [feedbackMessage, setFeedbackMessage] = useState<FeedbackMessage | null>(null);
  const [provisionedPassword, setProvisionedPassword] = useState<ProvisionedPassword | null>(
    null,
  );
  const [provisionedCopyStatus, setProvisionedCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );

  const users = usersQuery.users;
  const filteredUsers = useMemo(() => {
    return users.filter((user) => {
      if (statusFilter === "active") {
        return user.is_active;
      }
      if (statusFilter === "inactive") {
        return !user.is_active;
      }
      return true;
    });
  }, [statusFilter, users]);

  useEffect(() => {
    const availableIds = new Set(filteredUsers.map((user) => user.id));
    setSelectedUserIds((current) => {
      const next = new Set(Array.from(current).filter((id) => availableIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [filteredUsers]);

  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedUserId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedUser = users.find((entry) => entry.id === selectedUserId);

  const basePath = "/organization/access/users";
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openCreateDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openUserDrawer = (userId: string) => navigate(`${basePath}/${encodeURIComponent(userId)}${suffix}`);

  const selectedUsersForBulk = useMemo(
    () =>
      filteredUsers.filter(
        (user) => selectedUserIds.has(user.id) && user.id !== session.user.id,
      ),
    [filteredUsers, selectedUserIds, session.user.id],
  );

  const canBulkDeactivate = canManageUsers && selectedUsersForBulk.length > 0;

  const runBulkDeactivate = async (userIds: string[]) => {
    if (userIds.length === 0) {
      return;
    }

    const requests: BatchSubrequest[] = userIds.map((userId) => ({
      id: userId,
      method: "POST",
      url: `/users/${userId}/deactivate`,
      dependsOn: [],
    }));

    const response = await executeUserBatchChunked(requests);
    const failed = response.responses
      .filter((item) => item.status >= 400)
      .map((item) => {
        const user = users.find((entry) => entry.id === item.id);
        return {
          id: item.id,
          label: user?.display_name || user?.email || item.id,
          status: item.status,
          message: parseBatchErrorMessage(item.body),
        };
      });

    const summary: BatchResultSummary = {
      requested: requests.length,
      succeeded: response.responses.length - failed.length,
      failed,
    };
    setBulkResult(summary);

    if (summary.succeeded > 0) {
      setFeedbackMessage({ tone: "success", message: "Bulk deactivation completed." });
      setSelectedUserIds(new Set());
      await usersQuery.refetch();
    }
  };

  if (!canReadUsers) {
    return <Alert tone="danger">You do not have permission to access users.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {provisionedPassword ? (
        <div className="space-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3">
          <p className="text-sm font-semibold text-warning-foreground">
            Copy the initial password for {provisionedPassword.email}
          </p>
          <p className="text-xs text-warning-foreground/90">
            This password is shown only once. Store it securely and share it through a trusted channel.
          </p>
          <div className="flex flex-col gap-2 rounded-md border border-warning/40 bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
            <code className="break-all text-xs text-foreground">{provisionedPassword.secret}</code>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(provisionedPassword.secret);
                    setProvisionedCopyStatus("copied");
                  } catch {
                    setProvisionedCopyStatus("failed");
                  }
                }}
              >
                Copy
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  setProvisionedPassword(null);
                  setProvisionedCopyStatus("idle");
                }}
              >
                Dismiss
              </Button>
            </div>
          </div>
          {provisionedCopyStatus === "copied" ? (
            <p className="text-xs text-success">Password copied to clipboard.</p>
          ) : null}
          {provisionedCopyStatus === "failed" ? (
            <p className="text-xs text-destructive">Unable to copy. Copy manually.</p>
          ) : null}
        </div>
      ) : null}
      {usersQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(usersQuery.error, { fallback: "Unable to load users." }).message}
        </Alert>
      ) : null}
      {groupsQuery.isError ? (
        <Alert tone="warning">
          {mapUiError(groupsQuery.error, { fallback: "Unable to load groups for membership management." }).message}
        </Alert>
      ) : null}

      {bulkResult ? (
        <BatchResultPanel
          result={bulkResult}
          onDismiss={() => setBulkResult(null)}
          onRetryFailed={
            bulkResult.failed.length > 0
              ? async () => {
                  setIsRetryingBulk(true);
                  try {
                    await runBulkDeactivate(bulkResult.failed.map((item) => item.id));
                  } finally {
                    setIsRetryingBulk(false);
                  }
                }
              : undefined
          }
          isRetrying={isRetryingBulk}
        />
      ) : null}

      <SettingsSection
        title="Users"
        description={usersQuery.isLoading ? "Loading users..." : `${filteredUsers.length} users`}
        actions={
          canManageUsers ? (
            <Button type="button" size="sm" onClick={openCreateDrawer}>
              Create user
            </Button>
          ) : null
        }
      >
        <AccessCommandBar
          searchValue={searchValue}
          onSearchValueChange={setSearchValue}
          searchPlaceholder="Search users"
          searchAriaLabel="Search users"
          controls={
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as "all" | "active" | "inactive")}>
              <SelectTrigger className="w-full min-w-36 sm:w-40">
                <SelectValue placeholder="Filter status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          }
          actions={
            canBulkDeactivate ? (
              <>
                <Badge variant="secondary">{selectedUsersForBulk.length} selected</Badge>
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  onClick={() => setConfirmBulkDeactivateOpen(true)}
                >
                  Deactivate selected
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setSelectedUserIds(new Set())}
                >
                  Clear
                </Button>
              </>
            ) : null
          }
        />

        {usersQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading users...</p>
        ) : filteredUsers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No users match your current filters.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={filteredUsers}
            getItemKey={(user) => user.id}
            mobileListLabel="Organization users"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="w-10 px-4">
                        <input
                          aria-label="Select all users"
                          type="checkbox"
                          className="h-4 w-4 rounded border-border"
                          checked={
                            selectedUsersForBulk.length > 0 &&
                            selectedUsersForBulk.length ===
                              filteredUsers.filter((user) => user.id !== session.user.id).length
                          }
                          onChange={(event) => {
                            if (!event.target.checked) {
                              setSelectedUserIds(new Set());
                              return;
                            }
                            const selectableIds = filteredUsers
                              .filter((user) => user.id !== session.user.id)
                              .map((user) => user.id);
                            setSelectedUserIds(new Set(selectableIds));
                          }}
                        />
                      </TableHead>
                      <TableHead className="px-4">User</TableHead>
                      <TableHead className="px-4">Roles</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredUsers.map((user) => (
                      <TableRow key={user.id} className="text-sm text-foreground">
                        <TableCell className="px-4 py-3">
                          <input
                            aria-label={`Select ${user.display_name || user.email}`}
                            type="checkbox"
                            className="h-4 w-4 rounded border-border"
                            disabled={!canManageUsers || user.id === session.user.id}
                            checked={selectedUserIds.has(user.id)}
                            onChange={(event) => {
                              setSelectedUserIds((current) => {
                                const next = new Set(current);
                                if (event.target.checked) {
                                  next.add(user.id);
                                } else {
                                  next.delete(user.id);
                                }
                                return next;
                              });
                            }}
                          />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <PrincipalIdentityCell
                            principalType="user"
                            title={user.display_name || user.email}
                            subtitle={user.email}
                            detail={user.department || undefined}
                          />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <AssignmentChips assignments={user.roles ?? []} emptyLabel="No roles" />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={user.is_active ? "secondary" : "outline"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button type="button" variant="ghost" size="sm" onClick={() => openUserDrawer(user.id)}>
                            {canManageUsers ? "Manage" : "View"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(user) => (
              <>
                <PrincipalIdentityCell
                  principalType="user"
                  title={user.display_name || user.email}
                  subtitle={user.email}
                  detail={user.department || undefined}
                />
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Roles</dt>
                  <dd>
                    <AssignmentChips assignments={user.roles ?? []} emptyLabel="No roles" />
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={user.is_active ? "secondary" : "outline"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => openUserDrawer(user.id)}>
                    {canManageUsers ? "Manage" : "View"}
                  </Button>
                </div>
              </>
            )}
          />
        )}

        {usersQuery.hasNextPage ? (
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => usersQuery.fetchNextPage()}
              disabled={usersQuery.isFetchingNextPage}
            >
              {usersQuery.isFetchingNextPage ? "Loading more users..." : "Load more users"}
            </Button>
          </div>
        ) : null}

        {!canManageUsers ? (
          <Alert tone="info">You can view users, but you need user management permission to make changes.</Alert>
        ) : null}
      </SettingsSection>

      <CreateUserDrawer
        open={isCreateOpen && canManageUsers}
        onClose={closeDrawer}
        availableRoles={rolesQuery.data?.items ?? []}
        availableWorkspaces={workspacesQuery.data?.items ?? []}
        availableWorkspaceRoles={workspaceRoleCatalogQuery.data?.items ?? []}
        onSubmit={async ({
          email,
          displayName,
          passwordProfile,
          properties,
          organizationRoleIds,
          workspaceSeed,
        }: CreateUserInput) => {
          setFeedbackMessage(null);
          setProvisionedPassword(null);
          setProvisionedCopyStatus("idle");

          const created = await createUser.mutateAsync({
            email,
            displayName: displayName || null,
            givenName: properties.givenName || null,
            surname: properties.surname || null,
            jobTitle: properties.jobTitle || null,
            department: properties.department || null,
            officeLocation: properties.officeLocation || null,
            mobilePhone: properties.mobilePhone || null,
            businessPhones: properties.businessPhones || null,
            employeeId: properties.employeeId || null,
            passwordProfile,
          });

          const createdUser = created.user;

          await Promise.all(
            organizationRoleIds.map((roleId) =>
              assignRole.mutateAsync({ userId: createdUser.id, roleId }),
            ),
          );

          if (workspaceSeed && workspaceSeed.workspaceId && workspaceSeed.roleIds.length > 0) {
            await Promise.all(
              workspaceSeed.roleIds.map((roleId) =>
                createWorkspaceRoleAssignment(workspaceSeed.workspaceId, {
                  principal_type: "user",
                  principal_id: createdUser.id,
                  role_id: roleId,
                }),
              ),
            );
          }

          setFeedbackMessage({ tone: "success", message: "User created with initial access assignments." });

          if (
            created.passwordProvisioning.mode === "auto_generate" &&
            created.passwordProvisioning.initialPassword
          ) {
            setProvisionedPassword({
              email: created.user.email,
              secret: created.passwordProvisioning.initialPassword,
            });
          }
          closeDrawer();
        }}
        isSubmitting={createUser.isPending || assignRole.isPending}
      />

      <ManageUserDrawer
        open={Boolean(selectedUserId)}
        userId={selectedUserId}
        user={selectedUser}
        canManage={canManageUsers}
        canReadUserMemberOf={canReadUserMemberOf}
        canManageUserMemberOf={canManageUserMemberOf}
        availableGroups={groupsQuery.data?.items ?? []}
        currentUserId={session.user.id}
        roles={rolesQuery.data?.items ?? []}
        onOpenGroup={(groupId) => navigate(`/organization/access/groups/${encodeURIComponent(groupId)}${suffix}`)}
        onClose={closeDrawer}
        onUpdateProfile={async (payload) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await updateUser.mutateAsync({ userId: selectedUserId, payload });
          setFeedbackMessage({ tone: "success", message: "User profile updated." });
        }}
        onDeactivate={async () => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await deactivateUser.mutateAsync(selectedUserId);
          setFeedbackMessage({ tone: "success", message: "User deactivated." });
          closeDrawer();
        }}
        onSaveRoles={async (draftRoleIds, currentRoleIds) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          const toAssign = draftRoleIds.filter((roleId) => !currentRoleIds.includes(roleId));
          const toRemove = currentRoleIds.filter((roleId) => !draftRoleIds.includes(roleId));

          await Promise.all([
            ...toAssign.map((roleId) => assignRole.mutateAsync({ userId: selectedUserId, roleId })),
            ...toRemove.map((roleId) => removeRole.mutateAsync({ userId: selectedUserId, roleId })),
          ]);
          setFeedbackMessage({ tone: "success", message: "Roles updated." });
        }}
        onCreateApiKey={async ({ name, expiresInDays }) => {
          if (!selectedUserId) return null;
          setFeedbackMessage(null);
          const created = await createUserApiKey.mutateAsync({
            userId: selectedUserId,
            payload: {
              name: name || undefined,
              expires_in_days: expiresInDays ?? undefined,
            },
          });
          setFeedbackMessage({ tone: "success", message: "API key created." });
          return created;
        }}
        onRevokeApiKey={async (key) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await revokeUserApiKey.mutateAsync({
            userId: selectedUserId,
            apiKeyId: key.id,
            ifMatch: buildWeakEtag(key.id, key.revoked_at ?? key.created_at),
          });
          setFeedbackMessage({ tone: "success", message: "API key revoked." });
        }}
        isMutating={
          updateUser.isPending ||
          deactivateUser.isPending ||
          assignRole.isPending ||
          removeRole.isPending ||
          createUserApiKey.isPending ||
          revokeUserApiKey.isPending
        }
      />

      <ConfirmDialog
        open={confirmBulkDeactivateOpen}
        title="Deactivate selected users?"
        description={`Deactivate ${selectedUsersForBulk.length} selected user${selectedUsersForBulk.length === 1 ? "" : "s"}.`}
        confirmLabel="Deactivate users"
        tone="danger"
        onCancel={() => setConfirmBulkDeactivateOpen(false)}
        onConfirm={async () => {
          try {
            await runBulkDeactivate(selectedUsersForBulk.map((user) => user.id));
          } catch (error) {
            setFeedbackMessage({
              tone: "danger",
              message: error instanceof Error ? error.message : "Bulk deactivation failed.",
            });
          } finally {
            setConfirmBulkDeactivateOpen(false);
          }
        }}
      />
    </div>
  );
}

function parseBatchErrorMessage(body: unknown): string {
  if (body && typeof body === "object") {
    const asRecord = body as Record<string, unknown>;
    const detail = asRecord.detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
    const message = asRecord.message;
    if (typeof message === "string" && message.trim().length > 0) {
      return message;
    }
  }
  return "Operation failed.";
}

function CreateUserDrawer({
  open,
  onClose,
  onSubmit,
  isSubmitting,
  availableRoles,
  availableWorkspaces,
  availableWorkspaceRoles,
}: {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (input: CreateUserInput) => Promise<void>;
  readonly isSubmitting: boolean;
  readonly availableRoles: readonly { id: string; name: string }[];
  readonly availableWorkspaces: readonly WorkspaceProfile[];
  readonly availableWorkspaceRoles: readonly RoleDefinition[];
}) {
  const [stepIndex, setStepIndex] = useState(0);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [givenName, setGivenName] = useState("");
  const [surname, setSurname] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [officeLocation, setOfficeLocation] = useState("");
  const [mobilePhone, setMobilePhone] = useState("");
  const [businessPhones, setBusinessPhones] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [passwordMode, setPasswordMode] = useState<"auto_generate" | "explicit">("auto_generate");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [forceChangeOnNextSignIn, setForceChangeOnNextSignIn] = useState(false);
  const [organizationRoleIds, setOrganizationRoleIds] = useState<string[]>([]);
  const [seedWorkspaceAccess, setSeedWorkspaceAccess] = useState(false);
  const [seedWorkspaceId, setSeedWorkspaceId] = useState("");
  const [seedWorkspaceRoleIds, setSeedWorkspaceRoleIds] = useState<string[]>([]);

  const [error, setError] = useState<string | null>(null);

  const steps = ["Basics", "Properties", "Assignments", "Review"] as const;
  const isLastStep = stepIndex === steps.length - 1;

  useEffect(() => {
    if (!open) {
      setStepIndex(0);
      setEmail("");
      setDisplayName("");
      setGivenName("");
      setSurname("");
      setJobTitle("");
      setDepartment("");
      setOfficeLocation("");
      setMobilePhone("");
      setBusinessPhones("");
      setEmployeeId("");
      setPasswordMode("auto_generate");
      setPassword("");
      setConfirmPassword("");
      setForceChangeOnNextSignIn(false);
      setOrganizationRoleIds([]);
      setSeedWorkspaceAccess(false);
      setSeedWorkspaceId("");
      setSeedWorkspaceRoleIds([]);
      setError(null);
    }
  }, [open]);

  const validateBasics = () => {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Email is required.");
      return false;
    }
    if (!SIMPLE_EMAIL_PATTERN.test(trimmedEmail)) {
      setError("Enter a valid email address.");
      return false;
    }

    if (passwordMode === "explicit") {
      if (!password) {
        setError("Password is required in explicit mode.");
        return false;
      }
      if (password !== confirmPassword) {
        setError("Password and confirmation must match.");
        return false;
      }
    }

    return true;
  };

  const validateAssignments = () => {
    if (!seedWorkspaceAccess) {
      return true;
    }
    if (!seedWorkspaceId) {
      setError("Select a workspace for workspace role seeding.");
      return false;
    }
    if (seedWorkspaceRoleIds.length === 0) {
      setError("Select at least one workspace role when workspace seeding is enabled.");
      return false;
    }
    return true;
  };

  const goNext = () => {
    setError(null);
    if (stepIndex === 0 && !validateBasics()) {
      return;
    }
    if (stepIndex === 2 && !validateAssignments()) {
      return;
    }
    setStepIndex((current) => Math.min(current + 1, steps.length - 1));
  };

  const goBack = () => {
    setError(null);
    setStepIndex((current) => Math.max(current - 1, 0));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!validateBasics() || !validateAssignments()) {
      return;
    }

    try {
      await onSubmit({
        email: email.trim().toLowerCase(),
        displayName: displayName.trim(),
        properties: {
          givenName: givenName.trim(),
          surname: surname.trim(),
          jobTitle: jobTitle.trim(),
          department: department.trim(),
          officeLocation: officeLocation.trim(),
          mobilePhone: mobilePhone.trim(),
          businessPhones: businessPhones.trim(),
          employeeId: employeeId.trim(),
        },
        organizationRoleIds,
        workspaceSeed: seedWorkspaceAccess
          ? {
              workspaceId: seedWorkspaceId,
              roleIds: seedWorkspaceRoleIds,
            }
          : null,
        passwordProfile:
          passwordMode === "explicit"
            ? {
                mode: "explicit",
                password,
                forceChangeOnNextSignIn,
              }
            : {
                mode: "auto_generate",
                forceChangeOnNextSignIn,
              },
      });
    } catch (submitError) {
      const mapped = mapUiError(submitError, { fallback: "Unable to create user." });
      setError(mapped.message);
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title="Create user"
      description="Provision a user, configure profile details, and optionally assign access during creation."
      widthClassName="w-full max-w-2xl"
    >
      <form className="space-y-5" onSubmit={handleSubmit}>
        <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          {steps.map((step, index) => {
            const isActive = stepIndex === index;
            const isComplete = stepIndex > index;
            return (
              <li
                key={step}
                className={`rounded-md border px-2 py-2 text-center font-semibold ${
                  isActive
                    ? "border-ring bg-accent text-foreground"
                    : isComplete
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border text-muted-foreground"
                }`}
              >
                {index + 1}. {step}
              </li>
            );
          })}
        </ol>

        {error ? <Alert tone="danger">{error}</Alert> : null}

        {stepIndex === 0 ? (
          <div className="space-y-4">
            <FormField label="Email" required>
              <Input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="user@example.com"
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Display name">
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Optional"
                disabled={isSubmitting}
              />
            </FormField>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-foreground">Initial password</legend>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="radio"
                  name="password-mode"
                  checked={passwordMode === "auto_generate"}
                  onChange={() => setPasswordMode("auto_generate")}
                  disabled={isSubmitting}
                />
                Auto-generate password
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="radio"
                  name="password-mode"
                  checked={passwordMode === "explicit"}
                  onChange={() => setPasswordMode("explicit")}
                  disabled={isSubmitting}
                />
                Set password manually
              </label>
            </fieldset>

            {passwordMode === "explicit" ? (
              <>
                <FormField label="Password" required>
                  <Input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    disabled={isSubmitting}
                  />
                </FormField>
                <FormField label="Confirm password" required>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    disabled={isSubmitting}
                  />
                </FormField>
              </>
            ) : (
              <Alert tone="info">
                A compliant random password will be generated and shown once after user creation.
              </Alert>
            )}

            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={forceChangeOnNextSignIn}
                onChange={(event) => setForceChangeOnNextSignIn(event.target.checked)}
                disabled={isSubmitting}
              />
              Force password change on next sign-in
            </label>
          </div>
        ) : null}

        {stepIndex === 1 ? (
          <div className="grid gap-3 md:grid-cols-2">
            <FormField label="Given name">
              <Input value={givenName} onChange={(event) => setGivenName(event.target.value)} disabled={isSubmitting} />
            </FormField>
            <FormField label="Surname">
              <Input value={surname} onChange={(event) => setSurname(event.target.value)} disabled={isSubmitting} />
            </FormField>
            <FormField label="Job title">
              <Input value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} disabled={isSubmitting} />
            </FormField>
            <FormField label="Department">
              <Input value={department} onChange={(event) => setDepartment(event.target.value)} disabled={isSubmitting} />
            </FormField>
            <FormField label="Office location">
              <Input
                value={officeLocation}
                onChange={(event) => setOfficeLocation(event.target.value)}
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Mobile phone">
              <Input value={mobilePhone} onChange={(event) => setMobilePhone(event.target.value)} disabled={isSubmitting} />
            </FormField>
            <FormField label="Business phones">
              <Input
                value={businessPhones}
                onChange={(event) => setBusinessPhones(event.target.value)}
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Employee ID">
              <Input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} disabled={isSubmitting} />
            </FormField>
          </div>
        ) : null}

        {stepIndex === 2 ? (
          <div className="space-y-4">
            <fieldset className="space-y-2">
              <legend className="text-sm font-semibold text-foreground">Organization roles</legend>
              <p className="text-xs text-muted-foreground">Optional: assign global roles immediately.</p>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No organization roles available.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-border"
                        checked={organizationRoleIds.includes(role.id)}
                        onChange={(event) =>
                          setOrganizationRoleIds((current) =>
                            event.target.checked
                              ? Array.from(new Set([...current, role.id]))
                              : current.filter((id) => id !== role.id),
                          )
                        }
                        disabled={isSubmitting}
                      />
                      <span>{role.name}</span>
                    </label>
                  ))
                )}
              </div>
            </fieldset>

            <div className="space-y-3 rounded-lg border border-border bg-background p-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={seedWorkspaceAccess}
                  onChange={(event) => {
                    const enabled = event.target.checked;
                    setSeedWorkspaceAccess(enabled);
                    if (!enabled) {
                      setSeedWorkspaceId("");
                      setSeedWorkspaceRoleIds([]);
                    }
                  }}
                  disabled={isSubmitting}
                />
                Seed workspace access
              </label>
              <p className="text-xs text-muted-foreground">
                Optional: assign workspace roles at creation time so access is ready immediately.
              </p>

              {seedWorkspaceAccess ? (
                <>
                  <FormField label="Workspace" required>
                    <Select value={seedWorkspaceId || undefined} onValueChange={setSeedWorkspaceId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a workspace" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableWorkspaces.map((workspace) => (
                          <SelectItem key={workspace.id} value={workspace.id}>
                            {workspace.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormField>

                  <fieldset className="space-y-2">
                    <legend className="text-sm font-semibold text-foreground">Workspace roles</legend>
                    <div className="flex flex-wrap gap-2">
                      {availableWorkspaceRoles.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No workspace roles available.</p>
                      ) : (
                        availableWorkspaceRoles.map((role) => (
                          <label
                            key={role.id}
                            className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-border"
                              checked={seedWorkspaceRoleIds.includes(role.id)}
                              onChange={(event) =>
                                setSeedWorkspaceRoleIds((current) =>
                                  event.target.checked
                                    ? Array.from(new Set([...current, role.id]))
                                    : current.filter((id) => id !== role.id),
                                )
                              }
                              disabled={isSubmitting}
                            />
                            <span>{role.name}</span>
                          </label>
                        ))
                      )}
                    </div>
                  </fieldset>
                </>
              ) : null}
            </div>
          </div>
        ) : null}

        {stepIndex === 3 ? (
          <div className="space-y-3 rounded-lg border border-border bg-background p-4 text-sm">
            <p>
              <span className="font-semibold">Email:</span> {email || "—"}
            </p>
            <p>
              <span className="font-semibold">Display name:</span> {displayName || "—"}
            </p>
            <p>
              <span className="font-semibold">Password mode:</span>{" "}
              {passwordMode === "explicit" ? "Manual" : "Auto-generated"}
            </p>
            <div>
              <p className="font-semibold">Organization roles</p>
              <AssignmentChips
                assignments={organizationRoleIds.map((roleId) => {
                  const role = availableRoles.find((entry) => entry.id === roleId);
                  return role?.name ?? roleId;
                })}
                emptyLabel="No organization roles"
              />
            </div>
            <div>
              <p className="font-semibold">Workspace seed</p>
              {!seedWorkspaceAccess ? (
                <p className="text-muted-foreground">Not configured</p>
              ) : (
                <div className="space-y-1">
                  <p>
                    Workspace: {availableWorkspaces.find((workspace) => workspace.id === seedWorkspaceId)?.name || "—"}
                  </p>
                  <AssignmentChips
                    assignments={seedWorkspaceRoleIds.map((roleId) => {
                      const role = availableWorkspaceRoles.find((entry) => entry.id === roleId);
                      return role?.name ?? roleId;
                    })}
                    emptyLabel="No workspace roles"
                  />
                </div>
              )}
            </div>
          </div>
        ) : null}

        <div className="flex items-center justify-between gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <div className="flex items-center gap-2">
            {stepIndex > 0 ? (
              <Button type="button" variant="ghost" onClick={goBack} disabled={isSubmitting}>
                Back
              </Button>
            ) : null}
            {!isLastStep ? (
              <Button type="button" onClick={goNext} disabled={isSubmitting}>
                Next
              </Button>
            ) : (
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating..." : "Create user"}
              </Button>
            )}
          </div>
        </div>
      </form>
    </SettingsDrawer>
  );
}

function ManageUserDrawer({
  open,
  userId,
  user,
  canManage,
  canReadUserMemberOf,
  canManageUserMemberOf,
  availableGroups,
  currentUserId,
  roles,
  onOpenGroup,
  onClose,
  onUpdateProfile,
  onDeactivate,
  onSaveRoles,
  onCreateApiKey,
  onRevokeApiKey,
  isMutating,
}: {
  readonly open: boolean;
  readonly userId: string | null;
  readonly user:
    | {
        id: string;
        email: string;
        display_name?: string | null;
        is_active: boolean;
      }
    | undefined;
  readonly canManage: boolean;
  readonly canReadUserMemberOf: boolean;
  readonly canManageUserMemberOf: boolean;
  readonly availableGroups: readonly Group[];
  readonly currentUserId?: string;
  readonly roles: readonly { id: string; name: string }[];
  readonly onOpenGroup: (groupId: string) => void;
  readonly onClose: () => void;
  readonly onUpdateProfile: (payload: { display_name?: string | null; is_active?: boolean | null }) => Promise<void>;
  readonly onDeactivate: () => Promise<void>;
  readonly onSaveRoles: (draftRoleIds: string[], currentRoleIds: string[]) => Promise<void>;
  readonly onCreateApiKey: (input: { name: string; expiresInDays: number | null }) => Promise<{ id: string; prefix: string; secret: string } | null>;
  readonly onRevokeApiKey: (key: ApiKeySummary) => Promise<void>;
  readonly isMutating: boolean;
}) {
  const userRolesQuery = useAdminUserRolesQuery(userId);
  const userApiKeysQuery = useAdminUserApiKeysQuery(userId, { includeRevoked: true, limit: 100 });
  const userMemberOfQuery = useQuery({
    queryKey: ["admin", "users", userId, "memberOf"],
    queryFn: ({ signal }) => listAdminUserMemberOf(userId!, { signal }),
    enabled: open && Boolean(userId) && canReadUserMemberOf,
    staleTime: 10_000,
  });
  const addMemberOfMutation = useMutation({
    mutationFn: ({ groupId }: { groupId: string }) => addAdminUserMemberOf(userId!, groupId),
    onSuccess: () => {
      userMemberOfQuery.refetch();
    },
  });
  const removeMemberOfMutation = useMutation({
    mutationFn: ({ groupId }: { groupId: string }) => removeAdminUserMemberOf(userId!, groupId),
    onSuccess: () => {
      userMemberOfQuery.refetch();
    },
  });
  const [displayName, setDisplayName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [groupSearch, setGroupSearch] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyExpiry, setApiKeyExpiry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [issuedKey, setIssuedKey] = useState<KeyReveal | null>(null);
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const hasExpiryInput = apiKeyExpiry.trim().length > 0;
  const parsedExpiry = hasExpiryInput ? Number.parseInt(apiKeyExpiry.trim(), 10) : null;
  const apiKeyExpiryError =
    hasExpiryInput && (!Number.isInteger(parsedExpiry ?? Number.NaN) || (parsedExpiry ?? 0) <= 0)
      ? "Expiration must be a positive whole number of days."
      : null;

  const currentRoleIds = useMemo(
    () => (userRolesQuery.data?.roles ?? []).map((entry: { role_id: string }) => entry.role_id),
    [userRolesQuery.data?.roles],
  );
  const memberOfItems = userMemberOfQuery.data?.items ?? [];
  const memberOfByGroupId = useMemo(() => {
    const next = new Map<string, (typeof memberOfItems)[number]>();
    for (const item of memberOfItems) {
      next.set(item.group_id, item);
    }
    return next;
  }, [memberOfItems]);
  const filteredGroupOptions = useMemo(() => {
    const query = groupSearch.trim().toLowerCase();
    return availableGroups
      .filter((group) => !memberOfByGroupId.get(group.id)?.is_member)
      .filter((group) => {
        if (!query) {
          return true;
        }
        return `${group.display_name} ${group.slug} ${group.description ?? ""}`
          .toLowerCase()
          .includes(query);
      })
      .slice(0, 100);
  }, [availableGroups, groupSearch, memberOfByGroupId]);

  useEffect(() => {
    if (!open || !user) {
      setDisplayName("");
      setIsActive(true);
      setRoleDraft([]);
      setGroupSearch("");
      setSelectedGroupId("");
      setError(null);
      setIssuedKey(null);
      setCopyStatus("idle");
      return;
    }

    setDisplayName(user.display_name ?? "");
    setIsActive(Boolean(user.is_active));
  }, [open, user]);

  useEffect(() => {
    if (!open) return;
    setRoleDraft(currentRoleIds);
  }, [currentRoleIds, open]);

  useEffect(() => {
    if (!selectedGroupId) {
      return;
    }
    if (!filteredGroupOptions.some((group) => group.id === selectedGroupId)) {
      setSelectedGroupId("");
    }
  }, [filteredGroupOptions, selectedGroupId]);

  const disabled = !canManage || isMutating;
  const selectedGroup = selectedGroupId
    ? availableGroups.find((group) => group.id === selectedGroupId)
    : null;
  const selectedGroupIsReadOnly =
    selectedGroup?.source === "idp" || selectedGroup?.membership_mode === "dynamic";
  const addMembershipState = resolveAccessActionState({
    isDisabled:
      !canManageUserMemberOf ||
      !canReadUserMemberOf ||
      !selectedGroupId ||
      selectedGroupIsReadOnly ||
      addMemberOfMutation.isPending,
    reasonCode: !canManageUserMemberOf || !canReadUserMemberOf
      ? "perm_missing"
      : selectedGroup?.source === "idp"
        ? "provider_managed"
        : selectedGroup?.membership_mode === "dynamic"
          ? "dynamic_membership"
          : !selectedGroupId
            ? "invalid_selection"
            : null,
    reasonText: !canReadUserMemberOf
      ? "You need users and group-membership read access to view and manage memberships."
      : !canManageUserMemberOf
        ? "You need user and group-membership manage permissions to add memberships."
        : undefined,
  });

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title={user?.display_name || user?.email || "User"}
      description="Manage profile, global roles, and API keys."
      widthClassName="w-full max-w-2xl"
    >
      {!user ? (
        <Alert tone="warning">This user could not be found.</Alert>
      ) : (
        <div className="space-y-6">
          {error ? <Alert tone="danger">{error}</Alert> : null}
          {!canManage ? (
            <Alert tone="info">Read-only view. You need user management permission to make changes.</Alert>
          ) : null}

          {issuedKey ? (
            <div className="space-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3">
              <p className="text-sm font-semibold text-warning-foreground">Copy this API key secret now</p>
              <p className="text-xs text-warning-foreground/90">
                For security, this secret is shown only once and cannot be retrieved again.
              </p>
              <div className="flex flex-col gap-2 rounded-md border border-warning/40 bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
                <code className="break-all text-xs text-foreground">{issuedKey.secret}</code>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(issuedKey.secret);
                        setCopyStatus("copied");
                      } catch {
                        setCopyStatus("failed");
                      }
                    }}
                  >
                    Copy
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setIssuedKey(null)}>
                    Dismiss
                  </Button>
                </div>
              </div>
              {copyStatus === "copied" ? <p className="text-xs text-success">Secret copied to clipboard.</p> : null}
              {copyStatus === "failed" ? <p className="text-xs text-destructive">Unable to copy. Copy manually.</p> : null}
            </div>
          ) : null}

          <SettingsSection title="Profile" description="Update account details and activation status.">
            <FormField label="Email">
              <Input value={user.email} disabled />
            </FormField>
            <FormField label="Display name">
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                disabled={disabled}
              />
            </FormField>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={isActive}
                onChange={(event) => setIsActive(event.target.checked)}
                disabled={disabled}
              />
              Active user
            </label>
            <div className="flex justify-end gap-2">
              {user.id !== currentUserId && user.is_active ? (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={disabled}
                  onClick={async () => {
                    setError(null);
                    try {
                      await onDeactivate();
                    } catch (deactivateError) {
                      const mapped = mapUiError(deactivateError, { fallback: "Unable to deactivate user." });
                      setError(mapped.message);
                    }
                  }}
                >
                  Deactivate
                </Button>
              ) : null}
              <Button
                type="button"
                disabled={disabled}
                onClick={async () => {
                  setError(null);
                  try {
                    await onUpdateProfile({
                      display_name: displayName.trim() || null,
                      is_active: isActive,
                    });
                  } catch (saveError) {
                    const mapped = mapUiError(saveError, { fallback: "Unable to update user." });
                    setError(mapped.message);
                  }
                }}
              >
                Save profile
              </Button>
            </div>
          </SettingsSection>

          <SettingsSection title="Global roles" description="Assign global roles to this user.">
            {roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No global roles available.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {roles.map((role) => (
                  <label key={role.id} className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border"
                      checked={roleDraft.includes(role.id)}
                      onChange={(event) =>
                        setRoleDraft((current) =>
                          event.target.checked
                            ? Array.from(new Set([...current, role.id]))
                            : current.filter((id) => id !== role.id),
                        )
                      }
                      disabled={disabled}
                    />
                    <span>{role.name}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex justify-end">
              <Button
                type="button"
                disabled={disabled || userRolesQuery.isLoading}
                onClick={async () => {
                  setError(null);
                  try {
                    await onSaveRoles(roleDraft, currentRoleIds);
                    await userRolesQuery.refetch();
                  } catch (saveError) {
                    const mapped = mapUiError(saveError, { fallback: "Unable to update roles." });
                    setError(mapped.message);
                  }
                }}
              >
                Save roles
              </Button>
            </div>
          </SettingsSection>

          <SettingsSection title="Groups" description="Manage direct group memberships for this user.">
            {!canReadUserMemberOf ? (
              <p className="text-sm text-muted-foreground">
                You need users and group-membership read access to view memberships.
              </p>
            ) : (
              <div className="space-y-3">
                <div className="rounded-lg border border-border p-3">
                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
                    <FormField label="Search groups">
                      <Input
                        value={groupSearch}
                        onChange={(event) => setGroupSearch(event.target.value)}
                        placeholder="Search groups"
                        disabled={!canReadUserMemberOf || addMemberOfMutation.isPending}
                      />
                    </FormField>
                    <FormField label="Group">
                      <Select
                        value={selectedGroupId}
                        onValueChange={setSelectedGroupId}
                        disabled={!canReadUserMemberOf || addMemberOfMutation.isPending}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a group" />
                        </SelectTrigger>
                        <SelectContent>
                          {filteredGroupOptions.length === 0 ? (
                            <SelectItem value="__none__" disabled>
                              No eligible groups
                            </SelectItem>
                          ) : (
                            filteredGroupOptions.map((group) => (
                              <SelectItem key={group.id} value={group.id}>
                                {group.display_name}
                              </SelectItem>
                            ))
                          )}
                        </SelectContent>
                      </Select>
                    </FormField>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        disabled={addMembershipState.disabled}
                        onClick={async () => {
                          if (!selectedGroupId) {
                            return;
                          }
                          setError(null);
                          try {
                            await addMemberOfMutation.mutateAsync({ groupId: selectedGroupId });
                            setSelectedGroupId("");
                          } catch (membershipError) {
                            const mapped = mapUiError(membershipError, {
                              fallback: "Unable to add group membership.",
                              statusMessages: {
                                409: "This group is provider-managed and cannot be edited in ADE.",
                              },
                            });
                            setError(mapped.message);
                          }
                        }}
                      >
                        Add membership
                      </Button>
                    </div>
                  </div>
                  {addMembershipState.reasonText ? (
                    <p className="mt-2 text-xs text-muted-foreground">{addMembershipState.reasonText}</p>
                  ) : null}
                </div>

                {userMemberOfQuery.isLoading ? (
                  <p className="text-sm text-muted-foreground">Loading memberships...</p>
                ) : memberOfItems.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No direct group memberships.</p>
                ) : (
                  <div className="space-y-2">
                    {memberOfItems.map((membership) => {
                      const removeState = resolveAccessActionState({
                        isDisabled:
                          !membership.is_member ||
                          !canManageUserMemberOf ||
                          membership.source === "idp" ||
                          membership.membership_mode === "dynamic" ||
                          removeMemberOfMutation.isPending,
                        reasonCode: !canManageUserMemberOf
                          ? "perm_missing"
                          : membership.source === "idp"
                            ? "provider_managed"
                            : membership.membership_mode === "dynamic"
                              ? "dynamic_membership"
                              : !membership.is_member
                                ? "conflict_state"
                                : null,
                        reasonText: !membership.is_member
                          ? "Only direct memberships can be removed here."
                          : undefined,
                      });
                      return (
                        <div
                          key={membership.group_id}
                          className="flex flex-col gap-2 rounded-lg border border-border px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="space-y-1">
                            <p className="text-sm font-semibold text-foreground">{membership.display_name}</p>
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <Badge variant="outline">{membership.slug}</Badge>
                              {membership.is_member ? <Badge variant="secondary">Member</Badge> : null}
                              {membership.is_owner ? <Badge variant="secondary">Owner</Badge> : null}
                              <Badge
                                variant={
                                  membership.source === "idp" || membership.membership_mode === "dynamic"
                                    ? "outline"
                                    : "secondary"
                                }
                              >
                                {membership.source === "idp"
                                  ? "Provider-managed"
                                  : membership.membership_mode === "dynamic"
                                    ? "Dynamic"
                                    : "Internal"}
                              </Badge>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center justify-end gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => onOpenGroup(membership.group_id)}
                            >
                              Open group
                            </Button>
                            <DisabledActionButton
                              label="Remove"
                              disabled={removeState.disabled}
                              reason={removeState.reasonText}
                              tone="danger"
                              onClick={async () => {
                                setError(null);
                                try {
                                  await removeMemberOfMutation.mutateAsync({
                                    groupId: membership.group_id,
                                  });
                                } catch (removeError) {
                                  const mapped = mapUiError(removeError, {
                                    fallback: "Unable to remove group membership.",
                                    statusMessages: {
                                      409: "This group is provider-managed and cannot be edited in ADE.",
                                    },
                                  });
                                  setError(mapped.message);
                                }
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </SettingsSection>

          <SettingsSection title="API keys" description="Create and revoke API keys for this user.">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_9rem_auto] md:items-end">
              <FormField label="Name">
                <Input
                  value={apiKeyName}
                  onChange={(event) => setApiKeyName(event.target.value)}
                  placeholder="Optional"
                  disabled={disabled}
                />
              </FormField>
              <FormField label="Expires (days)" error={apiKeyExpiryError}>
                <Input
                  value={apiKeyExpiry}
                  onChange={(event) => setApiKeyExpiry(event.target.value)}
                  placeholder="Optional"
                  inputMode="numeric"
                  disabled={disabled}
                />
              </FormField>
              <Button
                type="button"
                disabled={disabled || Boolean(apiKeyExpiryError)}
                onClick={async () => {
                  setError(null);
                  if (apiKeyExpiryError) {
                    return;
                  }
                  try {
                    const created = await onCreateApiKey({
                      name: apiKeyName.trim(),
                      expiresInDays: hasExpiryInput ? parsedExpiry : null,
                    });
                    setApiKeyName("");
                    setApiKeyExpiry("");
                    setCopyStatus("idle");
                    setIssuedKey(created ? { id: created.id, prefix: created.prefix, secret: created.secret } : null);
                    await userApiKeysQuery.refetch();
                  } catch (createError) {
                    const mapped = mapUiError(createError, { fallback: "Unable to create API key." });
                    setError(mapped.message);
                  }
                }}
              >
                Create key
              </Button>
            </div>

            {userApiKeysQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading API keys...</p>
            ) : (
              <ResponsiveAdminTable
                items={userApiKeysQuery.data?.items ?? []}
                getItemKey={(key) => key.id}
                mobileListLabel="User API keys"
                desktopTable={
                  <div className="overflow-hidden rounded-xl border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Prefix</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(userApiKeysQuery.data?.items ?? []).map((key) => {
                          const isRevoked = Boolean(key.revoked_at);
                          return (
                            <TableRow key={key.id}>
                              <TableCell>{key.name ?? "(unnamed)"}</TableCell>
                              <TableCell className="font-mono text-xs">{key.prefix}</TableCell>
                              <TableCell>{isRevoked ? "Revoked" : "Active"}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  disabled={disabled || isRevoked}
                                  onClick={async () => {
                                    setError(null);
                                    try {
                                      await onRevokeApiKey(key);
                                      await userApiKeysQuery.refetch();
                                    } catch (revokeError) {
                                      const mapped = mapUiError(revokeError, {
                                        fallback: "Unable to revoke API key.",
                                        statusMessages: {
                                          412: "This key changed while you were viewing it. Refresh and retry.",
                                        },
                                      });
                                      setError(mapped.message);
                                    }
                                  }}
                                >
                                  Revoke
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                }
                mobileCard={(key) => {
                  const isRevoked = Boolean(key.revoked_at);
                  return (
                    <>
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-foreground">{key.name ?? "(unnamed)"}</p>
                        <p className="font-mono text-[11px] text-muted-foreground">{key.prefix}</p>
                      </div>
                      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                        <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                        <dd>{isRevoked ? "Revoked" : "Active"}</dd>
                      </dl>
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={disabled || isRevoked}
                          onClick={async () => {
                            setError(null);
                            try {
                              await onRevokeApiKey(key);
                              await userApiKeysQuery.refetch();
                            } catch (revokeError) {
                              const mapped = mapUiError(revokeError, {
                                fallback: "Unable to revoke API key.",
                                statusMessages: {
                                  412: "This key changed while you were viewing it. Refresh and retry.",
                                },
                              });
                              setError(mapped.message);
                            }
                          }}
                        >
                          Revoke
                        </Button>
                      </div>
                    </>
                  );
                }}
              />
            )}
          </SettingsSection>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
    </SettingsDrawer>
  );
}

function DisabledActionButton({
  label,
  disabled,
  reason,
  tone = "default",
  onClick,
}: {
  readonly label: string;
  readonly disabled: boolean;
  readonly reason: string | null;
  readonly tone?: "default" | "danger";
  readonly onClick: () => void | Promise<void>;
}) {
  const button = (
    <Button
      type="button"
      size="sm"
      variant={tone === "danger" ? "destructive" : "ghost"}
      disabled={disabled}
      onClick={() => {
        void onClick();
      }}
    >
      {label}
    </Button>
  );

  if (!disabled || !reason) {
    return button;
  }

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="top">{reason}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
