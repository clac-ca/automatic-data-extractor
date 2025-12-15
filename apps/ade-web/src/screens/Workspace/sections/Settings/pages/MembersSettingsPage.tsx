import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "@app/nav/history";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { SettingsSectionHeader } from "../components/SettingsSectionHeader";
import { useSettingsSection } from "../sectionContext";
import {
  useAddWorkspaceMemberMutation,
  useRemoveWorkspaceMemberMutation,
  useUpdateWorkspaceMemberRolesMutation,
  useWorkspaceMembersQuery,
} from "../hooks/useWorkspaceMembers";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { RoleDefinition, WorkspaceMember } from "@shared/workspaces";
import type { UserSummary } from "@shared/users/api";
import { Alert } from "@ui/Alert";
import { Avatar } from "@ui/Avatar";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { Select } from "@ui/Select";

type MemberWithUser = WorkspaceMember & { user?: UserSummary };

export function MembersSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const { params } = useSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageMembers = hasPermission("workspace.members.manage");

  const membersQuery = useWorkspaceMembersQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);

  const addMember = useAddWorkspaceMemberMutation(workspace.id);
  const updateMemberRoles = useUpdateWorkspaceMemberRolesMutation(workspace.id);
  const removeMember = useRemoveWorkspaceMemberMutation(workspace.id);

  const [memberSearch, setMemberSearch] = useState("");
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
  const normalizedMemberSearch = memberSearch.trim().toLowerCase();
  const filteredMembers = useMemo(() => {
    if (!normalizedMemberSearch) {
      return members;
    }
    return members.filter((member) => {
      const name = member.user?.display_name ?? "";
      const email = member.user?.email ?? "";
      return (
        name.toLowerCase().includes(normalizedMemberSearch) ||
        email.toLowerCase().includes(normalizedMemberSearch) ||
        member.user_id.toLowerCase().includes(normalizedMemberSearch)
      );
    });
  }, [members, normalizedMemberSearch]);

  const hasMoreMembers = Boolean(membersQuery.hasNextPage);
  const isMembersLoading = membersQuery.isLoading;
  const isMembersFetchingMore = membersQuery.isFetchingNextPage;

  const availableRoles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? []).slice().sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const selectedParam = params[0];
  const isInviteOpen = selectedParam === "new";
  const selectedMemberId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedMember = members.find((member) => member.user_id === selectedMemberId);

  const basePath = `/workspaces/${workspace.id}/settings/access/members`;
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openInviteDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openMemberDrawer = (userId: string) =>
    navigate(`${basePath}/${encodeURIComponent(userId)}${suffix}`);

  const handleInvite = async ({ user, roleIds }: { user: UserSummary; roleIds: string[] }) => {
    setFeedbackMessage(null);
    await addMember.mutateAsync({ user, roleIds });
    setFeedbackMessage({
      tone: "success",
      message: `${user.display_name ?? user.email} added to the workspace.`,
    });
    closeDrawer();
  };

  const handleUpdateRoles = async (userId: string, roleIds: string[]) => {
    setFeedbackMessage(null);
    await updateMemberRoles.mutateAsync({ userId, roleIds });
    setFeedbackMessage({ tone: "success", message: "Member roles updated." });
    closeDrawer();
  };

  const handleRemoveMember = async (member: MemberWithUser) => {
    setFeedbackMessage(null);
    await removeMember.mutateAsync(member.user_id);
    setFeedbackMessage({ tone: "success", message: "Member removed." });
    closeDrawer();
  };

  return (
    <div className="space-y-6">
      <SettingsSectionHeader
        title="Members"
        description="Invite teammates, adjust their workspace roles, or remove their access."
        actions={
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
            {memberCount} member{memberCount === 1 ? "" : "s"}
          </span>
        }
      />

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

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Workspace members</h2>
            <p className="text-sm text-slate-500">
              {isMembersLoading ? "Loading members…" : `${memberCount} member${memberCount === 1 ? "" : "s"} total`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <FormField label="Search members" className="w-full max-w-xs">
              <Input
                value={memberSearch}
                onChange={(event) => setMemberSearch(event.target.value)}
                placeholder="Search by name, email, or ID"
                disabled={isMembersLoading}
              />
            </FormField>
            {canManageMembers ? (
              <Button type="button" onClick={openInviteDrawer}>
                Add member
              </Button>
            ) : null}
          </div>
        </header>

        {isMembersLoading ? (
          <p className="text-sm text-slate-600">Loading members…</p>
        ) : filteredMembers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            {memberSearch ? `No members match "${memberSearch}".` : "No members yet. Add teammates to collaborate."}
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Member</th>
                  <th className="px-4 py-3">Roles</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {filteredMembers.map((member) => {
                  const roleChips = member.role_ids
                    .map((roleId) => availableRoles.find((role) => role.id === roleId)?.name ?? roleId)
                    .sort((a, b) => a.localeCompare(b));
                  const label = member.user?.display_name ?? member.user?.email ?? member.user_id;
                  return (
                    <tr key={member.user_id} className="text-sm text-slate-700">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={member.user?.display_name} email={member.user?.email} size="sm" />
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-slate-900">{label}</p>
                            <p className="truncate text-xs text-slate-500">{member.user?.email ?? member.user_id}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {roleChips.length === 0 ? (
                            <span className="text-xs text-slate-500">No roles assigned.</span>
                          ) : (
                            roleChips.map((name) => (
                              <span
                                key={`${member.user_id}-${name}`}
                                className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
                              >
                                {name}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => openMemberDrawer(member.user_id)}
                          disabled={!canManageMembers}
                        >
                          Manage
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {hasMoreMembers ? (
          <div className="pt-4">
            <Button
              type="button"
              variant="ghost"
              onClick={() => membersQuery.fetchNextPage()}
              disabled={isMembersFetchingMore}
            >
              {isMembersFetchingMore ? "Loading more members…" : "Load more members"}
            </Button>
          </div>
        ) : null}

        {!canManageMembers ? (
          <Alert tone="info">You do not have permission to manage workspace members.</Alert>
        ) : null}
      </section>

      <InviteMemberDrawer
        open={isInviteOpen && canManageMembers}
        onClose={closeDrawer}
        availableRoles={availableRoles}
        memberIds={memberIds}
        isSubmitting={addMember.isPending}
        onInvite={handleInvite}
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

interface InviteMemberDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly availableRoles: readonly RoleDefinition[];
  readonly memberIds: ReadonlySet<string>;
  readonly isSubmitting: boolean;
  readonly onInvite: (input: { user: UserSummary; roleIds: string[] }) => Promise<void>;
}

function InviteMemberDrawer({ open, onClose, availableRoles, memberIds, isSubmitting, onInvite }: InviteMemberDrawerProps) {
  const [inviteUserId, setInviteUserId] = useState("");
  const [inviteRoleIds, setInviteRoleIds] = useState<string[]>([]);
  const [inviteSearch, setInviteSearch] = useState("");
  const [debouncedInviteSearch, setDebouncedInviteSearch] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedInviteSearch(inviteSearch.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [inviteSearch]);

  useEffect(() => {
    if (!open) {
      setInviteUserId("");
      setInviteRoleIds([]);
      setInviteSearch("");
      setFeedback(null);
    }
  }, [open]);

  const usersQuery = useUsersQuery({
    enabled: open,
    search: debouncedInviteSearch,
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

  const selectedInviteUser = useMemo(
    () => availableUsers.find((user) => user.id === inviteUserId),
    [availableUsers, inviteUserId],
  );

  const canSubmitInvite = Boolean(inviteUserId) && inviteRoleIds.length > 0 && !isSubmitting;
  const inviteSearchTooShort = inviteSearch.trim().length > 0 && inviteSearch.trim().length < 2;
  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    const user = availableUsers.find((candidate) => candidate.id === inviteUserId);
    if (!user) {
      setFeedback("Select a user to add.");
      return;
    }
    if (inviteRoleIds.length === 0) {
      setFeedback("Select at least one role for this member.");
      return;
    }
    try {
      await onInvite({ user, roleIds: inviteRoleIds });
      setInviteUserId("");
      setInviteSearch("");
      setInviteRoleIds([]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to add member.";
      setFeedback(message);
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title="Add member"
      description="Invite an existing teammate and choose their workspace roles."
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
            value={inviteSearch}
            onChange={(event) => setInviteSearch(event.target.value)}
            placeholder="Search users"
            disabled={isSubmitting || usersLoading}
          />
          {inviteSearchTooShort ? (
            <p className="text-xs text-slate-500">Enter at least two characters to search the full directory.</p>
          ) : null}
        </FormField>

        <FormField label="User" required>
          <Select
            value={inviteUserId}
            onChange={(event) => {
              setInviteUserId(event.target.value);
              if (event.target.value) {
                setInviteSearch("");
              }
            }}
            disabled={isSubmitting || usersLoading}
            required
          >
            <option value="">Select a user</option>
            {selectedInviteUser &&
            !availableUsers.some((user) => user.id === selectedInviteUser.id) ? (
              <option value={selectedInviteUser.id}>
                {selectedInviteUser.display_name
                  ? `${selectedInviteUser.display_name} (${selectedInviteUser.email})`
                  : selectedInviteUser.email}
              </option>
            ) : null}
            {availableUsers.map((user) => (
              <option key={user.id} value={user.id}>
                {user.display_name ? `${user.display_name} (${user.email})` : user.email}
              </option>
            ))}
          </Select>
          {availableUsers.length === 0 && inviteSearch ? (
            <p className="text-xs text-slate-500">No users matched "{inviteSearch}".</p>
          ) : null}
        </FormField>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold text-slate-700">Roles</legend>
          <p className="text-xs text-slate-500">Assign at least one role to grant access.</p>
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
                    onChange={(event) =>
                      setInviteRoleIds((current) =>
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
          {inviteRoleIds.length > 0 ? (
            <p className="text-xs text-slate-500">{inviteRoleIds.length} role(s) selected.</p>
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
          <Button type="submit" isLoading={isSubmitting} disabled={!canSubmitInvite}>
            Add member
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
      const message = error instanceof Error ? error.message : "Unable to save member roles.";
      setFeedback(message);
    }
  };

  const handleRemove = async () => {
    if (!member) return;
    setFeedback(null);
    try {
      await onRemove();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to remove member.";
      setFeedback(message);
    } finally {
      setConfirmRemove(false);
    }
  };

  const title = member
    ? member.user?.display_name ?? member.user?.email ?? member.user_id
    : "Member details";

  return (
    <>
      <SettingsDrawer
        open={open}
        onClose={onClose}
        title={title}
        description={member ? "Update roles or remove this member from the workspace." : undefined}
      >
        {!member ? (
          <Alert tone="warning">This member could not be found.</Alert>
        ) : (
          <div className="space-y-4">
            {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
            <div className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <Avatar name={member.user?.display_name} email={member.user?.email} size="md" />
              <div className="space-y-1">
                <p className="text-base font-semibold text-slate-900">
                  {member.user?.display_name ?? member.user?.email ?? member.user_id}
                </p>
                <p className="text-sm text-slate-500">{member.user?.email ?? "No email available"}</p>
                <p className="text-xs text-slate-500">User ID: {member.user_id}</p>
              </div>
            </div>

            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold text-slate-700">Roles</legend>
              <p className="text-xs text-slate-500">Select the roles this member should have inside the workspace.</p>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-slate-500">No workspace roles available.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300"
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
                <p className="text-xs text-slate-500">{roleDraft.length} role(s) selected.</p>
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
                variant="danger"
                onClick={() => setConfirmRemove(true)}
                disabled={isRemoving}
                isLoading={isRemoving}
              >
                Remove
              </Button>
            ) : null}
            <Button type="button" onClick={handleSave} isLoading={isSaving} disabled={!member || isSaving}>
              Save changes
            </Button>
          </div>
        </div>
      </SettingsDrawer>

      <ConfirmDialog
        open={confirmRemove}
        title="Remove member?"
        description={
          member
            ? `Remove ${member.user?.display_name ?? member.user?.email ?? member.user_id} from this workspace.`
            : ""
        }
        confirmLabel="Remove member"
        tone="danger"
        onCancel={() => setConfirmRemove(false)}
        onConfirm={handleRemove}
        isConfirming={isRemoving}
      />
    </>
  );
}
