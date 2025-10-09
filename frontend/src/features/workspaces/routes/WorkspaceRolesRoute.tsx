import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRolesQuery";
import { RBAC } from "../../../shared/rbac/permissions";
import { hasPermission } from "../../../shared/rbac/utils";
import { formatRoleSlug } from "../utils/roles";

export function WorkspaceRolesRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to review available roles.
      </div>
    );
  }

  const canManageRoles = hasPermission(workspace.permissions, RBAC.Workspace.Roles.ReadWrite);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id, true);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h2 className="text-lg font-semibold text-slate-100">Role catalog</h2>
        <p className="text-sm text-slate-300">
          Review system and custom roles assigned to members. Custom role management will be enabled once backend APIs are
          available.
        </p>
      </header>

      {rolesQuery.isLoading ? (
        <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">Loading roles…</div>
      ) : rolesQuery.error ? (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-100">
          We were unable to load roles for this workspace.
        </div>
      ) : rolesQuery.data && rolesQuery.data.length > 0 ? (
        <ul className="space-y-4">
          {rolesQuery.data.map((role) => (
            <li key={role.id} className="rounded border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-slate-100">{role.name}</h3>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{formatRoleSlug(role.slug)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300">
                    {role.scope === "global" ? "Global" : "Workspace"}
                  </span>
                  <span
                    className={`rounded border px-2 py-1 ${
                      role.is_system
                        ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
                        : "border-emerald-500/40 bg-emerald-500/10 text-emerald-100"
                    }`}
                  >
                    {role.is_system ? "System" : "Custom"}
                  </span>
                  <span
                    className={`rounded border px-2 py-1 ${
                      role.editable
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-100"
                        : "border-slate-700 bg-slate-900 text-slate-300"
                    }`}
                  >
                    {role.editable ? "Editable" : "Locked"}
                  </span>
                </div>
              </div>
              {role.description && <p className="mt-3 text-sm text-slate-300">{role.description}</p>}
              <div className="mt-4 space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Permissions</h4>
                {role.permissions.length > 0 ? (
                  <ul className="flex flex-wrap gap-2 text-xs text-slate-200">
                    {role.permissions.map((permission) => (
                      <li key={permission} className="rounded border border-slate-800 bg-slate-950 px-2 py-1">
                        {permission}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-500">No permissions assigned yet.</p>
                )}
              </div>
              {canManageRoles && (
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                  <button
                    type="button"
                    disabled
                    className="cursor-not-allowed rounded border border-slate-800 bg-slate-900 px-3 py-2 font-medium text-slate-500"
                    title="Custom role editing will be available once APIs ship."
                  >
                    Edit role
                  </button>
                  <button
                    type="button"
                    disabled
                    className="cursor-not-allowed rounded border border-slate-800 bg-slate-900 px-3 py-2 font-medium text-slate-500"
                    title="Role deletion will be enabled once backend support is added."
                  >
                    Delete role
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
          No roles are defined for this workspace yet.
        </div>
      )}
    </div>
  );
}
