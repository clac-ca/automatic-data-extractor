import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { LoadingState } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceProfile } from "@/types/workspaces";

import { settingsPaths } from "../../routing/contracts";
import { SettingsCommandBar, SettingsDataTable, SettingsEmptyState, SettingsListLayout, useSettingsListState } from "../../shared";

export function WorkspaceListPage({
  workspaces,
  isLoading,
}: {
  readonly workspaces: readonly WorkspaceProfile[];
  readonly isLoading: boolean;
}) {
  const navigate = useNavigate();
  const listState = useSettingsListState({
    defaults: { sort: "name", order: "asc", pageSize: 25 },
  });

  const filteredWorkspaces = useMemo(() => {
    const term = listState.state.q.trim().toLowerCase();
    const ordered = [...workspaces].sort((a, b) => {
      const key = listState.state.sort === "slug" ? "slug" : "name";
      const left = a[key].toLowerCase();
      const right = b[key].toLowerCase();
      const direction = listState.state.order === "desc" ? -1 : 1;
      return left.localeCompare(right) * direction;
    });

    if (!term) {
      return ordered;
    }
    return ordered.filter((workspace) => `${workspace.name} ${workspace.slug}`.toLowerCase().includes(term));
  }, [listState.state.order, listState.state.q, listState.state.sort, workspaces]);

  return (
    <SettingsListLayout
      title="Workspaces"
      subtitle="Select a workspace to manage processing, access principals, roles, invitations, and lifecycle controls."
      breadcrumbs={[{ label: "Settings", href: settingsPaths.home }, { label: "Workspaces" }]}
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search workspaces"
        />
      }
    >
      {isLoading ? <LoadingState title="Loading workspaces" className="min-h-[220px]" /> : null}
      {!isLoading && workspaces.length === 0 ? (
        <SettingsEmptyState
          title="No workspaces"
          description="You do not currently have workspace administration access."
        />
      ) : null}

      {!isLoading && filteredWorkspaces.length > 0 ? (
        <SettingsDataTable
          rows={filteredWorkspaces}
          columns={[
            {
              id: "workspace",
              header: "Workspace",
              cell: (workspace) => <p className="font-medium text-foreground">{workspace.name}</p>,
            },
            {
              id: "slug",
              header: "Slug",
              cell: (workspace) => <p className="text-muted-foreground">{workspace.slug}</p>,
            },
            {
              id: "default",
              header: "Default",
              cell: (workspace) =>
                workspace.is_default ? (
                  <Badge variant="secondary">Default</Badge>
                ) : (
                  <span className="text-muted-foreground">-</span>
                ),
            },
          ]}
          getRowId={(workspace) => workspace.id}
          onRowOpen={(workspace) =>
            navigate(listState.withCurrentSearch(settingsPaths.workspaces.general(workspace.id)))
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={filteredWorkspaces.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey="settings-workspaces-list-row"
        />
      ) : null}
      {!isLoading && workspaces.length > 0 && filteredWorkspaces.length === 0 ? (
        <SettingsEmptyState
          title="No workspaces match this search"
          description="Try a different search term."
        />
      ) : null}
    </SettingsListLayout>
  );
}
