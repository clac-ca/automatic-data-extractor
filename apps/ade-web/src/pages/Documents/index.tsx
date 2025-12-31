import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";

import { useLocation, useNavigate } from "@app/navigation/history";
import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { usePresenceChannel, type PresenceParticipant } from "@hooks/presence";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { readPreferredWorkspaceId } from "@utils/workspaces";
import type { WorkspaceProfile } from "@schema/workspaces";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { ConfirmDialog } from "@components/ui/confirm-dialog";
import { PageState } from "@components/layouts/page-state";

import { DocumentsBoard } from "./components/DocumentsBoard";
import { BulkActionBar } from "./components/BulkActionBar";
import { BulkTagDialog } from "./components/BulkTagDialog";
import { DocumentsFiltersBar } from "./components/DocumentsFiltersBar";
import { DocumentsGrid } from "./components/DocumentsGrid";
import { DocumentsHeader } from "./components/DocumentsHeader";
import { DocumentsPreviewPane } from "./components/DocumentsPreviewPane";
import { SaveViewDialog } from "./components/SaveViewDialog";
import { UploadPreflightDialog } from "./components/UploadPreflightDialog";
import { useDocumentsModel } from "./hooks/useDocumentsModel";
import { getDocumentOutputRun } from "./data";
import type { DocumentEntry, DocumentsFilters, DocumentStatus, FileType } from "./types";
import {
  DEFAULT_DOCUMENT_FILTERS,
  assigneeKeysFromIds,
  buildFiltersForBuiltInView,
  filtersEqual,
  normalizeAssignees,
  type BuiltInViewId,
} from "./filters";

export default function DocumentsScreen() {
  return (
    <RequireSession>
      <DocumentsRedirect />
    </RequireSession>
  );
}

const STATUS_VALUES = new Set<DocumentStatus>(["queued", "processing", "ready", "failed", "archived"]);
const FILE_TYPE_VALUES = new Set<FileType>(["xlsx", "xls", "csv", "pdf"]);

function parseFiltersFromSearch(search: string): DocumentsFilters {
  const params = new URLSearchParams(search);
  const statuses = filterAllowed(
    readParamList(params, ["status", "status_in", "display_status", "display_status_in"]),
    STATUS_VALUES,
  );
  const fileTypes = filterAllowed(readParamList(params, ["file_type"]), FILE_TYPE_VALUES);
  const tags = readParamList(params, ["tags"]);
  const rawTagMode = coerceTagMode(params.get("tag_mode") ?? params.get("tags_match"));
  const tagMode = tags.length > 0 ? rawTagMode : "any";
  const assigneeIds = readParamList(params, ["assignee_user_id", "assignee_user_id_in"]);
  const includeUnassigned = parseBooleanParam(params.get("assignee_unassigned"));
  const assignees = assigneeKeysFromIds(assigneeIds, includeUnassigned);

  return {
    ...DEFAULT_DOCUMENT_FILTERS,
    statuses,
    fileTypes,
    tags,
    tagMode,
    assignees,
  };
}

function buildDocumentsSearchParams(filters: DocumentsFilters, search: string, docId: string | null) {
  const params = new URLSearchParams();
  const trimmedSearch = search.trim();
  if (trimmedSearch) params.set("q", trimmedSearch);
  if (docId) params.set("doc", docId);

  filters.statuses.forEach((status) => params.append("status", status));
  filters.fileTypes.forEach((type) => params.append("file_type", type));
  filters.tags.forEach((tag) => params.append("tags", tag));
  if (filters.tags.length > 0 && filters.tagMode !== "any") {
    params.set("tag_mode", filters.tagMode);
  }

  const { assigneeIds, includeUnassigned } = normalizeAssignees(filters.assignees);
  assigneeIds.forEach((id) => params.append("assignee_user_id", id));
  if (includeUnassigned) {
    params.set("assignee_unassigned", "true");
  }

  return params.toString();
}

function coerceTagMode(value: string | null): DocumentsFilters["tagMode"] {
  return value === "all" ? "all" : "any";
}

function parseBooleanParam(value: string | null) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "true" || normalized === "1" || normalized === "yes" || normalized === "on";
}

function readParamList(params: URLSearchParams, keys: string[]): string[] {
  const values = keys.flatMap((key) => params.getAll(key));
  const parsed = values
    .flatMap((value) => value.split(","))
    .map((value) => value.trim())
    .filter(Boolean);
  return Array.from(new Set(parsed));
}

function filterAllowed<T extends string>(values: string[], allowed: Set<T>): T[] {
  return values.filter((value): value is T => allowed.has(value as T));
}

function DocumentsRedirect() {
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

    const target = `/workspaces/${targetWorkspace.id}/documents${location.search}${location.hash}`;
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

export function DocumentsWorkbench() {
  const session = useSession();
  const { workspace, hasPermission } = useWorkspaceContext();
  const location = useLocation();
  const navigate = useNavigate();

  const currentUserLabel = session.user.display_name || session.user.email || "You";
  const currentUserId = session.user.id;
  const currentUserKey = `user:${currentUserId}`;
  const canManageConfigurations = hasPermission("workspace.configurations.manage");
  const canManageSettings = hasPermission("workspace.settings.manage");

  const urlFilters = useMemo(() => parseFiltersFromSearch(location.search), [location.search]);

  const model = useDocumentsModel({
    currentUserLabel,
    currentUserId,
    workspaceId: workspace.id,
    processingPaused: workspace.processing_paused ?? false,
    initialFilters: urlFilters,
  });
  const presenceContext = useMemo(() => ({ screen: "documents" }), []);
  const presence = usePresenceChannel({
    workspaceId: workspace.id,
    scope: "documents",
    context: presenceContext,
  });
  const activeParticipants = useMemo(() => {
    const seen = new Set<string>();
    const deduped: PresenceParticipant[] = [];
    presence.participants.forEach((participant) => {
      if (seen.has(participant.user_id)) return;
      seen.add(participant.user_id);
      deduped.push(participant);
    });
    return deduped;
  }, [presence.participants]);

  const presenceByDocument = useMemo(() => {
    const map: Record<string, PresenceParticipant[]> = {};
    const seenByDocument = new Map<string, Set<string>>();
    presence.participants.forEach((participant) => {
      const selection = participant.selection;
      if (!selection || typeof selection !== "object") return;
      const docId = (selection as { doc_id?: unknown }).doc_id;
      if (typeof docId !== "string" || !docId) return;
      let seen = seenByDocument.get(docId);
      if (!seen) {
        seen = new Set();
        seenByDocument.set(docId, seen);
      }
      if (seen.has(participant.user_id)) return;
      seen.add(participant.user_id);
      (map[docId] ??= []).push(participant);
    });
    return map;
  }, [presence.participants]);

  useEffect(() => {
    if (presence.connectionState !== "open") return;
    const selectionId = model.state.previewOpen ? model.state.activeId : null;
    presence.sendSelection({ doc_id: selectionId ?? null });
  }, [
    model.state.activeId,
    model.state.previewOpen,
    presence.connectionState,
    presence.sendSelection,
  ]);
  const { actions, state } = model;
  const [detailsRequest, setDetailsRequest] = useState<{ id: string; tab: "details" | "notes" } | null>(null);
  const [bulkTagOpen, setBulkTagOpen] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{
    ids: string[];
    title: string;
    description: string;
    confirmLabel: string;
  } | null>(null);
  const [uploadPreflightFiles, setUploadPreflightFiles] = useState<File[]>([]);
  const urlSearch = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("q") ?? "";
  }, [location.search]);

  const urlDocId = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("doc");
  }, [location.search]);

  useEffect(() => {
    if (urlSearch !== state.search) {
      actions.setSearch(urlSearch);
    }
  }, [actions, state.search, urlSearch]);

  useEffect(() => {
    if (!filtersEqual(model.state.filters, urlFilters)) {
      model.actions.setFilters(urlFilters);
    }
  }, [model.actions, model.state.filters, urlFilters]);

  useEffect(() => {
    if (!urlDocId) {
      if (state.previewOpen) {
        actions.closePreview();
      }
      return;
    }
    if (state.activeId !== urlDocId || !state.previewOpen) {
      actions.openPreview(urlDocId);
    }
  }, [actions, state.activeId, state.previewOpen, urlDocId]);

  const syncUrl = useCallback(
    (filters: DocumentsFilters, search: string, docId: string | null, replace = true) => {
      const params = buildDocumentsSearchParams(filters, search, docId);
      const target = `${location.pathname}${params ? `?${params}` : ""}${location.hash ?? ""}`;
      const current = `${location.pathname}${location.search}${location.hash ?? ""}`;
      if (target !== current) {
        navigate(target, { replace });
      }
    },
    [location.hash, location.pathname, location.search, navigate],
  );

  useEffect(() => {
    if (!state.previewOpen) return;
    if (!state.activeId) return;
    if (!urlDocId) return;
    if (urlDocId === state.activeId) return;
    syncUrl(state.filters, urlSearch, state.activeId, true);
  }, [state.activeId, state.filters, state.previewOpen, syncUrl, urlDocId, urlSearch]);

  const handleFiltersChange = useCallback(
    (next: DocumentsFilters) => {
      actions.setFilters(next);
      const docId = state.previewOpen ? state.activeId : null;
      syncUrl(next, urlSearch, docId);
    },
    [actions, state.activeId, state.previewOpen, syncUrl, urlSearch],
  );

  const handleSetBuiltInView = useCallback(
    (id: BuiltInViewId) => {
      actions.setBuiltInView(id);
      const docId = state.previewOpen ? state.activeId : null;
      const nextFilters = buildFiltersForBuiltInView(id, currentUserKey);
      syncUrl(nextFilters, urlSearch, docId);
    },
    [actions, currentUserKey, state.activeId, state.previewOpen, syncUrl, urlSearch],
  );

  const handleSelectSavedView = useCallback(
    (viewId: string) => {
      const view = model.derived.savedViews.find((saved) => saved.id === viewId);
      if (!view) return;
      actions.selectSavedView(viewId);
      const docId = state.previewOpen ? state.activeId : null;
      syncUrl(view.filters, urlSearch, docId);
    },
    [actions, model.derived.savedViews, state.activeId, state.previewOpen, syncUrl, urlSearch],
  );

  const handleClearFilters = () => {
    actions.setSearch("");
    actions.setBuiltInView("all_documents");
    const docId = state.previewOpen ? state.activeId : null;
    syncUrl(DEFAULT_DOCUMENT_FILTERS, "", docId);
  };

  const openConfigBuilder = useCallback(() => {
    navigate(`/workspaces/${workspace.id}/config-builder`);
  }, [navigate, workspace.id]);
  const openProcessingSettings = useCallback(() => {
    navigate(`/workspaces/${workspace.id}/settings/processing`);
  }, [navigate, workspace.id]);

  const onActivate = (id: string) => {
    if (state.activeId === id && state.previewOpen) {
      onClosePreview();
      return;
    }
    actions.openPreview(id);
    syncUrl(state.filters, urlSearch, id, Boolean(urlDocId));
  };

  const onClosePreview = () => {
    actions.closePreview();
    setDetailsRequest(null);
    syncUrl(state.filters, urlSearch, null, false);
  };

  const onOpenDetails = useCallback(
    (id: string) => {
      actions.openPreview(id);
      syncUrl(state.filters, urlSearch, id, Boolean(urlDocId));
      setDetailsRequest({ id, tab: "details" });
    },
    [actions, state.filters, syncUrl, urlDocId, urlSearch],
  );

  const onOpenNotes = useCallback(
    (id: string) => {
      actions.openPreview(id);
      syncUrl(state.filters, urlSearch, id, Boolean(urlDocId));
      setDetailsRequest({ id, tab: "notes" });
    },
    [actions, state.filters, syncUrl, urlDocId, urlSearch],
  );

  const requestDeleteDocument = useCallback((doc: DocumentEntry) => {
    setDeleteDialog({
      ids: [doc.id],
      title: `Delete ${doc.name}?`,
      description: "This removes the document from the workspace.",
      confirmLabel: "Delete document",
    });
  }, []);

  const selectedDocuments = useMemo(
    () => model.derived.visibleDocuments.filter((doc) => model.state.selectedIds.has(doc.id) && doc.record),
    [model.derived.visibleDocuments, model.state.selectedIds],
  );

  const selectedOutputReadyCount = useMemo(
    () => selectedDocuments.filter((doc) => Boolean(getDocumentOutputRun(doc.record))).length,
    [selectedDocuments],
  );
  const selectedArchivedCount = useMemo(
    () => selectedDocuments.filter((doc) => doc.status === "archived").length,
    [selectedDocuments],
  );
  const selectedActiveCount = selectedDocuments.length - selectedArchivedCount;

  const requestBulkDelete = useCallback(() => {
    if (selectedDocuments.length === 0) return;
    const countLabel = selectedDocuments.length === 1 ? "document" : "documents";
    setDeleteDialog({
      ids: selectedDocuments.map((doc) => doc.id),
      title: `Delete ${selectedDocuments.length} ${countLabel}?`,
      description: `This removes the ${countLabel} from the workspace.`,
      confirmLabel: `Delete ${selectedDocuments.length} ${countLabel}`,
    });
  }, [selectedDocuments]);

  const confirmDelete = useCallback(() => {
    if (!deleteDialog) return;
    const ids = deleteDialog.ids;
    if (ids.length === 0) {
      setDeleteDialog(null);
      return;
    }
    if (state.previewOpen && state.activeId && ids.includes(state.activeId)) {
      onClosePreview();
    }
    if (ids.length === 1) {
      actions.deleteDocument(ids[0]);
    } else {
      actions.bulkDeleteDocuments(ids);
    }
    setDeleteDialog(null);
  }, [actions, deleteDialog, onClosePreview, state.activeId, state.previewOpen]);

  const handleFileInputChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    if (selected.length > 0) {
      setUploadPreflightFiles(selected);
    }
    event.target.value = "";
  }, []);

  const handleUploadConfirm = useCallback(
    (items: Parameters<typeof model.actions.queueUploads>[0]) => {
      model.actions.queueUploads(items);
      setUploadPreflightFiles([]);
    },
    [model.actions.queueUploads],
  );

  const handleUploadCancel = useCallback(() => {
    setUploadPreflightFiles([]);
  }, []);
  return (
    <div className="documents flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <DocumentsHeader
        onUploadClick={model.actions.handleUploadClick}
        fileInputRef={model.refs.fileInputRef}
        onFileInputChange={handleFileInputChange}
        showConfigurationWarning={model.derived.configMissing}
        processingPaused={model.derived.processingPaused}
        canManageConfigurations={canManageConfigurations}
        canManageSettings={canManageSettings}
        onOpenConfigBuilder={openConfigBuilder}
        onOpenSettings={openProcessingSettings}
        uploads={model.derived.uploads}
        onPauseUpload={model.actions.pauseUpload}
        onResumeUpload={model.actions.resumeUpload}
        onRetryUpload={model.actions.retryUpload}
        onCancelUpload={model.actions.cancelUpload}
        onRemoveUpload={model.actions.removeUpload}
        onClearCompletedUploads={model.actions.clearCompletedUploads}
      />

      <UploadPreflightDialog
        open={uploadPreflightFiles.length > 0}
        files={uploadPreflightFiles}
        onConfirm={handleUploadConfirm}
        onCancel={handleUploadCancel}
        processingPaused={model.derived.processingPaused}
        configMissing={model.derived.configMissing}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <DocumentsFiltersBar
            viewMode={model.state.viewMode}
            onViewModeChange={model.actions.setViewMode}
            listSettings={model.state.listSettings}
            onListSettingsChange={model.actions.setListSettings}
            workspaceId={workspace.id}
            filters={model.state.filters}
            onChange={handleFiltersChange}
            people={model.derived.people}
            showingCount={model.derived.visibleDocuments.length}
            totalCount={model.derived.documents.length}
            isRefreshing={model.derived.isRefreshing}
            lastUpdatedAt={model.derived.lastUpdatedAt}
            now={model.derived.now}
            onRefresh={model.actions.refreshDocuments}
            presenceParticipants={activeParticipants}
            activeViewId={model.state.activeViewId}
            onSetBuiltInView={handleSetBuiltInView}
            savedViews={model.derived.savedViews}
            onSelectSavedView={handleSelectSavedView}
            onDeleteSavedView={(id) => model.actions.deleteView(id)}
            onOpenSaveDialog={model.actions.openSaveView}
            counts={model.derived.counts}
          />

          {model.state.viewMode === "grid" ? (
            <>
              <DocumentsGrid
                workspaceId={workspace.id}
                documents={model.derived.visibleDocuments}
                density={model.state.listSettings.density}
                activeId={model.state.activeId}
                presenceByDocument={presenceByDocument}
                selectedIds={model.state.selectedIds}
                onSelect={model.actions.updateSelection}
                onSelectAll={model.actions.selectAllVisible}
                onClearSelection={model.actions.clearSelection}
                allVisibleSelected={model.derived.allVisibleSelected}
                someVisibleSelected={model.derived.someVisibleSelected}
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
                processingPaused={model.derived.processingPaused}
                people={model.derived.people}
                onAssign={model.actions.assignDocument}
                onPickUp={model.actions.pickUpDocument}
                onTagsChange={model.actions.updateTagsOptimistic}
                onDownloadOriginal={model.actions.downloadOriginal}
                onDownloadOutput={model.actions.downloadOutputFromRow}
                onCopyLink={model.actions.copyLink}
                onReprocess={(doc) => model.actions.reprocess(doc)}
                onDelete={requestDeleteDocument}
                onArchive={(doc) => model.actions.archiveDocument(doc.id)}
                onRestore={(doc) => model.actions.restoreDocument(doc.id)}
                onOpenDetails={onOpenDetails}
                onOpenNotes={onOpenNotes}
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
                      runMetrics={model.derived.runMetrics}
                      outputUrl={model.derived.outputUrl}
                      onDownloadOutput={model.actions.downloadOutput}
                      onDownloadOriginal={model.actions.downloadOriginal}
                      onReprocess={model.actions.reprocess}
                      onArchive={(doc) => {
                        if (doc) model.actions.archiveDocument(doc.id);
                      }}
                      onRestore={(doc) => {
                        if (doc) model.actions.restoreDocument(doc.id);
                      }}
                      processingPaused={model.derived.processingPaused}
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
                      detailsRequestId={detailsRequest?.id ?? null}
                      detailsRequestTab={detailsRequest?.tab ?? null}
                      onDetailsRequestHandled={() => setDetailsRequest(null)}
                    />
                  ) : null
                }
              />

              <BulkActionBar
                count={selectedDocuments.length}
                outputReadyCount={selectedOutputReadyCount}
                archiveCount={selectedActiveCount}
                restoreCount={selectedArchivedCount}
                onArchive={model.actions.bulkArchiveDocuments}
                onRestore={model.actions.bulkRestoreDocuments}
                onClear={model.actions.clearSelection}
                onAddTag={() => setBulkTagOpen(true)}
                onDownloadOriginals={model.actions.bulkDownloadOriginals}
                onDownloadOutputs={model.actions.bulkDownloadOutputs}
                onDelete={requestBulkDelete}
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
                density={model.state.listSettings.density}
                now={model.derived.now}
                isLoading={model.derived.isLoading}
                isError={model.derived.isError}
                hasNextPage={model.derived.hasNextPage}
                isFetchingNextPage={model.derived.isFetchingNextPage}
                onLoadMore={model.actions.loadMore}
                onRefresh={model.actions.refreshDocuments}
                presenceByDocument={presenceByDocument}
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
                      runMetrics={model.derived.runMetrics}
                      outputUrl={model.derived.outputUrl}
                      onDownloadOutput={model.actions.downloadOutput}
                      onDownloadOriginal={model.actions.downloadOriginal}
                      onReprocess={model.actions.reprocess}
                      onArchive={(doc) => {
                        if (doc) model.actions.archiveDocument(doc.id);
                      }}
                      onRestore={(doc) => {
                        if (doc) model.actions.restoreDocument(doc.id);
                      }}
                      processingPaused={model.derived.processingPaused}
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
                      detailsRequestId={detailsRequest?.id ?? null}
                      detailsRequestTab={detailsRequest?.tab ?? null}
                      onDetailsRequestHandled={() => setDetailsRequest(null)}
                    />
                  </div>
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>

      <SaveViewDialog open={model.state.saveViewOpen} onClose={model.actions.closeSaveView} onSave={model.actions.saveView} />
      <BulkTagDialog
        open={bulkTagOpen}
        workspaceId={workspace.id}
        selectedCount={selectedDocuments.length}
        onClose={() => setBulkTagOpen(false)}
        onApply={(payload) => model.actions.bulkUpdateTags(payload)}
      />
      <ConfirmDialog
        open={Boolean(deleteDialog)}
        title={deleteDialog?.title ?? "Delete documents?"}
        description={deleteDialog?.description}
        confirmLabel={deleteDialog?.confirmLabel ?? "Delete"}
        onCancel={() => setDeleteDialog(null)}
        onConfirm={confirmDelete}
        tone="danger"
      />
    </div>
  );
}
