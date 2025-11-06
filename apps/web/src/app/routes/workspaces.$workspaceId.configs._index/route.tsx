import { useEffect, useMemo } from "react";
import { useNavigate } from "react-router";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import { useConfigsQuery } from "@shared/configs";
import { createScopedStorage } from "@shared/storage";

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.configs.last`;

type LastSelection = { readonly configId?: string | null } | null;

export const handle = { workspaceSectionId: "configurations" } as const;

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspace.id)), [workspace.id]);
  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });

  useEffect(() => {
    if (!configsQuery.data || configsQuery.data.length === 0) {
      return;
    }
    const stored = storage.get<LastSelection>();
    const configs = configsQuery.data.filter((config) => !config.deleted_at);
    const preferred = stored?.configId
      ? configs.find((config) => config.config_id === stored.configId)
      : undefined;
    const target = preferred ?? configs.find((config) => config.active_version) ?? configs[0];
    if (target) {
      navigate(`${target.config_id}/editor`, { replace: true });
    }
  }, [configsQuery.data, navigate, storage]);

  if (configsQuery.isLoading) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Loading configuration editor…</p>
      </div>
    );
  }

  if (configsQuery.isError) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Unable to load configurations.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm text-slate-600">
      <p>No configurations available yet. Create one from the Configs editor.</p>
    </div>
  );
}
