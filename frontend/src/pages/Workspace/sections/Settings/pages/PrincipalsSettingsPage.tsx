import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listGroups, type Group } from "@/api/groups/api";
import { useUsersQuery } from "@/hooks/users/useUsersQuery";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { AccessCommandBar, AssignmentChips, PrincipalIdentityCell } from "@/pages/SharedAccess/components";
import { ResponsiveAdminTable } from "@/pages/OrganizationSettings/components/ResponsiveAdminTable";
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
import { SettingsDrawer } from "../components/SettingsDrawer";
import { SettingsSection } from "../components/SettingsSection";
import { useSettingsSection } from "../sectionContext";
import {
  useAddWorkspacePrincipalMutation,
  useRemoveWorkspacePrincipalMutation,
  useUpdateWorkspacePrincipalRolesMutation,
  useWorkspacePrincipalsQuery,
} from "../hooks/useWorkspacePrincipals";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { RoleDefinition, WorkspacePrincipal, WorkspacePrincipalType } from "@/types/workspaces";
import type { UserSummary } from "@/api/users/api";

const SIMPLE_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Feedback = { tone: "success" | "danger"; message: string };

type PrincipalWithSource = WorkspacePrincipal & {
  readonly sourceLabel: "internal" | "idp" | "direct";
};

export function PrincipalsSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const { params } = useSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();

  const canManagePrincipals = hasPermission("workspace.members.manage");
  const canReadPrincipals = hasPermission("workspace.members.read") || canManagePrincipals;

  const principalsQuery = useWorkspacePrincipalsQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const groupsQuery = useQuery({
    queryKey: ["groups", "all", "workspace-principals"],
    queryFn: ({ signal }) => listGroups({ signal }),
    staleTime: 30_000,
    enabled: canReadPrincipals,
  });

  const addPrincipal = useAddWorkspacePrincipalMutation(workspace.id);
  const updatePrincipalRoles = useUpdateWorkspacePrincipalRolesMutation(workspace.id);
  const removePrincipal = useRemoveWorkspacePrincipalMutation(workspace.id);

  const [searchValue, setSearchValue] = useState("");
  const [principalFilter, setPrincipalFilter] = useState<"all" | WorkspacePrincipalType>("all");
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const basePath = `/workspaces/${workspace.id}/settings/access/principals`;
  const suffix = `${location.search}${location.hash}`;

  const routeMode = params[0] ?? null;
  const selectedType = params[0] === "user" || params[0] === "group" ? params[0] : null;
  const selectedPrincipalId = selectedType && params[1] ? decodeURIComponent(params[1]) : null;
  const isAddOpen = routeMode === "new";

  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openAddDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openPrincipalDrawer = (principal: WorkspacePrincipal) =>
    navigate(
      `${basePath}/${principal.principal_type}/${encodeURIComponent(principal.principal_id)}${suffix}`,
    );

  const availableRoles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? []).slice().sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const groupsById = useMemo(() => {
    const map = new Map<string, Group>();
    for (const group of groupsQuery.data?.items ?? []) {
      map.set(group.id, group);
    }
    return map;
  }, [groupsQuery.data?.items]);

  const principals = useMemo<PrincipalWithSource[]>(() => {
    return principalsQuery.principals.map((principal) => {
      if (principal.principal_type === "group") {
        const group = groupsById.get(principal.principal_id);
        return {
          ...principal,
          sourceLabel: group?.source === "idp" ? "idp" : "internal",
        };
      }
      return {
        ...principal,
        sourceLabel: "direct",
      };
    });
  }, [groupsById, principalsQuery.principals]);

  const filteredPrincipals = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    return principals.filter((principal) => {
      if (principalFilter !== "all" && principal.principal_type !== principalFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = [
        principal.principal_display_name,
        principal.principal_email,
        principal.principal_slug,
        principal.principal_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [principalFilter, principals, searchValue]);

  const selectedPrincipal = useMemo(
    () =>
      principals.find(
        (principal) =>
          principal.principal_type === selectedType && principal.principal_id === selectedPrincipalId,
      ),
    [principals, selectedPrincipalId, selectedType],
  );

  const userPrincipalIds = useMemo(
    () =>
      new Set(
        principals
          .filter((principal) => principal.principal_type === "user")
          .map((principal) => principal.principal_id),
      ),
    [principals],
  );

  const groupPrincipalIds = useMemo(
    () =>
      new Set(
        principals
          .filter((principal) => principal.principal_type === "group")
          .map((principal) => principal.principal_id),
      ),
    [principals],
  );

  if (!canReadPrincipals) {
    return <Alert tone="danger">You do not have permission to access workspace principals.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {principalsQuery.isError ? (
        <Alert tone="danger">
          {principalsQuery.error instanceof Error
            ? principalsQuery.error.message
            : "Unable to load workspace principals."}
        </Alert>
      ) : null}
      {rolesQuery.isError ? (
        <Alert tone="warning">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}

      <SettingsSection
        title="Workspace principals"
        description={
          principalsQuery.isLoading
            ? "Loading principals..."
            : `${filteredPrincipals.length} principal${filteredPrincipals.length === 1 ? "" : "s"}`
        }
        actions={
          canManagePrincipals ? (
            <Button type="button" size="sm" onClick={openAddDrawer}>
              Add principal
            </Button>
          ) : null
        }
      >
        <AccessCommandBar
          searchValue={searchValue}
          onSearchValueChange={setSearchValue}
          searchPlaceholder="Search principals"
          searchAriaLabel="Search principals"
          controls={
            <Select value={principalFilter} onValueChange={(value) => setPrincipalFilter(value as "all" | WorkspacePrincipalType)}>
              <SelectTrigger className="w-full min-w-36 sm:w-44">
                <SelectValue placeholder="Filter type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="user">Users</SelectItem>
                <SelectItem value="group">Groups</SelectItem>
              </SelectContent>
            </Select>
          }
        />

        {principalsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading principals...</p>
        ) : filteredPrincipals.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No principals match your current filters.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={filteredPrincipals}
            getItemKey={(principal) => `${principal.principal_type}:${principal.principal_id}`}
            mobileListLabel="Workspace principals"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Principal</TableHead>
                      <TableHead className="px-4">Type</TableHead>
                      <TableHead className="px-4">Roles</TableHead>
                      <TableHead className="px-4">Source</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPrincipals.map((principal) => (
                      <TableRow key={`${principal.principal_type}:${principal.principal_id}`}>
                        <TableCell className="px-4 py-3">
                          <PrincipalIdentityCell
                            principalType={principal.principal_type}
                            title={
                              principal.principal_display_name ??
                              principal.principal_email ??
                              principal.principal_slug ??
                              principal.principal_id
                            }
                            subtitle={principal.principal_email ?? principal.principal_slug ?? principal.principal_id}
                          />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant="outline" className="text-xs capitalize">
                            {principal.principal_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <AssignmentChips assignments={principal.role_slugs} emptyLabel="No roles" />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={principal.sourceLabel === "idp" ? "outline" : "secondary"}>
                            {principal.sourceLabel === "idp"
                              ? "Provider-managed"
                              : principal.sourceLabel === "internal"
                                ? "Internal"
                                : "Direct"}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={!canManagePrincipals}
                            onClick={() => openPrincipalDrawer(principal)}
                          >
                            Manage
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(principal) => (
              <>
                <PrincipalIdentityCell
                  principalType={principal.principal_type}
                  title={
                    principal.principal_display_name ??
                    principal.principal_email ??
                    principal.principal_slug ??
                    principal.principal_id
                  }
                  subtitle={principal.principal_email ?? principal.principal_slug ?? principal.principal_id}
                />
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Type</dt>
                  <dd>
                    <Badge variant="outline" className="capitalize">
                      {principal.principal_type}
                    </Badge>
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Roles</dt>
                  <dd>
                    <AssignmentChips assignments={principal.role_slugs} emptyLabel="No roles" />
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Source</dt>
                  <dd>
                    <Badge variant={principal.sourceLabel === "idp" ? "outline" : "secondary"}>
                      {principal.sourceLabel === "idp"
                        ? "Provider-managed"
                        : principal.sourceLabel === "internal"
                          ? "Internal"
                          : "Direct"}
                    </Badge>
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={!canManagePrincipals}
                    onClick={() => openPrincipalDrawer(principal)}
                  >
                    Manage
                  </Button>
                </div>
              </>
            )}
          />
        )}

        {!canManagePrincipals ? (
          <Alert tone="info">You can view principals, but you need manage permission to make changes.</Alert>
        ) : null}
      </SettingsSection>

      <AddPrincipalDrawer
        open={isAddOpen && canManagePrincipals}
        onClose={closeDrawer}
        availableRoles={availableRoles}
        existingUserPrincipalIds={userPrincipalIds}
        existingGroupPrincipalIds={groupPrincipalIds}
        availableGroups={groupsQuery.data?.items ?? []}
        onAdd={async (input) => {
          setFeedback(null);
          await addPrincipal.mutateAsync(input);
          setFeedback({ tone: "success", message: "Principal added." });
          closeDrawer();
        }}
        isSubmitting={addPrincipal.isPending}
      />

      <PrincipalDrawer
        open={Boolean(selectedType && selectedPrincipalId) && canManagePrincipals}
        principal={selectedPrincipal}
        availableRoles={availableRoles}
        onClose={closeDrawer}
        onSaveRoles={async (roleIds) => {
          if (!selectedPrincipal) {
            return;
          }
          setFeedback(null);
          await updatePrincipalRoles.mutateAsync({
            principalType: selectedPrincipal.principal_type,
            principalId: selectedPrincipal.principal_id,
            roleIds,
          });
          setFeedback({ tone: "success", message: "Principal roles updated." });
          closeDrawer();
        }}
        onRemove={async () => {
          if (!selectedPrincipal) {
            return;
          }
          setFeedback(null);
          await removePrincipal.mutateAsync({
            principalType: selectedPrincipal.principal_type,
            principalId: selectedPrincipal.principal_id,
          });
          setFeedback({ tone: "success", message: "Principal removed." });
          closeDrawer();
        }}
        isSaving={updatePrincipalRoles.isPending}
        isRemoving={removePrincipal.isPending}
      />
    </div>
  );
}

interface AddPrincipalInput {
  readonly principalType: WorkspacePrincipalType;
  readonly principalId?: string;
  readonly user?: UserSummary;
  readonly invitedEmail?: string;
  readonly displayName?: string;
  readonly roleIds: readonly string[];
}

interface AddPrincipalDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly availableRoles: readonly RoleDefinition[];
  readonly existingUserPrincipalIds: ReadonlySet<string>;
  readonly existingGroupPrincipalIds: ReadonlySet<string>;
  readonly availableGroups: readonly Group[];
  readonly onAdd: (input: AddPrincipalInput) => Promise<void>;
  readonly isSubmitting: boolean;
}

function AddPrincipalDrawer({
  open,
  onClose,
  availableRoles,
  existingUserPrincipalIds,
  existingGroupPrincipalIds,
  availableGroups,
  onAdd,
  isSubmitting,
}: AddPrincipalDrawerProps) {
  const [mode, setMode] = useState<"existing_user" | "invite_user" | "existing_group">("existing_user");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [groupSearch, setGroupSearch] = useState("");
  const [debouncedUserSearch, setDebouncedUserSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedUserSearch(userSearch.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [userSearch]);

  useEffect(() => {
    if (!open) {
      setMode("existing_user");
      setSelectedUserId("");
      setSelectedGroupId("");
      setInviteEmail("");
      setInviteDisplayName("");
      setSelectedRoleIds([]);
      setUserSearch("");
      setGroupSearch("");
      setError(null);
    }
  }, [open]);

  const usersQuery = useUsersQuery({
    enabled: open && mode === "existing_user",
    search: debouncedUserSearch,
    pageSize: 50,
  });

  const availableUsers = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return usersQuery.users
      .filter((user) => !existingUserPrincipalIds.has(user.id))
      .slice()
      .sort((a, b) => {
        const labelA = a.display_name ?? a.email;
        const labelB = b.display_name ?? b.email;
        return collator.compare(labelA, labelB);
      });
  }, [existingUserPrincipalIds, usersQuery.users]);

  const filteredGroups = useMemo(() => {
    const query = groupSearch.trim().toLowerCase();
    return availableGroups
      .filter((group) => !existingGroupPrincipalIds.has(group.id))
      .filter((group) => {
        if (!query) {
          return true;
        }
        const haystack = `${group.display_name} ${group.slug}`.toLowerCase();
        return haystack.includes(query);
      })
      .sort((a, b) => a.display_name.localeCompare(b.display_name));
  }, [availableGroups, existingGroupPrincipalIds, groupSearch]);

  const selectedUser = availableUsers.find((user) => user.id === selectedUserId);
  const selectedGroup = filteredGroups.find((group) => group.id === selectedGroupId);

  const canSubmit = selectedRoleIds.length > 0 && !isSubmitting;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (selectedRoleIds.length === 0) {
      setError("Select at least one workspace role.");
      return;
    }

    try {
      if (mode === "existing_user") {
        if (!selectedUser) {
          setError("Select an existing user.");
          return;
        }
        await onAdd({
          principalType: "user",
          user: selectedUser,
          roleIds: selectedRoleIds,
        });
        return;
      }

      if (mode === "invite_user") {
        if (!inviteEmail.trim() || !SIMPLE_EMAIL_PATTERN.test(inviteEmail.trim())) {
          setError("Enter a valid invitation email.");
          return;
        }
        await onAdd({
          principalType: "user",
          invitedEmail: inviteEmail.trim().toLowerCase(),
          displayName: inviteDisplayName.trim() || undefined,
          roleIds: selectedRoleIds,
        });
        return;
      }

      if (!selectedGroup) {
        setError("Select an existing group.");
        return;
      }
      await onAdd({
        principalType: "group",
        principalId: selectedGroup.id,
        roleIds: selectedRoleIds,
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to add principal.");
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title="Add principal"
      description="Add an existing user, invite by email, or add an existing group with initial role assignments."
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {error ? <Alert tone="danger">{error}</Alert> : null}

        <FormField label="Principal type" required>
          <Select
            value={mode}
            onValueChange={(value) => setMode(value as "existing_user" | "invite_user" | "existing_group")}
            disabled={isSubmitting}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select principal type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="existing_user">Existing user</SelectItem>
              <SelectItem value="invite_user">Invite by email</SelectItem>
              <SelectItem value="existing_group">Existing group</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        {mode === "existing_user" ? (
          <>
            <FormField label="Search directory" hint="Enter at least two characters to search by name or email.">
              <Input
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
                placeholder="Search users"
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="User" required>
              <Select
                value={selectedUserId || undefined}
                onValueChange={setSelectedUserId}
                disabled={isSubmitting}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>
                  {availableUsers.map((user) => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </>
        ) : null}

        {mode === "invite_user" ? (
          <div className="space-y-3 rounded-lg border border-border bg-background p-3">
            <FormField label="Email" required>
              <Input
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                placeholder="user@example.com"
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Display name">
              <Input
                value={inviteDisplayName}
                onChange={(event) => setInviteDisplayName(event.target.value)}
                placeholder="Optional"
                disabled={isSubmitting}
              />
            </FormField>
          </div>
        ) : null}

        {mode === "existing_group" ? (
          <>
            <FormField label="Search groups">
              <Input
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
                placeholder="Search groups"
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Group" required>
              <Select
                value={selectedGroupId || undefined}
                onValueChange={setSelectedGroupId}
                disabled={isSubmitting}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a group" />
                </SelectTrigger>
                <SelectContent>
                  {filteredGroups.map((group) => (
                    <SelectItem key={group.id} value={group.id}>
                      {group.display_name} ({group.source})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </>
        ) : null}

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold text-foreground">Workspace roles</legend>
          <p className="text-xs text-muted-foreground">Assign at least one role to grant access.</p>
          <div className="flex flex-wrap gap-2">
            {availableRoles.length === 0 ? (
              <p className="text-xs text-muted-foreground">No workspace roles available.</p>
            ) : (
              availableRoles.map((role) => (
                <label
                  key={role.id}
                  className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border"
                    checked={selectedRoleIds.includes(role.id)}
                    onChange={(event) =>
                      setSelectedRoleIds((current) =>
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

        {usersQuery.hasNextPage && mode === "existing_user" ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => usersQuery.fetchNextPage()}
            disabled={usersQuery.isFetchingNextPage}
          >
            {usersQuery.isFetchingNextPage ? "Loading more users..." : "Load more users"}
          </Button>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {isSubmitting ? "Adding..." : "Add principal"}
          </Button>
        </div>
      </form>
    </SettingsDrawer>
  );
}

interface PrincipalDrawerProps {
  readonly open: boolean;
  readonly principal?: PrincipalWithSource;
  readonly availableRoles: readonly RoleDefinition[];
  readonly onClose: () => void;
  readonly onSaveRoles: (roleIds: string[]) => Promise<void>;
  readonly onRemove: () => Promise<void>;
  readonly isSaving: boolean;
  readonly isRemoving: boolean;
}

function PrincipalDrawer({
  open,
  principal,
  availableRoles,
  onClose,
  onSaveRoles,
  onRemove,
  isSaving,
  isRemoving,
}: PrincipalDrawerProps) {
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  useEffect(() => {
    if (!open || !principal) {
      setRoleDraft([]);
      setError(null);
      setConfirmRemove(false);
      return;
    }
    setRoleDraft(principal.role_ids);
    setError(null);
    setConfirmRemove(false);
  }, [open, principal]);

  const principalLabel =
    principal?.principal_display_name ??
    principal?.principal_email ??
    principal?.principal_slug ??
    principal?.principal_id ??
    "Principal";

  return (
    <>
      <SettingsDrawer
        open={open}
        onClose={onClose}
        title={principalLabel}
        description={principal ? "Update role assignments or remove this principal from the workspace." : undefined}
      >
        {!principal ? (
          <Alert tone="warning">This principal could not be found.</Alert>
        ) : (
          <div className="space-y-4">
            {error ? <Alert tone="danger">{error}</Alert> : null}

            <div className="rounded-lg border border-border bg-background p-3">
              <PrincipalIdentityCell
                principalType={principal.principal_type}
                title={principalLabel}
                subtitle={
                  principal.principal_email ?? principal.principal_slug ?? principal.principal_id
                }
              />
              {principal.principal_type === "group" && principal.sourceLabel === "idp" ? (
                <Alert tone="info" className="mt-3">
                  Group membership is managed by your identity provider. Update group members in the provider.
                </Alert>
              ) : null}
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-semibold text-foreground">Workspace roles</legend>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No workspace roles available.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                    >
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
                        disabled={isSaving}
                      />
                      <span>{role.name}</span>
                    </label>
                  ))
                )}
              </div>
              {roleDraft.length > 0 ? (
                <p className="text-xs text-muted-foreground">{roleDraft.length} role(s) selected.</p>
              ) : null}
            </fieldset>

            <div className="mt-4 flex items-center justify-between gap-2">
              <Button type="button" variant="ghost" onClick={onClose} disabled={isSaving || isRemoving}>
                Close
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmRemove(true)}
                  disabled={isRemoving}
                >
                  {isRemoving ? "Removing..." : "Remove"}
                </Button>
                <Button
                  type="button"
                  disabled={isSaving}
                  onClick={async () => {
                    setError(null);
                    try {
                      await onSaveRoles(roleDraft);
                    } catch (saveError) {
                      setError(saveError instanceof Error ? saveError.message : "Unable to save roles.");
                    }
                  }}
                >
                  {isSaving ? "Saving..." : "Save changes"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </SettingsDrawer>

      <ConfirmDialog
        open={confirmRemove}
        title="Remove principal?"
        description={`Remove ${principalLabel} from this workspace.`}
        confirmLabel="Remove principal"
        tone="danger"
        onCancel={() => setConfirmRemove(false)}
        onConfirm={async () => {
          setError(null);
          try {
            await onRemove();
            setConfirmRemove(false);
          } catch (removeError) {
            setError(removeError instanceof Error ? removeError.message : "Unable to remove principal.");
          }
        }}
        isConfirming={isRemoving}
      />
    </>
  );
}
