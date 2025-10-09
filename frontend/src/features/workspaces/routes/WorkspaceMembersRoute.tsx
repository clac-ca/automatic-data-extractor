import { type FormEvent, useEffect, useMemo, useRef, useState, useId } from "react";
import { useOutletContext } from "react-router-dom";

import { ApiError } from "../../../shared/api/client";
import type { WorkspaceMember, WorkspaceRoleDefinition } from "../../../shared/api/types";
import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { useAddWorkspaceMemberMutation } from "../hooks/useAddWorkspaceMemberMutation";
import { useRemoveWorkspaceMemberMutation } from "../hooks/useRemoveWorkspaceMemberMutation";
import { useUpdateWorkspaceMemberRolesMutation } from "../hooks/useUpdateWorkspaceMemberRolesMutation";
import { useWorkspaceMembersQuery } from "../hooks/useWorkspaceMembersQuery";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRolesQuery";
import { workspaceCan } from "../../../shared/rbac/can";
import { formatRoleSlug } from "../utils/roles";

export function WorkspaceMembersRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to view member access.
      </div>
    );
  }

  const workspaceId = workspace.id;
  return <WorkspaceMembersContent workspaceId={workspaceId} workspacePermissions={workspace.permissions} />;
}

interface WorkspaceMembersContentProps {
  workspaceId: string;
  workspacePermissions: string[];
}

function WorkspaceMembersContent({ workspaceId, workspacePermissions }: WorkspaceMembersContentProps) {
  const canManageMembers = workspaceCan.manageMembers(workspacePermissions);
  const canReadRoles =
    canManageMembers ||
    workspaceCan.viewRoles(workspacePermissions) ||
    workspaceCan.manageRoles(workspacePermissions);

  const membersQuery = useWorkspaceMembersQuery(workspaceId, true);
  const rolesQuery = useWorkspaceRolesQuery(workspaceId, canReadRoles);

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<WorkspaceMember | null>(null);
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<WorkspaceMember | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const lastFocusedElementRef = useRef<HTMLElement | null>(null);

  const captureFocus = () => {
    lastFocusedElementRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
  };

  const restoreFocus = () => {
    const element = lastFocusedElementRef.current;
    lastFocusedElementRef.current = null;
    if (element) {
      window.setTimeout(() => {
        element.focus();
      }, 0);
    }
  };

  const addMemberMutation = useAddWorkspaceMemberMutation(workspaceId);
  const updateRolesMutation = useUpdateWorkspaceMemberRolesMutation(workspaceId);
  const removeMemberMutation = useRemoveWorkspaceMemberMutation(workspaceId);

  const roleMap = useMemo(() => {
    const roles = rolesQuery.data ?? [];
    return new Map(roles.map((role) => [role.slug, role]));
  }, [rolesQuery.data]);

  const members = membersQuery.data ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Members</h2>
          <p className="text-sm text-slate-300">
            View workspace memberships and effective permissions provided by assigned roles.
          </p>
        </div>
        {canManageMembers && (
          <button
            type="button"
            onClick={() => {
              captureFocus();
              setActionError(null);
              setIsAddDialogOpen(true);
            }}
            className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            + Invite member
          </button>
        )}
      </header>

      {membersQuery.isLoading ? (
        <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">Loading members…</div>
      ) : membersQuery.error ? (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-100">
          We were unable to load the members for this workspace.
        </div>
      ) : members.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
          No members have been added to this workspace yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded border border-slate-800">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Member</th>
                <th className="px-4 py-3 font-semibold">Roles</th>
                <th className="px-4 py-3 font-semibold">Permissions</th>
                <th className="px-4 py-3 font-semibold">Default</th>
                {canManageMembers && <th className="px-4 py-3 font-semibold text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-900 bg-slate-950/60 text-slate-200">
              {members.map((member) => (
                <tr key={member.id}>
                  <td className="px-4 py-3 align-top">
                    <div className="font-medium text-slate-100">{member.user.display_name ?? member.user.email}</div>
                    <div className="text-xs text-slate-500">{member.user.email}</div>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <RoleList member={member} roleMap={roleMap} />
                  </td>
                  <td className="px-4 py-3 align-top">
                    {member.permissions.length > 0 ? (
                      <ul className="flex flex-wrap gap-2 text-xs text-slate-200">
                        {member.permissions.map((permission) => (
                          <li key={permission} className="rounded border border-slate-800 bg-slate-900 px-2 py-1">
                            {permission}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-xs text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-300">{member.is_default ? "Yes" : "No"}</td>
                  {canManageMembers && (
                    <td className="px-4 py-3 align-top text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            captureFocus();
                            setActionError(null);
                            setEditingMember(member);
                          }}
                          className="rounded border border-slate-700 px-2 py-1 text-xs font-medium text-slate-200 transition hover:border-slate-500 hover:text-slate-50"
                        >
                          Edit roles
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            captureFocus();
                            setActionError(null);
                            setMemberPendingRemoval(member);
                          }}
                          disabled={removeMemberMutation.isPending}
                          className="rounded border border-transparent px-2 py-1 text-xs font-medium text-rose-200 transition hover:text-rose-100"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {actionError && (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-100" role="alert">
          {actionError}
        </div>
      )}

      <AddMemberDialog
        open={isAddDialogOpen}
        onClose={() => {
          setIsAddDialogOpen(false);
          setActionError(null);
          restoreFocus();
        }}
        roles={rolesQuery.data ?? []}
        isSubmitting={addMemberMutation.isPending}
        onSubmit={async (payload) => {
          setActionError(null);
          try {
            await addMemberMutation.mutateAsync(payload);
            setIsAddDialogOpen(false);
            restoreFocus();
          } catch (error) {
            if (error instanceof ApiError) {
              setActionError(error.problem?.detail ?? error.message);
              return;
            }
            setActionError("We couldn't add the member. Try again.");
          }
        }}
      />

      <EditMemberRolesDialog
        open={editingMember !== null}
        member={editingMember}
        roles={rolesQuery.data ?? []}
        isSubmitting={updateRolesMutation.isPending}
        onClose={() => {
          setEditingMember(null);
          setActionError(null);
          restoreFocus();
        }}
        onSubmit={async (membershipId, roleIds) => {
          setActionError(null);
          try {
            await updateRolesMutation.mutateAsync({ membershipId, payload: { role_ids: roleIds } });
            setEditingMember(null);
            restoreFocus();
          } catch (error) {
            if (error instanceof ApiError) {
              setActionError(error.problem?.detail ?? error.message);
              return;
            }
            setActionError("We couldn't update the member's roles. Try again.");
          }
        }}
      />

      <RemoveMemberDialog
        open={memberPendingRemoval !== null}
        member={memberPendingRemoval}
        isSubmitting={removeMemberMutation.isPending}
        onClose={() => {
          setMemberPendingRemoval(null);
          setActionError(null);
          restoreFocus();
        }}
        onConfirm={async (membershipId) => {
          setActionError(null);
          try {
            await removeMemberMutation.mutateAsync(membershipId);
            setMemberPendingRemoval(null);
            restoreFocus();
          } catch (error) {
            if (error instanceof ApiError) {
              setActionError(error.problem?.detail ?? error.message);
              return;
            }
            setActionError("We couldn't remove the member. Try again.");
          }
        }}
      />
    </div>
  );
}

function RoleList({
  member,
  roleMap,
}: {
  member: WorkspaceMember;
  roleMap: Map<string, WorkspaceRoleDefinition>;
}) {
  if (member.roles.length === 0) {
    return <span className="text-xs text-slate-500">workspace-member (default)</span>;
  }

  return (
    <ul className="flex flex-wrap gap-2 text-xs text-slate-200">
      {member.roles.map((role) => {
        const definition = roleMap.get(role);
        return (
          <li key={role} className="rounded border border-slate-800 bg-slate-900 px-2 py-1">
            {definition?.name ?? formatRoleSlug(role)}
          </li>
        );
      })}
    </ul>
  );
}

interface AddMemberDialogProps {
  open: boolean;
  onClose: () => void;
  roles: WorkspaceRoleDefinition[];
  isSubmitting: boolean;
  onSubmit: (payload: { user_id: string; role_ids?: string[] }) => Promise<void>;
}

function AddMemberDialog({ open, onClose, roles, isSubmitting, onSubmit }: AddMemberDialogProps) {
  const [userId, setUserId] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const dialogTitleId = useId();
  const descriptionId = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      setUserId("");
      setSelectedRoleIds([]);
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const focusTarget =
      containerRef.current?.querySelector<HTMLElement>('[data-autofocus]') ??
      containerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
    focusTarget?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedUserId = userId.trim();
    if (!trimmedUserId) {
      setError("Enter the user ID to invite.");
      return;
    }

    try {
      await onSubmit({ user_id: trimmedUserId, role_ids: selectedRoleIds.length > 0 ? selectedRoleIds : undefined });
      setUserId("");
      setSelectedRoleIds([]);
      setError(null);
    } catch {
      // errors are surfaced by the caller via actionError
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={dialogTitleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="w-full max-w-lg rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={dialogTitleId} className="text-xl font-semibold">
              Add workspace member
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-400">
              Provide the user's identifier and optional roles. Members inherit permissions from all assigned roles.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close add workspace member dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="member-user-id" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              User ID
            </label>
            <input
              id="member-user-id"
              name="member-user-id"
              type="text"
              value={userId}
              onChange={(event) => {
                setUserId(event.target.value);
                if (error) {
                  setError(null);
                }
              }}
              disabled={isSubmitting}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
              placeholder="usr_01h7x..."
              data-autofocus="true"
            />
          </div>
          <RoleChecklist
            roles={roles}
            selectedRoleIds={selectedRoleIds}
            onChange={setSelectedRoleIds}
            disabled={isSubmitting}
          />
          <p className="text-xs text-slate-500">
            Leaving all roles unchecked assigns the default workspace-member role.
          </p>
          {error && (
            <p className="text-sm text-rose-300" role="alert">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center rounded bg-sky-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-sky-800 disabled:text-slate-400"
            >
              {isSubmitting ? "Adding…" : "Add member"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface EditMemberRolesDialogProps {
  open: boolean;
  member: WorkspaceMember | null;
  roles: WorkspaceRoleDefinition[];
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (membershipId: string, roleIds: string[]) => Promise<void>;
}

function EditMemberRolesDialog({ open, member, roles, isSubmitting, onClose, onSubmit }: EditMemberRolesDialogProps) {
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const dialogTitleId = useId();
  const descriptionId = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!member) {
      setSelectedRoleIds([]);
      return;
    }

    const availableRolesBySlug = new Map(roles.map((role) => [role.slug, role]));
    const resolvedRoleIds = member.roles
      .map((slug) => availableRolesBySlug.get(slug)?.id)
      .filter((id): id is string => typeof id === "string");
    setSelectedRoleIds(resolvedRoleIds);
  }, [member, roles]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const checkbox = containerRef.current?.querySelector<HTMLInputElement>('input[type="checkbox"]:not([disabled])');
    const focusTarget =
      checkbox ??
      containerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
    focusTarget?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open || !member) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(member.id, selectedRoleIds);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={dialogTitleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="w-full max-w-lg rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={dialogTitleId} className="text-xl font-semibold">
              Edit member roles
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-400">
              Select the roles that apply to {member.user.display_name ?? member.user.email}. Removing all roles assigns the default workspace-member role.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close edit member roles dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <RoleChecklist
            roles={roles}
            selectedRoleIds={selectedRoleIds}
            onChange={setSelectedRoleIds}
            disabled={isSubmitting}
          />
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center rounded bg-sky-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-sky-800 disabled:text-slate-400"
            >
              {isSubmitting ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface RemoveMemberDialogProps {
  open: boolean;
  member: WorkspaceMember | null;
  isSubmitting: boolean;
  onClose: () => void;
  onConfirm: (membershipId: string) => Promise<void>;
}

function RemoveMemberDialog({ open, member, isSubmitting, onClose, onConfirm }: RemoveMemberDialogProps) {
  const dialogTitleId = useId();
  const descriptionId = useId();
  const containerRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const focusTarget =
      containerRef.current?.querySelector<HTMLElement>('[data-autofocus]') ??
      containerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
    focusTarget?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open || !member) {
    return null;
  }

  const displayName = member.user.display_name ?? member.user.email;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onConfirm(member.id);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <form
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={dialogTitleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="w-full max-w-md rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
        onSubmit={handleSubmit}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={dialogTitleId} className="text-xl font-semibold">
              Remove member
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-400">
              Removing {displayName} revokes their access to this workspace. You can re-invite them at any time.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close remove member dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <div className="mt-6 space-y-4 text-sm text-slate-200">
          <p>
            {displayName} currently holds roles:{" "}
            {member.roles.length > 0 ? member.roles.join(", ") : "workspace-member (default)"}.
          </p>
          <p className="text-xs text-slate-500">
            Guardrails prevent removing the last governor, so this action may fail if they are the only remaining workspace administrator.
          </p>
        </div>
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            data-autofocus="true"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center rounded bg-rose-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:bg-rose-900 disabled:text-rose-200"
          >
            {isSubmitting ? "Removing…" : "Remove member"}
          </button>
        </div>
      </form>
    </div>
  );
}

function RoleChecklist({
  roles,
  selectedRoleIds,
  onChange,
  disabled,
}: {
  roles: WorkspaceRoleDefinition[];
  selectedRoleIds: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}) {
  if (roles.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        System roles are loading. The workspace-member role will be assigned by default.
      </p>
    );
  }

  return (
    <fieldset className="space-y-3">
      <legend className="text-xs font-semibold uppercase tracking-wide text-slate-400">Assign roles</legend>
      {roles.map((role) => {
        const checked = selectedRoleIds.includes(role.id);
        return (
          <label key={role.id} className="flex items-start gap-3 text-sm text-slate-200">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-sky-500"
              checked={checked}
              onChange={(event) => {
                if (event.target.checked) {
                  onChange([...selectedRoleIds, role.id]);
                } else {
                  onChange(selectedRoleIds.filter((id) => id !== role.id));
                }
              }}
              disabled={disabled}
            />
            <div>
              <div className="font-medium text-slate-100">{role.name}</div>
              <div className="text-xs text-slate-500">
                {role.is_system ? "System role" : "Custom role"}
                {role.editable ? " • Editable" : " • Locked"}
              </div>
            </div>
          </label>
        );
      })}
    </fieldset>
  );
}
