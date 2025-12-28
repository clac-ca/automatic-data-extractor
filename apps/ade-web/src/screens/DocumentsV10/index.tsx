import { useCallback, useEffect, useMemo, useState } from "react";

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
import { SaveViewDialog } from "./components/SaveViewDialog";
import { useDocumentsV10Model } from "./hooks/useDocumentsV10Model";

export default function DocumentsV10Screen() {
  return (
    <RequireSession>
      <DocumentsV10Redirect />
    </RequireSession>
  );
}

function DocumentsV10Redirect() {
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

    const target = `/workspaces/${targetWorkspace.id}/documents-v10${location.search}${location.hash}`;
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

export function DocumentsV10Workbench() {
  const session = useSession();
  const { workspace } = useWorkspaceContext();
  const location = useLocation();
  const navigate = useNavigate();

  const currentUserLabel = session.user.display_name || session.user.email || "You";
  const currentUserId = session.user.id;

  const model = useDocumentsV10Model({ currentUserLabel, currentUserId, workspaceId: workspace.id });
  const [detailsRequestId, setDetailsRequestId] = useState<string | null>(null);
  const handleClearFilters = () => {
    setSearchParam("");
    model.actions.setSearch("");
    model.actions.setBuiltInView("all");
  };

  const urlSearch = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("q") ?? "";
  }, [location.search]);

  const urlDocId = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("doc");
  }, [location.search]);

  useEffect(() => {
    if (urlSearch !== model.state.search) {
      model.actions.setSearch(urlSearch);
    }
  }, [model.actions.setSearch, model.state.search, urlSearch]);

  useEffect(() => {
    if (!urlDocId) return;
    model.actions.openPreview(urlDocId);
  }, [urlDocId]);

  const setSearchParam = useCallback(
    (value: string, replace = true) => {
      const params = new URLSearchParams(location.search);
      if (value) {
        params.set("q", value);
      } else {
        params.delete("q");
      }
      const nextSearch = params.toString();
      const target = `${location.pathname}${nextSearch ? `?${nextSearch}` : ""}${location.hash ?? ""}`;
      navigate(target, { replace });
    },
    [location.hash, location.pathname, location.search, navigate],
  );

  const setDocParam = (docId: string | null, replace = false) => {
    const params = new URLSearchParams(location.search);
    if (docId) params.set("doc", docId);
    else params.delete("doc");
    const nextSearch = params.toString();
    const target = `${location.pathname}${nextSearch ? `?${nextSearch}` : ""}${location.hash ?? ""}`;
    navigate(target, { replace });
  };

  const onActivate = (id: string) => {
    if (model.state.activeId === id && model.state.previewOpen) {
      onClosePreview();
      return;
    }
    const hadDoc = Boolean(urlDocId);
    setDocParam(id, hadDoc);
    model.actions.openPreview(id);
  };

  const onClosePreview = () => {
    setDocParam(null, false);
    model.actions.closePreview();
    setDetailsRequestId(null);
  };

  const onOpenDetails = useCallback(
    (id: string) => {
      const hadDoc = Boolean(urlDocId);
      setDocParam(id, hadDoc);
      model.actions.openPreview(id);
      setDetailsRequestId(id);
    },
    [model.actions, setDocParam, urlDocId],
  );

  return (
    <div className="documents-v10 flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <DocumentsHeader
        viewMode={model.state.viewMode}
        onViewModeChange={model.actions.setViewMode}
        onUploadClick={model.actions.handleUploadClick}
        fileInputRef={model.refs.fileInputRef}
        onFileInputChange={model.actions.handleFileInputChange}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <DocumentsFiltersBar
            workspaceId={workspace.id}
            filters={model.state.filters}
            onChange={model.actions.setFilters}
            people={model.derived.people}
            showingCount={model.derived.visibleDocuments.length}
            totalCount={model.derived.documents.length}
            activeViewId={model.state.activeViewId}
            onSetBuiltInView={(id) => model.actions.setBuiltInView(id)}
            savedViews={model.derived.savedViews}
            onSelectSavedView={(id) => model.actions.selectSavedView(id)}
            onDeleteSavedView={(id) => model.actions.deleteView(id)}
            onOpenSaveDialog={model.actions.openSaveView}
            counts={model.derived.counts}
          />

          {model.state.viewMode === "grid" ? (
            <>
              <DocumentsGrid
                documents={model.derived.visibleDocuments}
                activeId={model.state.activeId}
                selectedIds={model.state.selectedIds}
                onSelect={model.actions.toggleSelect}
                onSelectAll={model.actions.selectAllVisible}
                onClearSelection={model.actions.clearSelection}
                allVisibleSelected={model.derived.allVisibleSelected}
                onActivate={onActivate}
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
                people={model.derived.people}
                onAssign={model.actions.assignDocument}
                onPickUp={model.actions.pickUpDocument}
                onDownloadOriginal={model.actions.downloadOriginal}
                onDownloadOutput={model.actions.downloadOutputFromRow}
                onCopyLink={model.actions.copyLink}
                onReprocess={(doc) => model.actions.reprocess(doc)}
                onOpenDetails={onOpenDetails}
                onClosePreview={onClosePreview}
                expandedId={model.state.previewOpen ? model.state.activeId : null}
                expandedContent={
                  model.state.previewOpen ? (
                    <DocumentsPreviewPane
                      workspaceId={workspace.id}
                      document={model.derived.activeDocument}
                      now={model.derived.now}
                      activeSheetId={model.state.activeSheetId}
                      onSheetChange={model.actions.setActiveSheetId}
                      runs={model.derived.runs}
                      runsLoading={model.derived.runsLoading}
                      selectedRunId={model.derived.selectedRunId}
                      onSelectRun={model.actions.selectRun}
                      activeRun={model.derived.activeRun}
                      runLoading={model.derived.runLoading}
                      outputUrl={model.derived.outputUrl}
                      onDownloadOutput={model.actions.downloadOutput}
                      onDownloadOriginal={model.actions.downloadOriginal}
                      onReprocess={model.actions.reprocess}
                      people={model.derived.people}
                      currentUserKey={model.derived.currentUserKey}
                      currentUserLabel={currentUserLabel}
                      onAssign={model.actions.assignDocument}
                      onPickUp={model.actions.pickUpDocument}
                      onCopyLink={model.actions.copyLink}
                      comments={model.derived.activeComments}
                      onAddComment={model.actions.addComment}
                      onEditComment={model.actions.editComment}
                      onDeleteComment={model.actions.deleteComment}
                      onTagsChange={model.actions.updateTagsOptimistic}
                      workbook={model.derived.workbook}
                      workbookLoading={model.derived.workbookLoading}
                      workbookError={model.derived.workbookError}
                      onClose={onClosePreview}
                      detailsRequestId={detailsRequestId}
                      onDetailsRequestHandled={() => setDetailsRequestId(null)}
                    />
                  ) : null
                }
              />

              <BulkActionBar
                count={model.state.selectedIds.size}
                onClear={model.actions.clearSelection}
                onAddTag={model.actions.bulkAddTagPrompt}
                onDownloadOriginals={model.actions.bulkDownloadOriginals}
                onDownloadOutputs={model.actions.bulkDownloadOutputs}
              />
            </>
          ) : (
            <>
              <DocumentsBoard
                columns={model.derived.boardColumns}
                groupBy={model.state.groupBy}
                onGroupByChange={model.actions.setGroupBy}
                activeId={model.state.previewOpen ? model.state.activeId : null}
                onActivate={onActivate}
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
                people={model.derived.people}
                onAssign={model.actions.assignDocument}
                onPickUp={model.actions.pickUpDocument}
              />
              {model.state.previewOpen ? (
                <div className="border-t border-border bg-background px-6 pb-6 pt-4">
                  <div className="rounded-2xl border border-border bg-card shadow-sm">
                    <DocumentsPreviewPane
                      workspaceId={workspace.id}
                      document={model.derived.activeDocument}
                      now={model.derived.now}
                      activeSheetId={model.state.activeSheetId}
                      onSheetChange={model.actions.setActiveSheetId}
                      runs={model.derived.runs}
                      runsLoading={model.derived.runsLoading}
                      selectedRunId={model.derived.selectedRunId}
                      onSelectRun={model.actions.selectRun}
                      activeRun={model.derived.activeRun}
                      runLoading={model.derived.runLoading}
                      outputUrl={model.derived.outputUrl}
                      onDownloadOutput={model.actions.downloadOutput}
                      onDownloadOriginal={model.actions.downloadOriginal}
                      onReprocess={model.actions.reprocess}
                      people={model.derived.people}
                      currentUserKey={model.derived.currentUserKey}
                      currentUserLabel={currentUserLabel}
                      onAssign={model.actions.assignDocument}
                      onPickUp={model.actions.pickUpDocument}
                      onCopyLink={model.actions.copyLink}
                      comments={model.derived.activeComments}
                      onAddComment={model.actions.addComment}
                      onEditComment={model.actions.editComment}
                      onDeleteComment={model.actions.deleteComment}
                      onTagsChange={model.actions.updateTagsOptimistic}
                      workbook={model.derived.workbook}
                      workbookLoading={model.derived.workbookLoading}
                      workbookError={model.derived.workbookError}
                      onClose={onClosePreview}
                      detailsRequestId={detailsRequestId}
                      onDetailsRequestHandled={() => setDetailsRequestId(null)}
                    />
                  </div>
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>

      <SaveViewDialog open={model.state.saveViewOpen} onClose={model.actions.closeSaveView} onSave={model.actions.saveView} />
    </div>
  );
}
