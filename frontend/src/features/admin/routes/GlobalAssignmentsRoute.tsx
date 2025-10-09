import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../../shared/api/client";
import type { RoleAssignment, RoleDefinition, UserSummary } from "../../../shared/api/types";
import { useGlobalAssignmentsQuery } from "../hooks/useGlobalAssignmentsQuery";
import { useCreateGlobalAssignmentMutation, useDeleteGlobalAssignmentMutation } from "../hooks/useAssignmentMutations";
import { useGlobalRolesQuery } from "../hooks/useGlobalRolesQuery";
import { useUsersQuery } from "../hooks/useUsersQuery";

export function GlobalAssignmentsRoute() {
  const assignmentsQuery = useGlobalAssignmentsQuery();
  const rolesQuery = useGlobalRolesQuery();
  const usersQuery = useUsersQuery();
  const createAssignment = useCreateGlobalAssignmentMutation();
  const deleteAssignment = useDeleteGlobalAssignmentMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);

  const assignableRoles = useMemo(() => {
    return (rolesQuery.data ?? []).filter((role) => role.scope_type === "global");
  }, [rolesQuery.data]);

  const users = usersQuery.data ?? [];
  const assignments = assignmentsQuery.data ?? [];

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
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
      const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to assign role.";
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

  if (assignmentsQuery.isLoading || rolesQuery.isLoading || usersQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading assignments…</p>;
  }

  if (assignmentsQuery.error) {
    return <p className="text-sm text-rose-200">We couldn't load role assignments.</p>;
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold text-slate-100">Assign global roles</h2>
        <p className="text-sm text-slate-400">Grant administrator roles to users across the tenant.</p>
        <form onSubmit={handleSubmit} className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="md:col-span-1">
            <label htmlFor="assignment-user" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              User
            </label>
            <select
              id="assignment-user"
              value={selectedUserId}
              onChange={(event) => {
                setSelectedUserId(event.target.value);
                if (formError) {
                  setFormError(null);
                }
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
            <label htmlFor="assignment-role" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              Role
            </label>
            <select
              id="assignment-role"
              value={selectedRoleId}
              onChange={(event) => {
                setSelectedRoleId(event.target.value);
                if (formError) {
                  setFormError(null);
                }
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
              disabled={createAssignment.isPending}
            >
              Assign role
            </button>
          </div>
        </form>
        {formError && <p className="mt-2 text-sm text-rose-200" role="alert">{formError}</p>}
      </section>

      <section className="space-y-3">
        <header>
          <h3 className="text-lg font-semibold text-slate-100">Current assignments</h3>
          <p className="text-sm text-slate-400">Assignments show the user, role, and when the grant was created.</p>
        </header>
        {assignments.length === 0 ? (
          <p className="text-sm text-slate-300">No global role assignments yet.</p>
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
