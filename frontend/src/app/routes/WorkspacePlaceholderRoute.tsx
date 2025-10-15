import { Link } from "react-router-dom";

import { getWorkspacePlaceholder } from "../workspaces/sections";

interface WorkspacePlaceholderRouteProps {
  readonly sectionId: string;
}

export function WorkspacePlaceholderRoute({ sectionId }: WorkspacePlaceholderRouteProps) {
  const entry = getWorkspacePlaceholder(sectionId);

  return (
    <div className="space-y-4 text-sm text-slate-600">
      <div className="space-y-2">
        <h2 id="page-title" className="text-2xl font-semibold text-slate-900">{entry.title}</h2>
        <p className="leading-relaxed">{entry.description}</p>
      </div>
      {entry.cta ? (
        <Link
          to={entry.cta.href}
          className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          {entry.cta.label}
        </Link>
      ) : null}
    </div>
  );
}
