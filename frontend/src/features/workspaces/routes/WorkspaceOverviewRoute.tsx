import { useOutletContext } from "react-router-dom";

import { formatDateTime } from "../../../shared/dates";
import type { WorkspaceSummary } from "../../../shared/api/types";

interface WorkspaceOutletContext {
  workspace?: WorkspaceSummary;
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

  if (workspace.document_types.length === 0) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        No document types are configured yet. Published document types will appear here.
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {workspace.document_types.map((documentType) => (
        <section key={documentType.id} className="space-y-4 rounded border border-slate-800 bg-slate-900/60 p-6">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">{documentType.display_name}</h2>
              <p className="text-xs uppercase tracking-wide text-slate-500">{documentType.status}</p>
            </div>
            <a
              href={`/workspaces/${workspace.id}/document-types/${documentType.id}`}
              className="text-sm font-medium text-sky-300 hover:text-sky-200"
            >
              View details
            </a>
          </header>
          <dl className="grid gap-4 text-sm text-slate-300">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Last run</dt>
              <dd className="mt-1">{formatDateTime(documentType.last_run_at)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Active configuration</dt>
              <dd className="mt-1">{documentType.active_configuration_id}</dd>
            </div>
          </dl>
          {documentType.recent_alerts && documentType.recent_alerts.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-rose-300">Recent alerts</p>
              <ul className="space-y-1 text-sm text-rose-200">
                {documentType.recent_alerts.map((alert, index) => (
                  <li key={index} className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2">
                    {alert}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
