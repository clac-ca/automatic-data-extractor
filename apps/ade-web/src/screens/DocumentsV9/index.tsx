import { useEffect, useState } from "react";
import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { readPreferredWorkspaceId, useWorkspacesQuery, type WorkspaceProfile } from "@shared/workspaces";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { PageState } from "@ui/PageState";

import { DocumentsBoard } from "./components/DocumentsBoard";
import { BulkActionBar } from "./components/BulkActionBar";
import { DocumentsFiltersBar } from "./components/DocumentsFiltersBar";
import { DocumentsGrid } from "./components/DocumentsGrid";
import { DocumentsHeader } from "./components/DocumentsHeader";
import { DocumentsPreviewPane } from "./components/DocumentsPreviewPane";
import { DocumentsSidebar } from "./components/DocumentsSidebar";
import { SaveViewDialog } from "./components/SaveViewDialog";
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
    if (workspacesQuery.isLoading || workspacesQuery.isError) return;

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

  if (workspacesQuery.isLoading) return <PageState title="Loading Documents" variant="loading" />;

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
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const handleClearFilters = () => {
    model.actions.setSearch("");
    model.actions.clearFilters();
  };

  return (
    <div className="documents-v9 flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <DocumentsHeader
        search={model.state.search}
        onSearchChange={model.actions.setSearch}
        searchRef={model.refs.searchRef}
        viewMode={model.state.viewMode}
        onViewModeChange={model.actions.setViewMode}
        sort={model.state.sort}
        onSortChange={model.actions.setSort}
        onUploadClick={model.actions.handleUploadClick}
        fileInputRef={model.refs.fileInputRef}
        onFileInputChange={model.actions.handleFileInputChange}
        activeViewLabel={model.derived.activeViewLabel}
        showSaveView={model.derived.showSaveView}
        onSaveViewClick={() => setSaveDialogOpen(true)}
      />

      <div className="flex min-h-0 flex-1">
        <DocumentsSidebar
          activeViewKey={model.state.activeViewKey}
          onSelectBuiltIn={model.actions.selectBuiltInView}
          savedViews={model.state.savedViews}
          onSelectSavedView={model.actions.selectSavedView}
          onDeleteSavedView={model.actions.deleteSavedView}
          statusCounts={model.derived.statusCounts}
          now={model.derived.now}
        />

        <div className={clsx("flex min-h-0 min-w-0 flex-1 flex-col", model.state.previewOpen && "lg:flex-row")}>
          <section
            className={clsx(
              "flex min-h-0 min-w-0 flex-1 flex-col",
              model.state.previewOpen && "lg:border-r lg:border-slate-200",
            )}
          >
            <DocumentsFiltersBar
              workspaceId={workspace.id}
              filters={model.state.filters}
              onToggleStatus={model.actions.toggleStatusFilter}
              onToggleFileType={model.actions.toggleFileTypeFilter}
              onSetTagMode={model.actions.setTagMode}
              onToggleTag={model.actions.toggleTagFilter}
              onClearAll={model.actions.clearFilters}
              showingCount={model.derived.visibleDocuments.length}
              totalCount={model.derived.documents.length}
            />

            {model.state.viewMode === "grid" ? (
              <>
                <DocumentsGrid
                  workspaceId={workspace.id}
                  documents={model.derived.visibleDocuments}
                  activeId={model.state.activeId}
                  selectedIds={model.state.selectedIds}
                  onSelect={model.actions.toggleSelect}
                  onSelectAll={model.actions.selectAllVisible}
                  onClearSelection={model.actions.clearSelection}
                  allVisibleSelected={model.derived.allVisibleSelected}
                  onActivate={model.actions.openPreview}
                  onUploadClick={model.actions.handleUploadClick}
                  onClearFilters={handleClearFilters}
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
                  onDownloadOriginal={model.actions.downloadOriginal}
                  onDownloadOutputFromRow={model.actions.downloadOutputFromRow}
                  onReprocess={model.actions.reprocessDocument}
                  onToggleTagOnDocument={model.actions.toggleTagOnDocument}
                />

                <BulkActionBar
                  count={model.state.selectedIds.size}
                  onClear={model.actions.clearSelection}
                  onAddTag={model.actions.bulkAddTagPrompt}
                  onDownloadOriginals={model.actions.bulkDownloadOriginals}
                  onReprocess={model.actions.bulkReprocess}
                />
              </>
            ) : (
                <DocumentsBoard
                  columns={model.derived.boardColumns}
                  groupBy={model.state.groupBy}
                  onGroupByChange={model.actions.setGroupBy}
                  hideEmptyColumns={model.state.hideEmptyColumns}
                  onHideEmptyColumnsChange={model.actions.setHideEmptyColumns}
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
                  onClearFilters={handleClearFilters}
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
              onClose={model.actions.closePreview}
              runs={model.derived.runs}
              runsLoading={model.derived.runsLoading}
              activeRunId={model.state.activeRunId}
              onRunSelect={model.actions.setActiveRunId}
              activeRun={model.derived.activeRun}
              outputUrl={model.derived.outputUrl}
              workbook={model.derived.workbook}
              workbookLoading={model.derived.workbookLoading}
              workbookError={model.derived.workbookError}
              onDownloadOutput={model.actions.downloadOutputFromPreview}
              onDownloadOriginal={model.actions.downloadOriginal}
              onReprocess={model.actions.reprocessDocument}
            />
          ) : null}
        </div>
      </div>

      <SaveViewDialog
        open={saveDialogOpen}
        initialName="My view"
        onCancel={() => setSaveDialogOpen(false)}
        onSave={(name) => {
          model.actions.saveCurrentView(name);
          setSaveDialogOpen(false);
        }}
      />
    </div>
  );
}
