import { useMemo, useState, type FormEvent } from "react";

import { useWorkspaceContext } from "../context/WorkspaceContext";
import { useUsersQuery } from "../../users/hooks/useUsersQuery";
import {
  useAddWorkspaceMemberMutation,
  useRemoveWorkspaceMemberMutation,
  useUpdateWorkspaceMemberRolesMutation,
  useWorkspaceMembersQuery,
} from "../hooks/useWorkspaceMembers";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { WorkspaceMember } from "@types/workspace-members";
import type { RoleDefinition } from "@types/roles";
import type { UserSummary } from "@types/users";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";

export function WorkspaceMembersSection() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageMembers = hasPermission("Workspace.Members.ReadWrite");
  const membersQuery = useWorkspaceMembersQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const usersQuery = useUsersQuery({ enabled: canManageMembers });

  const addMember = useAddWorkspaceMemberMutation(workspace.id);
  const updateMemberRoles = useUpdateWorkspaceMemberRolesMutation(workspace.id);
  const removeMember = useRemoveWorkspaceMemberMutation(workspace.id);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [inviteUserId, setInviteUserId] = useState<string>("");
  const [inviteRoleIds, setInviteRoleIds] = useState<string[]>([]);
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const roleLookup = useMemo(() => {
    const map = new Map<string, RoleDefinition>();
    for (const role of rolesQuery.data ?? []) {
      map.set(role.role_id, role);
    }
    return map;
  }, [rolesQuery.data]);

  const members = membersQuery.data ?? [];
  const memberIds = useMemo(() => new Set(members.map((member) => member.user.user_id)), [members]);

  const availableUsers: UserSummary[] = useMemo(() => {
    if (!usersQuery.data) {
      return [];
    }
    return usersQuery.data.filter((user) => !memberIds.has(user.user_id));
  }, [memberIds, usersQuery.data]);

  const availableRoles = useMemo(() => {
    return (rolesQuery.data ?? []).filter((role) => role.scope_type === "workspace");
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
    setEditingId(member.workspace_membership_id);
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
    removeMember.mutate(member.workspace_membership_id, {
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

  const handleInvite = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!inviteUserId) {
      setFeedbackMessage({ tone: "danger", message: "Select a user to invite." });
      return;
    }
    const user = availableUsers.find((candidate) => candidate.user_id === inviteUserId);
    if (!user) {
      setFeedbackMessage({ tone: "danger", message: "Selected user is no longer available." });
      return;
    }
    setFeedbackMessage(null);
    addMember.mutate(
      { user, roleIds: inviteRoleIds },
      {
        onSuccess: () => {
          setInviteUserId("");
          setInviteRoleIds([]);
          setFeedbackMessage({ tone: "success", message: "Member invited to the workspace." });
        },
        onError: (error) => {
          const message =
            error instanceof Error ? error.message : "Unable to invite member.";
          setFeedbackMessage({ tone: "danger", message });
        },
      },
    );
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
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
        >
          <header className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-900">Invite member</h2>
            <p className="text-sm text-slate-500">
              Select an existing user and assign roles to grant access to this workspace.
            </p>
          </header>
          {usersQuery.isError ? (
            <Alert tone="warning">
              We couldn't load the user directory. Retry or invite later.
            </Alert>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm font-medium text-slate-700">
              User
              <select
                className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
                value={inviteUserId}
                onChange={(event) => setInviteUserId(event.target.value)}
                disabled={addMember.isPending || usersQuery.isLoading}
                required
              >
                <option value="">Select a user</option>
                {availableUsers.map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-slate-700">Roles</legend>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-slate-500">No workspace roles available yet.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.role_id}
                      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300"
                        checked={inviteRoleIds.includes(role.role_id)}
                        onChange={(event) => handleToggleInviteRole(role.role_id, event.target.checked)}
                        disabled={addMember.isPending}
                      />
                      <span>{role.name}</span>
                    </label>
                  ))
                )}
              </div>
            </fieldset>
          </div>

          <div className="flex justify-end">
            <Button type="submit" isLoading={addMember.isPending} disabled={!inviteUserId}>
              Invite member
            </Button>
          </div>
        </form>
      ) : (
        <Alert tone="info">
          You do not have permission to manage workspace members. Contact an administrator for access.
        </Alert>
      )}

      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Current members</h2>
            <p className="text-sm text-slate-500">
              {membersQuery.isLoading ? "Loading members…" : `${members.length} member${members.length === 1 ? "" : "s"}`}
            </p>
          </div>
        </header>

        {membersQuery.isLoading ? (
          <p className="text-sm text-slate-600">Loading members…</p>
        ) : members.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No members yet. Invite teammates to collaborate on this workspace.
          </p>
        ) : (
          <ul className="space-y-4" role="list">
            {members.map((member) => {
              const userLabel = member.user.display_name ?? member.user.email;
              const roleChips = member.roles.map((roleId) => roleLookup.get(roleId)?.name ?? roleId);
              const isEditing = editingId === member.workspace_membership_id;
              return (
                <li
                  key={member.workspace_membership_id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-base font-semibold text-slate-900">{userLabel}</p>
                      <p className="text-sm text-slate-500">{member.user.email}</p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        {member.is_default ? (
                          <span className="inline-flex items-center rounded-full bg-brand-100 px-2 py-0.5 font-semibold text-brand-700">
                            Default workspace
                          </span>
                        ) : null}
                        <span>ID: {member.workspace_membership_id}</span>
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
                          key={`${member.workspace_membership_id}-${roleName}`}
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
                            key={role.role_id}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-slate-300"
                              checked={roleDraft.includes(role.role_id)}
                              onChange={(event) => handleToggleRoleDraft(role.role_id, event.target.checked)}
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
