import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { useInviteUserMutation } from "@shared/users/hooks/useInviteUserMutation";
import {
  useAddWorkspaceMemberMutation,
  useRemoveWorkspaceMemberMutation,
  useUpdateWorkspaceMemberRolesMutation,
  useWorkspaceMembersQuery,
} from "../hooks/useWorkspaceMembers";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { WorkspaceMember, RoleDefinition } from "@features/Workspace/api/workspaces-api";
import type { UserSummary } from "@shared/users/api";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { Select } from "@ui/Select";
import { Avatar } from "@ui/Avatar";

export function WorkspaceMembersSection() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageMembers = hasPermission("Workspace.Members.ReadWrite");
  const membersQuery = useWorkspaceMembersQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);

  const addMember = useAddWorkspaceMemberMutation(workspace.id);
  const updateMemberRoles = useUpdateWorkspaceMemberRolesMutation(workspace.id);
  const removeMember = useRemoveWorkspaceMemberMutation(workspace.id);
  const inviteUserMutation = useInviteUserMutation();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [inviteUserId, setInviteUserId] = useState<string>("");
  const [inviteRoleIds, setInviteRoleIds] = useState<string[]>([]);
  const [inviteSearch, setInviteSearch] = useState<string>("");
  const [debouncedInviteSearch, setDebouncedInviteSearch] = useState<string>("");
  const [inviteOption, setInviteOption] = useState<"existing" | "new">("existing");
  const [inviteEmail, setInviteEmail] = useState<string>("");
  const [inviteDisplayName, setInviteDisplayName] = useState<string>("");
  const [memberSearch, setMemberSearch] = useState<string>("");
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedInviteSearch(inviteSearch.trim());
    }, 250);
    return () => window.clearTimeout(handle);
  }, [inviteSearch]);

  const usersQuery = useUsersQuery({
    enabled: canManageMembers,
    search: debouncedInviteSearch,
    pageSize: 50,
  });

  const roleLookup = useMemo(() => {
    const map = new Map<string, RoleDefinition>();
    for (const role of rolesQuery.data?.items ?? []) {
      map.set(role.id, role);
    }
    return map;
  }, [rolesQuery.data]);

  const members = useMemo(() => {
    const list = membersQuery.data?.items ?? [];
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return Array.from(list).sort((a, b) => {
      const nameA = a.user.display_name ?? a.user.email;
      const nameB = b.user.display_name ?? b.user.email;
      return collator.compare(nameA ?? "", nameB ?? "");
    });
  }, [membersQuery.data]);
  const memberIds = useMemo(() => new Set(members.map((member) => member.user.id)), [members]);

  const normalizedMemberSearch = memberSearch.trim().toLowerCase();
  const filteredMembers = useMemo(() => {
    if (!normalizedMemberSearch) {
      return members;
    }
    return members.filter((member) => {
      const name = member.user.display_name ?? "";
      const email = member.user.email ?? "";
      return (
        name.toLowerCase().includes(normalizedMemberSearch) ||
        email.toLowerCase().includes(normalizedMemberSearch) ||
        member.id.toLowerCase().includes(normalizedMemberSearch)
      );
    });
  }, [members, normalizedMemberSearch]);

  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;
  const usersFetchingMore = usersQuery.isFetchingNextPage;

  const availableUsers: UserSummary[] = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return usersQuery.users
      .filter((user) => !memberIds.has(user.id))
      .sort((a, b) => {
        const nameA = a.display_name ?? a.email;
        const nameB = b.display_name ?? b.email;
        return collator.compare(nameA ?? "", nameB ?? "");
      });
  }, [memberIds, usersQuery.users]);

  const normalizedInviteSearch = inviteSearch.trim().toLowerCase();
  const serverInviteSearch = debouncedInviteSearch.trim().toLowerCase();
  const usingServerSearch = serverInviteSearch.length >= 2;
  const inviteSearchTooShort = inviteOption === "existing" && inviteSearch.trim().length > 0 && inviteSearch.trim().length < 2;
  const filteredAvailableUsers = useMemo(() => {
    if (!normalizedInviteSearch || usingServerSearch) {
      return availableUsers;
    }
    return availableUsers.filter((user) => {
      const name = user.display_name ?? "";
      return (
        name.toLowerCase().includes(normalizedInviteSearch) ||
        user.email.toLowerCase().includes(normalizedInviteSearch)
      );
    });
  }, [availableUsers, normalizedInviteSearch, usingServerSearch]);

  const selectedInviteUser = useMemo(
    () =>
      inviteOption === "existing"
        ? availableUsers.find((user) => user.id === inviteUserId)
        : undefined,
    [availableUsers, inviteOption, inviteUserId],
  );

  const availableRoles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? [])
      .filter((role) => role.scope_type === "workspace")
      .sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const handleToggleRoleDraft = (roleId: string, selected: boolean) => {
    setRoleDraft((current) => {
      if (selected) {
        return current.includes(roleId) ? current : [...current, roleId];
      }
      return current.filter((id) => id !== roleId);
    });
  };

  const handleToggleInviteRole = (roleId: string, selected: boolean) => {
    setInviteRoleIds((current) => {
      if (selected) {
        return current.includes(roleId) ? current : [...current, roleId];
      }
      return current.filter((id) => id !== roleId);
    });
  };

  const startEdit = (member: WorkspaceMember) => {
    setEditingId(member.id);
    setRoleDraft(member.roles);
    setFeedbackMessage(null);
  };

  const resetEditState = () => {
    setEditingId(null);
    setRoleDraft([]);
  };

  const handleUpdateRoles = () => {
    if (!editingId) {
      return;
    }
    setFeedbackMessage(null);
    updateMemberRoles.mutate(
      { membershipId: editingId, roleIds: roleDraft },
      {
        onSuccess: () => {
          setFeedbackMessage({ tone: "success", message: "Member roles updated." });
          resetEditState();
        },
        onError: (error) => {
          const message =
            error instanceof Error ? error.message : "Unable to update member roles.";
          setFeedbackMessage({ tone: "danger", message });
        },
      },
    );
  };

  const handleRemoveMember = (member: WorkspaceMember) => {
    if (!canManageMembers) {
      return;
    }
    const confirmed = window.confirm(`Remove ${member.user.display_name ?? member.user.email} from the workspace?`);
    if (!confirmed) {
      return;
    }
    setFeedbackMessage(null);
    removeMember.mutate(member.id, {
      onSuccess: () => {
        setFeedbackMessage({ tone: "success", message: "Member removed." });
      },
      onError: (error) => {
        const message =
          error instanceof Error ? error.message : "Unable to remove member.";
        setFeedbackMessage({ tone: "danger", message });
      },
    });
  };

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const isInvitePending = addMember.isPending || inviteUserMutation.isPending;
  const canSubmitInvite =
    inviteOption === "existing"
      ? Boolean(inviteUserId)
      : emailPattern.test(inviteEmail.trim());

  const handleInvite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedbackMessage(null);
    try {
      if (inviteOption === "existing") {
        if (!inviteUserId) {
          setFeedbackMessage({ tone: "danger", message: "Select a user to invite." });
          return;
        }
        const user = availableUsers.find((candidate) => candidate.id === inviteUserId);
        if (!user) {
          setFeedbackMessage({ tone: "danger", message: "Selected user is no longer available." });
          return;
        }
        await addMember.mutateAsync({ user, roleIds: inviteRoleIds });
        setInviteUserId("");
        setInviteRoleIds([]);
        setInviteSearch("");
        setFeedbackMessage({
          tone: "success",
          message: `${user.display_name ?? user.email} added to the workspace.`,
        });
        return;
      }

      const normalizedEmail = inviteEmail.trim().toLowerCase();
      if (!normalizedEmail || !emailPattern.test(normalizedEmail)) {
        setFeedbackMessage({ tone: "danger", message: "Enter a valid email address to send an invite." });
        return;
      }

      const invitedUser = await inviteUserMutation.mutateAsync({
        email: normalizedEmail,
        displayName: inviteDisplayName.trim() || undefined,
      });

      await addMember.mutateAsync({ user: invitedUser, roleIds: inviteRoleIds });
      setInviteEmail("");
      setInviteDisplayName("");
      setInviteRoleIds([]);
      setFeedbackMessage({
        tone: "success",
        message: `Invitation sent to ${invitedUser.display_name ?? invitedUser.email}.`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to invite member.";
      setFeedbackMessage({ tone: "danger", message });
    }
  };

  useEffect(() => {
    if (inviteOption !== "existing" || !selectedInviteUser) {
      return;
    }
    if (!filteredAvailableUsers.some((user) => user.id === selectedInviteUser.id)) {
      setInviteSearch("");
    }
  }, [filteredAvailableUsers, inviteOption, selectedInviteUser]);

  useEffect(() => {
    setFeedbackMessage(null);
    if (inviteOption === "existing") {
      setInviteEmail("");
      setInviteDisplayName("");
      return;
    }
    setInviteUserId("");
    setInviteSearch("");
  }, [inviteOption]);

  const resetInviteDraft = () => {
    if (inviteOption === "existing") {
      setInviteUserId("");
      setInviteSearch("");
    } else {
      setInviteEmail("");
      setInviteDisplayName("");
    }
    setInviteRoleIds([]);
  };

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {membersQuery.isError ? (
        <Alert tone="danger">
          {membersQuery.error instanceof Error ? membersQuery.error.message : "Unable to load workspace members."}
        </Alert>
      ) : null}
      {rolesQuery.isError ? (
        <Alert tone="warning">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}

      {canManageMembers ? (
        <form
          onSubmit={handleInvite}
          className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
        >
          <header className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-900">Invite member</h2>
            <p className="text-sm text-slate-500">
              Invite someone new by email or add an existing teammate, then choose the roles that reflect what they should be able
              to do here.
            </p>
          </header>
          {usersQuery.isError ? (
            <Alert tone="warning">
              We couldn't load the user directory. Retry or invite later.
            </Alert>
          ) : null}
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-slate-700">Invite method</legend>
            <p className="text-xs text-slate-500">Choose whether you are inviting someone who already has an account or sending a brand-new invite.</p>
            <div className="flex flex-wrap gap-2">
              <label
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  inviteOption === "existing"
                    ? "border-brand-300 bg-brand-50 text-brand-700"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="invite-method"
                  value="existing"
                  checked={inviteOption === "existing"}
                  onChange={() => setInviteOption("existing")}
                  disabled={isInvitePending}
                  className="h-4 w-4"
                />
                <span>Existing teammate</span>
              </label>
              <label
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  inviteOption === "new"
                    ? "border-brand-300 bg-brand-50 text-brand-700"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="invite-method"
                  value="new"
                  checked={inviteOption === "new"}
                  onChange={() => setInviteOption("new")}
                  disabled={isInvitePending}
                  className="h-4 w-4"
                />
                <span>Invite by email</span>
              </label>
            </div>
          </fieldset>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              {inviteOption === "existing" ? (
                <>
                  <FormField
                    label="Search directory"
                    hint="Filter by name or email to quickly find a teammate."
                  >
                    <Input
                      value={inviteSearch}
                      onChange={(event) => setInviteSearch(event.target.value)}
                      placeholder="e.g. Casey or casey@example.com"
                      disabled={isInvitePending || usersLoading}
                    />
                  </FormField>
                  {inviteSearchTooShort ? (
                    <p className="text-xs text-slate-500">
                      Enter at least two characters to search the full directory.
                    </p>
                  ) : null}
                  {usersQuery.isError ? (
                    <p className="text-xs text-rose-600">Unable to load users. Try again shortly.</p>
                  ) : null}
                  <FormField label="User" required>
                    <Select
                      value={inviteUserId}
                      onChange={(event) => {
                        setInviteUserId(event.target.value);
                        if (event.target.value) {
                          setInviteSearch("");
                        }
                      }}
                      disabled={isInvitePending || usersLoading}
                      required
                    >
                      <option value="">Select a user</option>
                      {selectedInviteUser &&
                      !filteredAvailableUsers.some((user) => user.id === selectedInviteUser.id) ? (
                        <option value={selectedInviteUser.id}>
                          {selectedInviteUser.display_name
                            ? `${selectedInviteUser.display_name} (${selectedInviteUser.email})`
                            : selectedInviteUser.email}
                        </option>
                      ) : null}
                      {filteredAvailableUsers.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                        </option>
                      ))}
                    </Select>
                  </FormField>
                  {filteredAvailableUsers.length === 0 && inviteSearch ? (
                    <p className="text-xs text-slate-500">
                      No users matched "{inviteSearch}". Clear the search to see everyone.
                    </p>
                  ) : null}
                  {usersQuery.hasNextPage ? (
                    <div className="pt-2">
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => usersQuery.fetchNextPage()}
                        disabled={usersLoading || usersFetchingMore}
                      >
                        {usersFetchingMore ? "Loading more users…" : "Load more users"}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <FormField label="Email" required>
                    <Input
                      type="email"
                      value={inviteEmail}
                      onChange={(event) => setInviteEmail(event.target.value)}
                      placeholder="name@example.com"
                      autoComplete="off"
                      disabled={isInvitePending}
                      required
                    />
                  </FormField>
                  <FormField
                    label="Display name"
                    hint="Optional – helps teammates recognise them."
                  >
                    <Input
                      value={inviteDisplayName}
                      onChange={(event) => setInviteDisplayName(event.target.value)}
                      placeholder="Casey Lee"
                      autoComplete="off"
                      disabled={isInvitePending}
                    />
                  </FormField>
                  <p className="text-xs text-slate-500">
                    We'll email an invitation so they can create their account and join this workspace.
                  </p>
                </>
              )}
            </div>

            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold text-slate-700">Roles</legend>
              <p className="text-xs text-slate-500">
                Roles control which actions a member can perform inside this workspace.
              </p>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-slate-500">No workspace roles available yet.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300"
                        checked={inviteRoleIds.includes(role.id)}
                        onChange={(event) => handleToggleInviteRole(role.id, event.target.checked)}
                        disabled={isInvitePending}
                      />
                      <span>{role.name}</span>
                    </label>
                  ))
                )}
              </div>
              {inviteRoleIds.length > 0 ? (
                <p className="text-xs text-slate-500">{inviteRoleIds.length} role(s) selected.</p>
              ) : null}
            </fieldset>
          </div>

          <div className="flex justify-end gap-2">
            {(inviteOption === "existing"
            ? inviteUserId || inviteSearch || inviteRoleIds.length > 0
            : inviteEmail || inviteDisplayName || inviteRoleIds.length > 0) ? (
              <Button type="button" variant="ghost" onClick={resetInviteDraft} disabled={isInvitePending}>
                Clear
              </Button>
            ) : null}
            <Button type="submit" isLoading={isInvitePending} disabled={!canSubmitInvite || isInvitePending}>
              {inviteOption === "existing" ? "Add member" : "Send invite"}
            </Button>
          </div>
        </form>
      ) : (
        <Alert tone="info">
          You do not have permission to manage workspace members. Contact an administrator for access.
        </Alert>
      )}

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Current members</h2>
            <p className="text-sm text-slate-500">
              {membersQuery.isLoading
                ? "Loading members…"
                : `${members.length} member${members.length === 1 ? "" : "s"}`}
            </p>
          </div>
          <FormField label="Search members" className="w-full max-w-xs">
            <Input
              value={memberSearch}
              onChange={(event) => setMemberSearch(event.target.value)}
              placeholder="Search by name, email, or ID"
              disabled={membersQuery.isLoading}
            />
          </FormField>
        </header>

        {membersQuery.isLoading ? (
          <p className="text-sm text-slate-600">Loading members…</p>
        ) : members.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No members yet. Invite teammates to collaborate on this workspace.
          </p>
        ) : filteredMembers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No members match "{memberSearch}".
          </p>
        ) : (
          <ul className="space-y-4" role="list">
            {filteredMembers.map((member) => {
              const userLabel = member.user.display_name ?? member.user.email;
              const roleChips = member.roles.map((roleId) => roleLookup.get(roleId)?.name ?? roleId);
              const isEditing = editingId === member.id;
              return (
                <li
                  key={member.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <Avatar name={member.user.display_name} email={member.user.email} size="sm" />
                      <div className="space-y-1">
                        <p className="text-base font-semibold text-slate-900">{userLabel}</p>
                        <p className="text-sm text-slate-500">{member.user.email}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          {member.is_default ? (
                            <span className="inline-flex items-center rounded-full bg-brand-100 px-2 py-0.5 font-semibold text-brand-700">
                              Default workspace
                            </span>
                          ) : null}
                          <span>ID: {member.id}</span>
                        </div>
                      </div>
                    </div>
                    {canManageMembers ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => (isEditing ? resetEditState() : startEdit(member))}
                          disabled={
                            updateMemberRoles.isPending ||
                            removeMember.isPending ||
                            (isEditing && updateMemberRoles.isPending)
                          }
                        >
                          {isEditing ? "Cancel" : "Manage roles"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveMember(member)}
                          disabled={removeMember.isPending}
                        >
                          Remove
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {roleChips.length > 0 ? (
                      roleChips.map((roleName) => (
                        <span
                          key={`${member.id}-${roleName}`}
                          className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm"
                        >
                          {roleName}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No roles assigned.</span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                      <p className="text-sm font-semibold text-slate-700">Assign roles</p>
                      <div className="flex flex-wrap gap-2">
                        {availableRoles.map((role) => (
                          <label
                            key={role.id}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-slate-300"
                              checked={roleDraft.includes(role.id)}
                              onChange={(event) => handleToggleRoleDraft(role.id, event.target.checked)}
                              disabled={updateMemberRoles.isPending}
                            />
                            <span>{role.name}</span>
                          </label>
                        ))}
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={resetEditState}
                          disabled={updateMemberRoles.isPending}
                        >
                          Cancel
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={handleUpdateRoles}
                          isLoading={updateMemberRoles.isPending}
                          disabled={updateMemberRoles.isPending}
                        >
                          Save roles
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
