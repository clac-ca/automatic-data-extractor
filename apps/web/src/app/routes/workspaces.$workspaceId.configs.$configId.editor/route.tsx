import { useEffect, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import { findActiveVersion, useConfigVersionsQuery } from "@shared/configs";

export const handle = { workspaceSectionId: "configurations" } as const;

export default function WorkspaceConfigEditorRedirectRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const params = useParams<{ configId: string }>();
  const [searchParams] = useSearchParams();
  const configId = params.configId ?? "";

  const versionsQuery = useConfigVersionsQuery({
    workspaceId: workspace.id,
    configId,
    includeDeleted: false,
    enabled: Boolean(configId),
  });

  const targetVersionId = useMemo(() => {
    if (!versionsQuery.data || versionsQuery.data.length === 0) {
      return null;
    }
    const active = findActiveVersion(versionsQuery.data);
    if (active) {
      return active.config_version_id;
    }
    return versionsQuery.data[0]?.config_version_id ?? null;
  }, [versionsQuery.data]);

  useEffect(() => {
    if (!configId || !targetVersionId) {
      return;
    }
    navigate({ pathname: targetVersionId, search: searchParams.toString() }, { replace: true, relative: "path" });
  }, [configId, navigate, searchParams, targetVersionId]);

  if (versionsQuery.isLoading) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Loading configuration editor…</p>
      </div>
    );
  }

  if (versionsQuery.isError) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Unable to load configuration versions.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm text-slate-600">
      <p>No configuration versions are available yet. Create one to begin editing.</p>
    </div>
  );
}
