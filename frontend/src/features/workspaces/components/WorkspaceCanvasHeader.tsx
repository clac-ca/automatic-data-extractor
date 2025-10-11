import { useId } from "react";

import type { WorkspaceProfile } from "../../../shared/api/types";
import { formatRoleSlug } from "../utils/roles";

interface WorkspaceCanvasHeaderProps {
  workspace?: WorkspaceProfile;
}

export function WorkspaceCanvasHeader({ workspace }: WorkspaceCanvasHeaderProps) {
  const headingId = useId();
  const name = workspace?.name ?? "Workspace";
  const subtitleParts = [workspace?.slug ? `Slug: ${workspace.slug}` : null, workspace?.is_default ? "Default" : null].filter(
    Boolean,
  );

  return (
    <section
      className="flex flex-col gap-2 border-b border-slate-900 bg-slate-950/70 px-6 py-5 md:flex-row md:items-center md:justify-between lg:px-8"
      aria-labelledby={headingId}
    >
      <div>
        <h1 id={headingId} className="text-xl font-semibold text-slate-100">
          {name}
        </h1>
        <p className="text-xs text-slate-500">
          {subtitleParts.length > 0
            ? subtitleParts.join(" • ")
            : "Monitor extraction activity, configure processing, and manage workspace access."}
        </p>
      </div>
      {workspace?.roles && workspace.roles.length > 0 ? (
        <ul className="flex flex-wrap items-center gap-2 text-xs text-slate-100">
          {workspace.roles.map((role) => (
            <li
              key={role}
              className="rounded border border-slate-800 bg-slate-950 px-2 py-1 uppercase tracking-wide text-slate-300"
            >
              {formatRoleSlug(role)}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
