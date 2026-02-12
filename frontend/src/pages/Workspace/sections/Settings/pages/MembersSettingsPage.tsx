import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listWorkspaceRoleAssignmentsRaw } from "@/api/workspaces/api";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useUsersQuery } from "@/hooks/users/useUsersQuery";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { useSettingsSection } from "../sectionContext";
import {
  useAddWorkspaceMemberMutation,
  useRemoveWorkspaceMemberMutation,
  useUpdateWorkspaceMemberRolesMutation,
  useWorkspaceMembersQuery,
} from "../hooks/useWorkspaceMembers";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { RoleDefinition, WorkspaceMember } from "@/types/workspaces";
import type { UserSummary } from "@/api/users/api";
import { Alert } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { SettingsSection } from "../components/SettingsSection";
import { getInitials } from "@/lib/format";

type MemberWithUser = WorkspaceMember & { user?: UserSummary };

export function MembersSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const { params } = useSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageMembers = hasPermission("workspace.members.manage");

  const membersQuery = useWorkspaceMembersQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const groupAssignmentsQuery = useQuery({
    queryKey: ["workspaces", workspace.id, "group-assignments"],
    queryFn: () => listWorkspaceRoleAssignmentsRaw(workspace.id),
    staleTime: 15_000,
    enabled: workspace.id.length > 0,
  });

  const addMember = useAddWorkspaceMemberMutation(workspace.id);
  const updateMemberRoles = useUpdateWorkspaceMemberRolesMutation(workspace.id);
  const removeMember = useRemoveWorkspaceMemberMutation(workspace.id);

  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const members = useMemo<MemberWithUser[]>(() => {
    const list = membersQuery.members as MemberWithUser[];
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return [...list].sort((a, b) => {
      const nameA = a.user?.display_name ?? a.user?.email ?? a.user_id;
      const nameB = b.user?.display_name ?? b.user?.email ?? b.user_id;
      return collator.compare(nameA ?? "", nameB ?? "");
    });
  }, [membersQuery.members]);

  const memberIds = useMemo(() => new Set(members.map((member) => member.user_id)), [members]);
  const memberCount = membersQuery.total ?? members.length;
  const hasMoreMembers = Boolean(membersQuery.hasNextPage);
  const isMembersLoading = membersQuery.isLoading;
  const isMembersFetchingMore = membersQuery.isFetchingNextPage;

  const availableRoles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? []).slice().sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const selectedParam = params[0];
  const isAddMemberOpen = selectedParam === "new";
  const selectedMemberId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedMember = members.find((member) => member.user_id === selectedMemberId);
  const [activeTab, setActiveTab] = useState<"users" | "groups">("users");

  const basePath = `/workspaces/${workspace.id}/settings/access/principals`;
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openAddMemberDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openMemberDrawer = (userId: string) =>
    navigate(`${basePath}/${encodeURIComponent(userId)}${suffix}`);

  const handleAddMember = async ({
    user,
    invitedEmail,
    displayName,
    roleIds,
  }: {
    user?: UserSummary;
    invitedEmail?: string;
    displayName?: string;
    roleIds: string[];
  }) => {
    setFeedbackMessage(null);
    await addMember.mutateAsync({ user, invitedEmail, displayName, roleIds });
    setFeedbackMessage(
      invitedEmail
        ? { tone: "success", message: `Invitation sent to ${invitedEmail}.` }
        : { tone: "success", message: `${user?.display_name ?? user?.email ?? "User"} added to the workspace.` },
    );
    closeDrawer();
  };

  const handleUpdateRoles = async (userId: string, roleIds: string[]) => {
    setFeedbackMessage(null);
    await updateMemberRoles.mutateAsync({ userId, roleIds });
    setFeedbackMessage({ tone: "success", message: "Principal roles updated." });
    closeDrawer();
  };

  const handleRemoveMember = async (member: MemberWithUser) => {
    setFeedbackMessage(null);
    await removeMember.mutateAsync(member.user_id);
    setFeedbackMessage({ tone: "success", message: "Principal removed." });
    closeDrawer();
  };

  const groupedRoleAssignments = useMemo(() => {
    const byGroup = new Map<string, { label: string; slug: string | null; roles: string[] }>();
    for (const assignment of groupAssignmentsQuery.data ?? []) {
      if (assignment.principal_type !== "group") {
        continue;
      }
      const existing = byGroup.get(assignment.principal_id);
      if (!existing) {
        byGroup.set(assignment.principal_id, {
          label: assignment.principal_display_name ?? assignment.principal_id,
          slug: assignment.principal_slug ?? null,
          roles: [assignment.role_slug],
        });
        continue;
      }
      if (!existing.roles.includes(assignment.role_slug)) {
        existing.roles.push(assignment.role_slug);
      }
    }
    return Array.from(byGroup.entries()).map(([groupId, value]) => ({
      groupId,
      label: value.label,
      slug: value.slug,
      roles: value.roles.slice().sort((a, b) => a.localeCompare(b)),
    }));
  }, [groupAssignmentsQuery.data]);

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {membersQuery.isError ? (
        <Alert tone="danger">
          {membersQuery.error instanceof Error ? membersQuery.error.message : "Unable to load workspace principals."}
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
          isMembersLoading ? "Loading principals…" : `${memberCount} principal${memberCount === 1 ? "" : "s"}`
        }
        actions={
          canManageMembers ? (
            <Button type="button" size="sm" onClick={openAddMemberDrawer}>
              Add principal
            </Button>
          ) : null
        }
      >
        <TabsRoot value={activeTab} onValueChange={(value) => setActiveTab(value as "users" | "groups")}>
          <TabsList className="mb-3 inline-flex gap-1 rounded-full border border-border bg-background p-1">
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="groups">Groups</TabsTrigger>
          </TabsList>

          <TabsContent value="users" className="space-y-4">
            {isMembersLoading ? (
              <p className="text-sm text-muted-foreground">Loading principals...</p>
            ) : members.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                No user principals yet. Add users or invite by email.
              </p>
            ) : (
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Principal</TableHead>
                      <TableHead className="px-4">Roles</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.map((member) => {
                      const roleChips = member.role_ids
                        .map((roleId) => availableRoles.find((role) => role.id === roleId)?.name ?? roleId)
                        .sort((a, b) => a.localeCompare(b));
                      const label = member.user?.display_name ?? member.user?.email ?? member.user_id;
                      const initials = getInitials(member.user?.display_name, member.user?.email);
                      return (
                        <TableRow key={member.user_id} className="text-sm text-foreground">
                          <TableCell className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <Avatar aria-hidden="true" className="h-8 w-8" title={label}>
                                <AvatarFallback className="text-sm font-semibold text-foreground">
                                  {initials}
                                </AvatarFallback>
                              </Avatar>
                              <div className="min-w-0">
                                <p className="truncate font-semibold text-foreground">{label}</p>
                                <p className="truncate text-xs text-muted-foreground">
                                  {member.user?.email ?? member.user_id}
                                </p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="px-4 py-3">
                            <div className="flex flex-wrap gap-2">
                              {roleChips.length === 0 ? (
                                <span className="text-xs text-muted-foreground">No roles assigned.</span>
                              ) : (
                                roleChips.map((name) => (
                                  <Badge key={`${member.user_id}-${name}`} variant="secondary" className="text-xs">
                                    {name}
                                  </Badge>
                                ))
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="px-4 py-3 text-right">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => openMemberDrawer(member.user_id)}
                              disabled={!canManageMembers}
                            >
                              Manage
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>

          <TabsContent value="groups">
            {groupAssignmentsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading group principals...</p>
            ) : groupedRoleAssignments.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                No group principals assigned in this workspace.
              </p>
            ) : (
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Group</TableHead>
                      <TableHead className="px-4">Roles</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {groupedRoleAssignments.map((groupAssignment) => (
                      <TableRow key={groupAssignment.groupId}>
                        <TableCell className="px-4 py-3">
                          <p className="font-semibold text-foreground">{groupAssignment.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {groupAssignment.slug ?? groupAssignment.groupId}
                          </p>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <div className="flex flex-wrap gap-2">
                            {groupAssignment.roles.map((role) => (
                              <Badge key={`${groupAssignment.groupId}-${role}`} variant="secondary" className="text-xs">
                                {role}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        </TabsRoot>

        {hasMoreMembers && activeTab === "users" ? (
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => membersQuery.fetchNextPage()}
              disabled={isMembersFetchingMore}
            >
              {isMembersFetchingMore ? "Loading more principals..." : "Load more principals"}
            </Button>
          </div>
        ) : null}

        {!canManageMembers ? (
          <Alert tone="info">You do not have permission to manage workspace principals.</Alert>
        ) : null}
      </SettingsSection>

      <AddMemberDrawer
        open={isAddMemberOpen && canManageMembers}
        onClose={closeDrawer}
        availableRoles={availableRoles}
        memberIds={memberIds}
        isSubmitting={addMember.isPending}
        onAdd={handleAddMember}
      />

      <MemberDrawer
        open={Boolean(selectedMemberId) && canManageMembers}
        member={selectedMember}
        availableRoles={availableRoles}
        onClose={closeDrawer}
        onSaveRoles={(roleIds) => handleUpdateRoles(selectedMemberId ?? "", roleIds)}
        onRemove={() => (selectedMember ? handleRemoveMember(selectedMember) : Promise.resolve())}
        isSaving={updateMemberRoles.isPending}
        isRemoving={removeMember.isPending}
      />
    </div>
  );
}

interface AddMemberDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly availableRoles: readonly RoleDefinition[];
  readonly memberIds: ReadonlySet<string>;
  readonly isSubmitting: boolean;
  readonly onAdd: (input: {
    user?: UserSummary;
    invitedEmail?: string;
    displayName?: string;
    roleIds: string[];
  }) => Promise<void>;
}

function AddMemberDrawer({ open, onClose, availableRoles, memberIds, isSubmitting, onAdd }: AddMemberDrawerProps) {
  const [selectedUserId, setSelectedUserId] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [debouncedUserSearch, setDebouncedUserSearch] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedUserSearch(userSearch.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [userSearch]);

  useEffect(() => {
    if (!open) {
      setSelectedUserId("");
      setInviteEmail("");
      setInviteDisplayName("");
      setSelectedRoleIds([]);
      setUserSearch("");
      setFeedback(null);
    }
  }, [open]);

  const usersQuery = useUsersQuery({
    enabled: open,
    search: debouncedUserSearch,
    pageSize: 50,
  });

  const availableUsers = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return usersQuery.users
      .filter((user) => !memberIds.has(user.id))
      .sort((a, b) => {
        const nameA = a.display_name ?? a.email;
        const nameB = b.display_name ?? b.email;
        return collator.compare(nameA ?? "", nameB ?? "");
      });
  }, [memberIds, usersQuery.users]);

  const selectableUsers = useMemo(() => {
    if (!selectedUserId) {
      return availableUsers;
    }
    if (availableUsers.some((user) => user.id === selectedUserId)) {
      return availableUsers;
    }
    const fallback = usersQuery.users.find((user) => user.id === selectedUserId);
    return fallback ? [fallback, ...availableUsers] : availableUsers;
  }, [availableUsers, selectedUserId, usersQuery.users]);

  const selectedUser = useMemo(
    () => selectableUsers.find((user) => user.id === selectedUserId),
    [selectableUsers, selectedUserId],
  );

  const canSubmitAdd = (Boolean(selectedUser) || Boolean(inviteEmail.trim())) && selectedRoleIds.length > 0 && !isSubmitting;
  const searchTooShort = userSearch.trim().length > 0 && userSearch.trim().length < 2;
  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    const user = selectedUser;
    if (!user && !inviteEmail.trim()) {
      setFeedback("Select a user or enter an invitation email.");
      return;
    }
    if (selectedRoleIds.length === 0) {
      setFeedback("Select at least one role for this principal.");
      return;
    }
    if (!user && !SIMPLE_EMAIL_PATTERN.test(inviteEmail.trim())) {
      setFeedback("Enter a valid invitation email.");
      return;
    }
    try {
      await onAdd({
        user: user ?? undefined,
        invitedEmail: user ? undefined : inviteEmail.trim().toLowerCase(),
        displayName: inviteDisplayName.trim() || undefined,
        roleIds: selectedRoleIds,
      });
      setSelectedUserId("");
      setInviteEmail("");
      setInviteDisplayName("");
      setUserSearch("");
      setSelectedRoleIds([]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to add principal.";
      setFeedback(message);
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title="Add principal"
      description="Add an existing user or invite by email, then choose workspace roles."
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
        {usersQuery.isError ? (
          <Alert tone="warning">
            {usersQuery.error instanceof Error ? usersQuery.error.message : "Unable to load the user directory."}
          </Alert>
        ) : null}

        <FormField label="Search directory" hint="Enter at least two characters to search by name or email.">
          <Input
            value={userSearch}
            onChange={(event) => setUserSearch(event.target.value)}
            placeholder="Search users"
            disabled={isSubmitting || usersLoading}
          />
          {searchTooShort ? (
            <p className="text-xs text-muted-foreground">Enter at least two characters to search the full directory.</p>
          ) : null}
        </FormField>

        <FormField label="User">
          <Select
            value={selectedUserId || undefined}
            onValueChange={(value) => {
              setSelectedUserId(value);
              if (value) {
                setUserSearch("");
              }
            }}
            disabled={isSubmitting || usersLoading}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a user" />
            </SelectTrigger>
            <SelectContent>
              {selectableUsers.map((user) => (
                <SelectItem key={user.id} value={user.id}>
                  {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {availableUsers.length === 0 && userSearch ? (
            <p className="text-xs text-muted-foreground">No users matched "{userSearch}".</p>
          ) : null}
        </FormField>

        <div className="space-y-3 rounded-lg border border-border bg-background p-3">
          <p className="text-sm font-semibold text-foreground">Or invite by email</p>
          <FormField label="Email">
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

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold text-foreground">Roles</legend>
          <p className="text-xs text-muted-foreground">Assign at least one role to grant access.</p>
          <div className="flex flex-wrap gap-2">
            {availableRoles.length === 0 ? (
              <p className="text-xs text-muted-foreground">No workspace roles available yet.</p>
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
                        event.target.checked ? [...current, role.id] : current.filter((id) => id !== role.id),
                      )
                    }
                    disabled={isSubmitting}
                  />
                  <span>{role.name}</span>
                </label>
              ))
            )}
          </div>
          {selectedRoleIds.length > 0 ? (
            <p className="text-xs text-muted-foreground">{selectedRoleIds.length} role(s) selected.</p>
          ) : null}
        </fieldset>

        {usersQuery.hasNextPage ? (
          <div className="pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => usersQuery.fetchNextPage()}
              disabled={usersQuery.isFetchingNextPage}
            >
              {usersQuery.isFetchingNextPage ? "Loading more users…" : "Load more users"}
            </Button>
          </div>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmitAdd}>
            {isSubmitting ? "Submitting..." : "Add principal"}
          </Button>
        </div>
      </form>
    </SettingsDrawer>
  );
}

interface MemberDrawerProps {
  readonly open: boolean;
  readonly member: MemberWithUser | undefined;
  readonly availableRoles: readonly RoleDefinition[];
  readonly onClose: () => void;
  readonly onSaveRoles: (roleIds: string[]) => Promise<void>;
  readonly onRemove: () => Promise<void>;
  readonly isSaving: boolean;
  readonly isRemoving: boolean;
}

function MemberDrawer({
  open,
  member,
  availableRoles,
  onClose,
  onSaveRoles,
  onRemove,
  isSaving,
  isRemoving,
}: MemberDrawerProps) {
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  useEffect(() => {
    if (!open || !member) {
      setRoleDraft([]);
      setFeedback(null);
      setConfirmRemove(false);
      return;
    }
    setRoleDraft(member.role_ids);
    setFeedback(null);
    setConfirmRemove(false);
  }, [member, open]);

  const handleSave = async () => {
    if (!member) return;
    setFeedback(null);
    try {
      await onSaveRoles(roleDraft);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save principal roles.";
      setFeedback(message);
    }
  };

  const handleRemove = async () => {
    if (!member) return;
    setFeedback(null);
    try {
      await onRemove();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to remove principal.";
      setFeedback(message);
    } finally {
      setConfirmRemove(false);
    }
  };

  const title = member
    ? member.user?.display_name ?? member.user?.email ?? member.user_id
    : "Principal details";
  const initials = getInitials(member?.user?.display_name, member?.user?.email);

  return (
    <>
      <SettingsDrawer
        open={open}
        onClose={onClose}
        title={title}
        description={member ? "Update roles or remove this principal from the workspace." : undefined}
      >
        {!member ? (
          <Alert tone="warning">This principal could not be found.</Alert>
        ) : (
          <div className="space-y-4">
            {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
            <div className="flex items-start gap-3 rounded-lg border border-border bg-background p-3">
              <Avatar aria-hidden="true" className="h-10 w-10" title={title}>
                <AvatarFallback className="text-base font-semibold text-foreground">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="space-y-1">
                <p className="text-base font-semibold text-foreground">
                  {member.user?.display_name ?? member.user?.email ?? member.user_id}
                </p>
                <p className="text-sm text-muted-foreground">{member.user?.email ?? "No email available"}</p>
                <p className="text-xs text-muted-foreground">User ID: {member.user_id}</p>
              </div>
            </div>

            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold text-foreground">Roles</legend>
              <p className="text-xs text-muted-foreground">Select roles this principal should have inside the workspace.</p>
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
          </div>
        )}
        <div className="mt-6 flex items-center justify-between gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSaving || isRemoving}>
            Close
          </Button>
          <div className="flex items-center gap-2">
            {member ? (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => setConfirmRemove(true)}
                disabled={isRemoving}
              >
                {isRemoving ? "Removing..." : "Remove"}
              </Button>
            ) : null}
            <Button type="button" onClick={handleSave} disabled={!member || isSaving}>
              {isSaving ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </div>
      </SettingsDrawer>

      <ConfirmDialog
        open={confirmRemove}
        title="Remove principal?"
        description={
          member
            ? `Remove ${member.user?.display_name ?? member.user?.email ?? member.user_id} from this workspace.`
            : ""
        }
        confirmLabel="Remove principal"
        tone="danger"
        onCancel={() => setConfirmRemove(false)}
        onConfirm={handleRemove}
        isConfirming={isRemoving}
      />
    </>
  );
}
