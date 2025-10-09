import { useOutletContext } from "react-router-dom";

import type { WorkspaceProfile } from "../../../shared/api/types";

interface WorkspaceOutletContext {
  workspace?: WorkspaceProfile;
}

export function WorkspaceOverviewRoute() {
  const { workspace } = useOutletContext<WorkspaceOutletContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace from the navigation to get started.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <header className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-100">Workspace access</h2>
          <p className="text-sm text-slate-300">
            {workspace.role === "owner" ? "You are the owner of this workspace." : "You are a member of this workspace."}
          </p>
        </header>
        <dl className="mt-4 grid gap-4 text-sm text-slate-300 md:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Slug</dt>
            <dd className="mt-1">{workspace.slug || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Default workspace</dt>
            <dd className="mt-1">{workspace.is_default ? "Yes" : "No"}</dd>
          </div>
        </dl>
      </section>
      <section className="space-y-3 rounded border border-slate-800 bg-slate-900/60 p-6">
        <h3 className="text-lg font-semibold text-slate-100">Permissions</h3>
        {workspace.permissions.length > 0 ? (
          <ul className="flex flex-wrap gap-2 text-xs text-slate-200">
            {workspace.permissions.map((permission) => (
              <li key={permission} className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1">
                {permission}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-300">No additional permissions have been granted.</p>
        )}
      </section>
      <section className="space-y-2 rounded border border-slate-800 bg-slate-900/60 p-6">
        <h3 className="text-lg font-semibold text-slate-100">Next steps</h3>
        <p className="text-sm text-slate-300">
          Owners can invite teammates and configure document extraction once workspace management tools are available. For now,
          use this area to review your access and confirm workspace details.
        </p>
      </section>
    </div>
  );
}
