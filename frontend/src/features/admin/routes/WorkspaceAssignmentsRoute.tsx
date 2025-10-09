import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../../shared/api/client";
import type { RoleAssignment, RoleDefinition, UserSummary } from "../../../shared/api/types";
import { useWorkspacesQuery } from "../../workspaces/hooks/useWorkspacesQuery";
import { useWorkspaceRolesQuery } from "../../workspaces/hooks/useWorkspaceRolesQuery";
import { useUsersQuery } from "../hooks/useUsersQuery";
import { useWorkspaceAssignmentsQuery } from "../hooks/useWorkspaceAssignmentsQuery";
import {
  useCreateWorkspaceAssignmentMutation,
  useDeleteWorkspaceAssignmentMutation,
} from "../hooks/useAssignmentMutations";

export function WorkspaceAssignmentsRoute() {
  const workspacesQuery = useWorkspacesQuery();
  const usersQuery = useUsersQuery();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedWorkspaceId && workspacesQuery.data && workspacesQuery.data.length > 0) {
      setSelectedWorkspaceId(workspacesQuery.data[0].id);
    }
  }, [selectedWorkspaceId, workspacesQuery.data]);

  const rolesQuery = useWorkspaceRolesQuery(selectedWorkspaceId, Boolean(selectedWorkspaceId));
  const assignmentsQuery = useWorkspaceAssignmentsQuery(selectedWorkspaceId);
  const createAssignment = useCreateWorkspaceAssignmentMutation(selectedWorkspaceId);
  const deleteAssignment = useDeleteWorkspaceAssignmentMutation(selectedWorkspaceId);

  const assignableRoles = useMemo(() => {
    if (!rolesQuery.data) {
      return [] as RoleDefinition[];
    }
    return rolesQuery.data.filter((role) => role.scope_type === "workspace");
  }, [rolesQuery.data]);

  const users = usersQuery.data ?? [];
  const assignments = assignmentsQuery.data ?? [];

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!selectedWorkspaceId) {
      setFormError("Select a workspace.");
      return;
    }
    if (!selectedUserId) {
      setFormError("Select a user to assign.");
      return;
    }
    if (!selectedRoleId) {
      setFormError("Select a role to assign.");
      return;
    }

    try {
      await createAssignment.mutateAsync({ role_id: selectedRoleId, user_id: selectedUserId });
      setSelectedRoleId("");
      setSelectedUserId("");
    } catch (error) {
      const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to assign workspace role.";
      setFormError(message);
    }
  };

  const handleDelete = async (assignment: RoleAssignment) => {
    setActionError(null);
    try {
      await deleteAssignment.mutateAsync(assignment.id);
    } catch (error) {
      const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to remove assignment.";
      setActionError(message);
    }
  };

  if (workspacesQuery.isLoading || usersQuery.isLoading || rolesQuery.isLoading || assignmentsQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading workspace assignments…</p>;
  }

  if (workspacesQuery.error) {
    return <p className="text-sm text-rose-200">We couldn't load workspaces.</p>;
  }

  const workspaces = workspacesQuery.data ?? [];

  if (workspaces.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">No workspaces available</h2>
        <p className="text-sm text-slate-400">
          Create a workspace before assigning workspace-scoped roles.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="md:col-span-1">
            <label htmlFor="workspace-select" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              Workspace
            </label>
            <select
              id="workspace-select"
              value={selectedWorkspaceId}
              onChange={(event) => {
                setSelectedWorkspaceId(event.target.value);
                setSelectedRoleId("");
                setSelectedUserId("");
                setFormError(null);
                setActionError(null);
              }}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <header>
          <h2 className="text-lg font-semibold text-slate-100">Assign workspace roles</h2>
          <p className="text-sm text-slate-400">
            Assign workspace owners or members by granting workspace-scoped roles directly.
          </p>
        </header>
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-3">
          <div className="md:col-span-1">
            <label htmlFor="workspace-assignment-user" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              User
            </label>
            <select
              id="workspace-assignment-user"
              value={selectedUserId}
              onChange={(event) => {
                setSelectedUserId(event.target.value);
                if (formError) setFormError(null);
              }}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            >
              <option value="">Select a user…</option>
              {users.map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {formatUserLabel(user)}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-1">
            <label htmlFor="workspace-assignment-role" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              Role
            </label>
            <select
              id="workspace-assignment-role"
              value={selectedRoleId}
              onChange={(event) => {
                setSelectedRoleId(event.target.value);
                if (formError) setFormError(null);
              }}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            >
              <option value="">Select a role…</option>
              {assignableRoles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end md:col-span-1">
            <button
              type="submit"
              className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
              disabled={createAssignment.isPending || !selectedWorkspaceId}
            >
              Assign role
            </button>
          </div>
        </form>
        {formError && <p className="text-sm text-rose-200" role="alert">{formError}</p>}
      </section>

      <section className="space-y-3">
        <header>
          <h3 className="text-lg font-semibold text-slate-100">Current assignments</h3>
          <p className="text-sm text-slate-400">Assignments reflect workspace roles granted to each user.</p>
        </header>
        {assignments.length === 0 ? (
          <p className="text-sm text-slate-300">No assignments for this workspace.</p>
        ) : (
          <div className="overflow-hidden rounded border border-slate-800">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead className="bg-slate-900/70 text-left text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-semibold">User</th>
                  <th className="px-4 py-3 font-semibold">Role</th>
                  <th className="px-4 py-3 font-semibold">Created</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900 bg-slate-950/60 text-slate-200">
                {assignments.map((assignment) => (
                  <AssignmentRow
                    key={assignment.id}
                    assignment={assignment}
                    role={findRole(assignment.role_id, assignableRoles)}
                    onDelete={() => handleDelete(assignment)}
                    isDeleting={deleteAssignment.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {actionError && <p className="text-sm text-rose-200" role="alert">{actionError}</p>}
      </section>
    </div>
  );
}

function AssignmentRow({
  assignment,
  role,
  onDelete,
  isDeleting,
}: {
  assignment: RoleAssignment;
  role: RoleDefinition | undefined;
  onDelete: () => Promise<void>;
  isDeleting: boolean;
}) {
  return (
    <tr>
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-slate-100">{assignment.user_display_name ?? assignment.user_email ?? assignment.principal_id}</div>
        {assignment.user_email && <div className="text-xs text-slate-500">{assignment.user_email}</div>}
      </td>
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-slate-100">{role?.name ?? assignment.role_slug}</div>
        <div className="text-xs text-slate-500">{assignment.role_slug}</div>
      </td>
      <td className="px-4 py-3 align-top text-xs text-slate-400">{new Date(assignment.created_at).toLocaleString()}</td>
      <td className="px-4 py-3 align-top text-right text-xs">
        <button
          type="button"
          onClick={onDelete}
          disabled={isDeleting}
          className="rounded border border-transparent px-2 py-1 font-medium text-rose-200 transition hover:text-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Remove
        </button>
      </td>
    </tr>
  );
}

function findRole(roleId: string, roles: RoleDefinition[]) {
  return roles.find((role) => role.id === roleId);
}

function formatUserLabel(user: UserSummary) {
  const parts = [user.display_name ?? user.email];
  if (user.display_name && user.display_name !== user.email) {
    parts.push(`<${user.email}>`);
  }
  return parts.join(" ");
}
