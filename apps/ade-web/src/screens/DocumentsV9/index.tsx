import { useEffect } from "react";
import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { readPreferredWorkspaceId, useWorkspacesQuery, type WorkspaceProfile } from "@shared/workspaces";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { PageState } from "@ui/PageState";

import { DocumentsBoard } from "./components/DocumentsBoard";
import { DocumentsGrid } from "./components/DocumentsGrid";
import { DocumentsHeader } from "./components/DocumentsHeader";
import { DocumentsPreviewPane } from "./components/DocumentsPreviewPane";
import { useDocumentsV9Model } from "./hooks/useDocumentsV9Model";

export default function DocumentsV9Screen() {
  return (
    <RequireSession>
      <DocumentsV9Redirect />
    </RequireSession>
  );
}

function DocumentsV9Redirect() {
  const location = useLocation();
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces: WorkspaceProfile[] = workspacesQuery.data?.items ?? [];

  const preferredIds = [readPreferredWorkspaceId(), session.user.preferred_workspace_id].filter(
    (value): value is string => Boolean(value),
  );
  const preferredWorkspace = preferredIds
    .map((id) => workspaces.find((workspace) => workspace.id === id))
    .find((match) => Boolean(match));

  const targetWorkspace = preferredWorkspace ?? workspaces[0] ?? null;

  useEffect(() => {
    if (workspacesQuery.isLoading || workspacesQuery.isError) {
      return;
    }

    if (!targetWorkspace) {
      navigate("/workspaces", { replace: true });
      return;
    }

    const target = `/workspaces/${targetWorkspace.id}/documents-v9${location.search}${location.hash}`;
    navigate(target, { replace: true });
  }, [
    location.hash,
    location.search,
    navigate,
    targetWorkspace,
    workspacesQuery.isError,
    workspacesQuery.isLoading,
  ]);

  if (workspacesQuery.isLoading) {
    return <PageState title="Loading Documents v9" variant="loading" />;
  }

  if (workspacesQuery.isError) {
    return (
      <PageState title="Unable to load workspaces" description="Refresh the page or try again later." variant="error" />
    );
  }

  return null;
}

export function DocumentsV9Workbench() {
  const session = useSession();
  const { workspace } = useWorkspaceContext();
  const currentUserLabel = session.user.display_name || session.user.email || "You";
  const model = useDocumentsV9Model({ currentUserLabel, workspaceId: workspace.id });

  return (
    <div className="documents-v9 flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <DocumentsHeader
        search={model.state.search}
        onSearchChange={model.actions.setSearch}
        searchRef={model.refs.searchRef}
        viewMode={model.state.viewMode}
        onViewModeChange={model.actions.setViewMode}
        onUploadClick={model.actions.handleUploadClick}
        fileInputRef={model.refs.fileInputRef}
        onFileInputChange={model.actions.handleFileInputChange}
        now={model.derived.now}
        lastSyncedAt={model.derived.lastSyncedAt}
        isRefreshing={model.derived.isRefreshing}
        onRefresh={model.actions.refreshDocuments}
        statusFilter={model.state.statusFilter}
        statusCounts={model.derived.statusCounts}
        filteredTotal={model.derived.filteredTotal}
        onStatusFilterChange={model.actions.setStatusFilter}
        hasFilters={model.derived.hasFilters}
        onClearFilters={model.actions.clearFilters}
      />

      <div className={clsx("flex min-h-0 flex-1 flex-col", model.state.previewOpen && "lg:flex-row")}>
        <section
          className={clsx(
            "flex min-h-0 flex-1 flex-col",
            model.state.previewOpen && "lg:border-r lg:border-slate-200",
          )}
        >
          {model.state.viewMode === "grid" ? (
            <DocumentsGrid
              documents={model.derived.sortedDocuments}
              activeId={model.state.activeId}
              selectedIds={model.state.selectedIds}
              onSelect={model.actions.toggleSelect}
              onSelectAll={model.actions.selectAllVisible}
              onClearSelection={model.actions.clearSelection}
              allVisibleSelected={model.derived.allVisibleSelected}
              onActivate={model.actions.openPreview}
              onUploadClick={model.actions.handleUploadClick}
              onClearFilters={model.actions.clearFilters}
              showNoDocuments={model.derived.showNoDocuments}
              showNoResults={model.derived.showNoResults}
              isLoading={model.derived.isLoading}
              isError={model.derived.isError}
              hasNextPage={model.derived.hasNextPage}
              isFetchingNextPage={model.derived.isFetchingNextPage}
              onLoadMore={model.actions.loadMore}
              onRefresh={model.actions.refreshDocuments}
              now={model.derived.now}
              onKeyNavigate={model.actions.handleKeyNavigate}
              selectedCount={model.derived.selectedCount}
              selectedReadyCount={model.derived.selectedReadyCount}
              onDownloadSelected={model.actions.downloadSelected}
            />
          ) : (
            <DocumentsBoard
              columns={model.derived.boardColumns}
              groupBy={model.state.groupBy}
              onGroupByChange={model.actions.setGroupBy}
              hideEmptyColumns={model.state.boardHideEmpty}
              onHideEmptyColumnsChange={model.actions.setBoardHideEmpty}
              activeId={model.state.activeId}
              onActivate={model.actions.openPreview}
              now={model.derived.now}
              isLoading={model.derived.isLoading}
              isError={model.derived.isError}
              hasNextPage={model.derived.hasNextPage}
              isFetchingNextPage={model.derived.isFetchingNextPage}
              onLoadMore={model.actions.loadMore}
              onRefresh={model.actions.refreshDocuments}
              onUploadClick={model.actions.handleUploadClick}
              onClearFilters={model.actions.clearFilters}
              showNoDocuments={model.derived.showNoDocuments}
              showNoResults={model.derived.showNoResults}
            />
          )}
        </section>

        {model.state.previewOpen ? (
          <DocumentsPreviewPane
            document={model.derived.activeDocument}
            now={model.derived.now}
            activeSheetId={model.state.activeSheetId}
            onSheetChange={model.actions.setActiveSheetId}
            onDownload={model.actions.downloadDocument}
            onClose={model.actions.closePreview}
            activeRun={model.derived.activeRun}
            runLoading={model.derived.runLoading}
            outputUrl={model.derived.outputUrl}
            workbook={model.derived.workbook}
            workbookLoading={model.derived.workbookLoading}
            workbookError={model.derived.workbookError}
          />
        ) : null}
      </div>
    </div>
  );
}
