import { redirect, type LoaderFunctionArgs } from "react-router-dom";

import { fetchWorkspaces } from "../../features/workspaces/api";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import { defaultWorkspaceSection } from "./sections";

export interface WorkspaceLoaderData {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: WorkspaceProfile[];
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | undefined | null) {
  if (!identifier) {
    return workspaces[0] ?? null;
  }

  return (
    workspaces.find((workspace) => workspace.id === identifier) ??
    workspaces.find((workspace) => workspace.slug === identifier) ??
    workspaces[0] ??
    null
  );
}

function buildCanonicalPath(requestUrl: string, currentId: string | undefined, resolvedId: string) {
  const url = new URL(requestUrl);
  const pathname = url.pathname;
  const search = url.search;

  const baseSegment = currentId ? `/workspaces/${currentId}` : "/workspaces";
  const trailing = pathname.startsWith(baseSegment) ? pathname.slice(baseSegment.length) : "";
  const normalisedTrailing = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;

  return `/workspaces/${resolvedId}${normalisedTrailing}${search}`;
}

export async function workspaceLoader({ params, request }: LoaderFunctionArgs): Promise<WorkspaceLoaderData> {
  const workspaces = await fetchWorkspaces(request.signal);

  if (workspaces.length === 0) {
    throw redirect("/workspaces");
  }

  const resolved = findWorkspace(workspaces, params.workspaceId);

  if (!resolved) {
    throw redirect("/workspaces");
  }

  if (!params.workspaceId || params.workspaceId !== resolved.id) {
    const canonicalPath = buildCanonicalPath(request.url, params.workspaceId, resolved.id);
    throw redirect(canonicalPath);
  }

  return { workspace: resolved, workspaces };
}

export function getDefaultWorkspacePath(workspaceId: string) {
  return `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}`;
}
