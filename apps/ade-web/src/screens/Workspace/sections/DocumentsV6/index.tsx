import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from "react";
import clsx from "clsx";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSearchParams } from "@app/nav/urlState";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { client } from "@shared/api/client";
import { useFlattenedPages } from "@shared/api/pagination";
import { uploadWorkspaceDocument } from "@shared/documents";
import { useUploadQueue, type UploadQueueItem } from "@shared/uploads/queue";
import { fetchRun, runOutputUrl } from "@shared/runs/api";
import type { components, paths } from "@schema";

import { Avatar } from "@ui/Avatar";
import { Button } from "@ui/Button";
import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

/* -------------------------------- Types & constants ------------------------------- */

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type DocumentPage = components["schemas"]["DocumentPage"];
type DocumentLastRun = components["schemas"]["DocumentLastRun"];
type RunResource = components["schemas"]["RunResource"];

type UploadItem = UploadQueueItem<DocumentRecord>;

type DocumentsView = "grid" | "board";
type BoardGroupBy = "status" | "owner" | "tag";
type UploadDisplayStatus = "queued" | "uploading" | "failed-upload" | "cancelled" | "uploaded";
type DisplayStatus = DocumentStatus | UploadDisplayStatus;

type OwnerInfo = {
  readonly id: string;
  readonly name: string;
  readonly email?: string | null;
  readonly source: "uploader" | "metadata" | "override";
};

type MappingHealth = {
  readonly score: number | null;
  readonly issues: number;
  readonly unmapped: number;
  readonly status: "good" | "warning" | "critical" | "pending";
};

type DocumentOverride = {
  readonly owner?: OwnerInfo | null;
  readonly tags?: string[];
  readonly status?: DocumentStatus;
};

type UploadContext = {
  readonly owner?: OwnerInfo | null;
  readonly tag?: string | null;
};

type DocumentListItem = {
  readonly id: string;
  readonly kind: "document" | "upload";
  readonly document?: DocumentRecord;
  readonly upload?: UploadItem;
  readonly name: string;
  readonly status: DisplayStatus;
  readonly tags: string[];
  readonly owner: OwnerInfo | null;
  readonly updatedAt: string;
  readonly mapping: MappingHealth | null;
  readonly processedReady: boolean;
  readonly needsAttention: boolean;
  readonly bytes?: number | null;
};

type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

type WorkbookSheet = {
  readonly name: string;
  readonly headers: string[];
  readonly rows: string[][];
  readonly totalRows: number;
  readonly totalColumns: number;
  readonly truncatedRows: boolean;
  readonly truncatedColumns: boolean;
};

type WorkbookPreview = {
  readonly sheets: WorkbookSheet[];
};

const DOCUMENTS_PAGE_SIZE = 50;
const DEFAULT_SORT = "-last_run_at";
const MAX_PREVIEW_ROWS = 500;
const MAX_PREVIEW_COLUMNS = 32;

const STATUS_COLUMNS: readonly DocumentStatus[] = [
  "uploaded",
  "processing",
  "processed",
  "failed",
  "archived",
];

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const DISPLAY_STATUS_META: Record<DisplayStatus, { label: string; tone: string }> = {
  uploaded: { label: "Uploaded", tone: "bg-slate-400" },
  processing: { label: "Processing", tone: "bg-amber-500" },
  processed: { label: "Processed", tone: "bg-emerald-500" },
  failed: { label: "Failed", tone: "bg-rose-500" },
  archived: { label: "Archived", tone: "bg-slate-300" },
  queued: { label: "Queued", tone: "bg-slate-400" },
  uploading: { label: "Uploading", tone: "bg-sky-500" },
  "failed-upload": { label: "Upload failed", tone: "bg-rose-500" },
  cancelled: { label: "Cancelled", tone: "bg-slate-300" },
};

const GRID_TEMPLATE =
  "42px minmax(220px,2.2fr) minmax(120px,0.9fr) minmax(140px,1fr) minmax(160px,1fr) minmax(120px,0.8fr) 40px";

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

const documentsV6Keys = {
  root: () => ["documents-v6"] as const,
  workspace: (workspaceId: string) => [...documentsV6Keys.root(), workspaceId] as const,
  list: (workspaceId: string, sort: string | null) =>
    [...documentsV6Keys.workspace(workspaceId), "list", { sort }] as const,
  run: (runId: string) => [...documentsV6Keys.root(), "run", runId] as const,
  workbook: (url: string) => [...documentsV6Keys.root(), "workbook", url] as const,
};

/* -------------------------------- Route component ------------------------------- */

export default function WorkspaceDocumentsV6Route() {
  const { workspace } = useWorkspaceContext();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const view = parseViewParam(searchParams.get("view"));
  const groupBy = parseGroupParam(searchParams.get("group"));
  const search = searchParams.get("q") ?? "";
  const searchNormalized = search.trim().toLowerCase();

  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [documentOverrides, setDocumentOverrides] = useState<Record<string, DocumentOverride>>({});
  const [uploadContexts, setUploadContexts] = useState<Record<string, UploadContext>>({});
  const [bulkMessage, setBulkMessage] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileDragColumn, setFileDragColumn] = useState<string | null>(null);
  const [draggingCardId, setDraggingCardId] = useState<string | null>(null);
  const dragCounter = useRef(0);
  const bulkMessageTimeout = useRef<number | null>(null);
  const invalidatedUploadsRef = useRef(new Set<string>());
  const appliedUploadContextsRef = useRef(new Set<string>());

  const documentsQuery = useWorkspaceDocumentsV6(workspace.id, DEFAULT_SORT);

  const uploadQueue = useUploadQueue({
    startUpload: (file, { onProgress }) =>
      uploadWorkspaceDocument(workspace.id, file, { onProgress }),
  });

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!bulkMessage) {
      return;
    }
    if (bulkMessageTimeout.current) {
      window.clearTimeout(bulkMessageTimeout.current);
    }
    bulkMessageTimeout.current = window.setTimeout(() => setBulkMessage(null), 3200);
    return () => {
      if (bulkMessageTimeout.current) {
        window.clearTimeout(bulkMessageTimeout.current);
      }
    };
  }, [bulkMessage]);

  useEffect(() => {
    let shouldInvalidate = false;
    uploadQueue.items.forEach((item) => {
      if (item.status !== "succeeded" || !item.response) {
        return;
      }
      if (!invalidatedUploadsRef.current.has(item.response.id)) {
        invalidatedUploadsRef.current.add(item.response.id);
        shouldInvalidate = true;
      }
    });
    if (shouldInvalidate) {
      queryClient.invalidateQueries({ queryKey: documentsV6Keys.workspace(workspace.id) });
    }
  }, [queryClient, uploadQueue.items, workspace.id]);

  useEffect(() => {
    uploadQueue.items.forEach((item) => {
      const response = item.response;
      if (!response || item.status !== "succeeded") {
        return;
      }
      if (appliedUploadContextsRef.current.has(item.id)) {
        return;
      }
      const context = uploadContexts[item.id];
      if (context) {
        setDocumentOverrides((current) => {
          const existing = current[response.id] ?? {};
          return {
            ...current,
            [response.id]: {
              ...existing,
              owner: context.owner ?? existing.owner,
              tags: context.tag
                ? [context.tag, ...(existing.tags ?? response.tags ?? []).filter((tag) => tag !== context.tag)]
                : existing.tags,
            },
          };
        });
      }
      appliedUploadContextsRef.current.add(item.id);
    });
  }, [uploadContexts, uploadQueue.items]);

  const documentsRaw = useFlattenedPages(documentsQuery.data?.pages, (doc) => doc.id);

  const documentsSorted = useMemo(() => {
    const copy = [...documentsRaw];
    copy.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
    return copy;
  }, [documentsRaw]);

  const documentsById = useMemo(() => {
    return new Map(documentsSorted.map((doc) => [doc.id, doc]));
  }, [documentsSorted]);

  const uploadResponseDocs = useMemo(() => {
    return uploadQueue.items
      .map((item) => item.response)
      .filter((doc): doc is DocumentRecord => Boolean(doc))
      .filter((doc) => !documentsById.has(doc.id));
  }, [documentsById, uploadQueue.items]);

  const documentsCombined = useMemo(() => {
    return [...uploadResponseDocs, ...documentsSorted];
  }, [documentsSorted, uploadResponseDocs]);

  const documentItems = useMemo<DocumentListItem[]>(() => {
    return documentsCombined.map((doc) => buildDocumentItem(doc, documentOverrides[doc.id]));
  }, [documentsCombined, documentOverrides]);

  const ownerLookup = useMemo(() => {
    const map = new Map<string, OwnerInfo>();
    documentItems.forEach((item) => {
      if (item.owner) {
        map.set(item.owner.id, item.owner);
      }
    });
    return map;
  }, [documentItems]);

  const uploadItems = useMemo<DocumentListItem[]>(() => {
    return uploadQueue.items
      .filter((item) => !item.response)
      .map((item) => buildUploadItem(item, uploadContexts[item.id]));
  }, [uploadContexts, uploadQueue.items]);

  const combinedItems = useMemo(() => {
    return [...uploadItems, ...documentItems];
  }, [documentItems, uploadItems]);

  const filteredItems = useMemo(() => {
    if (!searchNormalized) {
      return combinedItems;
    }
    return combinedItems.filter((item) => matchesSearch(item, searchNormalized));
  }, [combinedItems, searchNormalized]);

  const visibleDocumentIds = useMemo(() => {
    return new Set(filteredItems.filter((item) => item.document).map((item) => item.id));
  }, [filteredItems]);

  const selectedVisibleIds = useMemo(() => {
    return new Set([...selectedIds].filter((id) => visibleDocumentIds.has(id)));
  }, [selectedIds, visibleDocumentIds]);

  const selectedDocuments = useMemo(() => {
    return documentsCombined.filter((doc) => selectedVisibleIds.has(doc.id));
  }, [documentsCombined, selectedVisibleIds]);

  const activeDocument = useMemo(() => {
    if (!activeDocumentId) {
      return null;
    }
    return (
      documentsById.get(activeDocumentId) ??
      uploadQueue.items.find((item) => item.response?.id === activeDocumentId)?.response ??
      null
    );
  }, [activeDocumentId, documentsById, uploadQueue.items]);

  const activeOverrides = useMemo(() => {
    if (!activeDocument) {
      return undefined;
    }
    return documentOverrides[activeDocument.id];
  }, [activeDocument, documentOverrides]);

  useEffect(() => {
    if (activeDocumentId && !activeDocument) {
      setActiveDocumentId(null);
    }
  }, [activeDocument, activeDocumentId]);

  const showEmpty = !documentsQuery.isLoading && combinedItems.length === 0;
  const showNoResults = !documentsQuery.isLoading && combinedItems.length > 0 && filteredItems.length === 0;
  const hasNextPage = documentsQuery.hasNextPage ?? false;
  const isFetchingNextPage = documentsQuery.isFetchingNextPage;

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set("q", value);
        } else {
          next.delete("q");
        }
        return next;
      });
    },
    [setSearchParams],
  );

  const handleViewChange = useCallback(
    (nextView: DocumentsView) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("view", nextView);
        return next;
      });
    },
    [setSearchParams],
  );

  const handleGroupChange = useCallback(
    (nextGroup: BoardGroupBy) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("group", nextGroup);
        return next;
      });
    },
    [setSearchParams],
  );

  const handleToggleSelection = useCallback((documentId: string, nextValue: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (nextValue) {
        next.add(documentId);
      } else {
        next.delete(documentId);
      }
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(
    (nextValue: boolean) => {
      setSelectedIds((current) => {
        if (!nextValue) {
          const next = new Set(current);
          visibleDocumentIds.forEach((id) => next.delete(id));
          return next;
        }
        const next = new Set(current);
        visibleDocumentIds.forEach((id) => next.add(id));
        return next;
      });
    },
    [visibleDocumentIds],
  );

  const handleRowClick = useCallback((item: DocumentListItem) => {
    if (!item.document) {
      return;
    }
    setActiveDocumentId(item.id);
  }, []);

  const handleUploadFiles = useCallback(
    (files: File[], context?: UploadContext) => {
      if (files.length === 0) {
        return;
      }
      const queued = uploadQueue.enqueue(files);
      if (context) {
        setUploadContexts((current) => {
          const next = { ...current };
          queued.forEach((item) => {
            next[item.id] = context;
          });
          return next;
        });
      }
    },
    [uploadQueue],
  );

  const handleUploadButtonClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files ?? []);
      handleUploadFiles(files);
      event.target.value = "";
    },
    [handleUploadFiles],
  );

  const handleDragEnter = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!isFileTransfer(event.dataTransfer.types)) {
      return;
    }
    event.preventDefault();
    dragCounter.current += 1;
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!isFileTransfer(event.dataTransfer.types)) {
      return;
    }
    event.preventDefault();
    dragCounter.current = Math.max(0, dragCounter.current - 1);
    if (dragCounter.current === 0) {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!event.dataTransfer.files.length) {
        return;
      }
      event.preventDefault();
      dragCounter.current = 0;
      setDragActive(false);
      const files = Array.from(event.dataTransfer.files);
      handleUploadFiles(files);
    },
    [handleUploadFiles],
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    }),
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setDraggingCardId(String(event.active.id));
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const activeId = String(event.active.id);
      const overId = event.over?.id ? String(event.over.id) : null;
      if (!overId || !activeId || activeId === overId) {
        setDraggingCardId(null);
        return;
      }
      const targetGroup = parseBoardDropTarget(overId, ownerLookup);
      if (!targetGroup) {
        setDraggingCardId(null);
        return;
      }
      const item = documentItems.find((doc) => doc.id === activeId);
      if (!item || !item.document) {
        setDraggingCardId(null);
        return;
      }

      const currentStatus = isDocumentStatus(item.status) ? item.status : item.document.status;

      if (groupBy === "status" && targetGroup.type === "status") {
        if (currentStatus === targetGroup.value) {
          setDraggingCardId(null);
          return;
        }
        if (!isStatusMoveAllowed(currentStatus, targetGroup.value)) {
          setBulkMessage("Status changes are limited in this view.");
          setDraggingCardId(null);
          return;
        }
        setDocumentOverrides((current) => ({
          ...current,
          [item.document.id]: {
            ...current[item.document.id],
            status: targetGroup.value,
          },
        }));
      }

      if (groupBy === "owner" && targetGroup.type === "owner") {
        setDocumentOverrides((current) => ({
          ...current,
          [item.document.id]: {
            ...current[item.document.id],
            owner: targetGroup.value,
          },
        }));
      }

      if (groupBy === "tag" && targetGroup.type === "tag") {
        const nextTags = targetGroup.value
          ? [targetGroup.value, ...item.tags.filter((tag) => tag !== targetGroup.value)]
          : [];
        setDocumentOverrides((current) => ({
          ...current,
          [item.document.id]: {
            ...current[item.document.id],
            tags: nextTags,
          },
        }));
      }

      setDraggingCardId(null);
    },
    [documentItems, groupBy, ownerLookup],
  );

  if (documentsQuery.isError) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6">
        <PageState
          title="Unable to load documents"
          description="Refresh the page or try again in a moment."
          variant="error"
        />
      </div>
    );
  }

  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden bg-slate-50"
      onDragEnter={handleDragEnter}
      onDragOver={(event) => {
        if (isFileTransfer(event.dataTransfer.types)) {
          event.preventDefault();
        }
      }}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <DocumentsTopBar
        view={view}
        search={search}
        onSearchChange={handleSearchChange}
        onViewChange={handleViewChange}
        onUploadClick={handleUploadButtonClick}
      />
      {selectedVisibleIds.size > 0 ? (
        <BulkActionsBar
          selectedCount={selectedVisibleIds.size}
          hasFailed={selectedDocuments.some((doc) => doc.status === "failed")}
          message={bulkMessage}
          onClear={() => setSelectedIds(new Set())}
          onAction={(label) => setBulkMessage(`${label} is coming soon.`)}
        />
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col border-b border-slate-200 bg-white lg:border-b-0 lg:border-r">
          {view === "board" ? (
            <BoardControls groupBy={groupBy} onGroupChange={handleGroupChange} />
          ) : null}
          <div className="min-h-0 flex-1 flex flex-col">
            <div className="min-h-0 flex-1">
              {documentsQuery.isLoading ? (
                view === "grid" ? (
                  <GridSkeleton />
                ) : (
                  <BoardSkeleton />
                )
              ) : showEmpty ? (
                <EmptyState onUploadClick={handleUploadButtonClick} />
              ) : showNoResults ? (
                <NoResultsState onClear={() => handleSearchChange("")} query={search} />
              ) : view === "grid" ? (
                <DocumentsGrid
                  items={filteredItems}
                  selectedIds={selectedVisibleIds}
                  activeId={activeDocumentId}
                  onToggleSelection={handleToggleSelection}
                  onToggleAll={handleToggleAll}
                  onRowClick={handleRowClick}
                />
              ) : (
                <DocumentsBoard
                  items={filteredItems}
                  groupBy={groupBy}
                  draggingId={draggingCardId}
                  onCardClick={handleRowClick}
                  onUploadFiles={handleUploadFiles}
                  onFileDragColumn={setFileDragColumn}
                  fileDragColumn={fileDragColumn}
                  sensors={sensors}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                />
              )}
            </div>
            {hasNextPage && !documentsQuery.isLoading ? (
              <LoadMoreFooter
                isLoading={isFetchingNextPage}
                onLoadMore={() => documentsQuery.fetchNextPage()}
              />
            ) : null}
          </div>
        </div>
        <div className="flex min-h-0 w-full flex-col bg-slate-50 lg:w-[420px] lg:max-w-[42%]">
          <DocumentInspector
            document={activeDocument}
            mapping={activeDocument ? deriveMappingHealth(activeDocument) : null}
            overrides={activeOverrides}
          />
        </div>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        multiple
        accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
        onChange={handleFileInputChange}
      />
      {dragActive ? <UploadOverlay /> : null}
    </div>
  );
}

/* -------------------------------- Top bar & controls ------------------------------- */

function DocumentsTopBar({
  view,
  search,
  onSearchChange,
  onViewChange,
  onUploadClick,
}: {
  readonly view: DocumentsView;
  readonly search: string;
  readonly onSearchChange: (value: string) => void;
  readonly onViewChange: (value: DocumentsView) => void;
  readonly onUploadClick: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-6 py-4">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-slate-900">Documents</h1>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
          v6
        </span>
      </div>
      <div className="flex min-w-[220px] flex-1 items-center gap-2">
        <div className="relative flex w-full max-w-xl items-center">
          <SearchIcon className="pointer-events-none absolute left-3 h-4 w-4 text-slate-400" />
          <Input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search by name, tag, or owner"
            className="pl-9"
            aria-label="Search documents"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <SegmentedControl
          value={view}
          options={[
            { id: "grid", label: "Grid" },
            { id: "board", label: "Board" },
          ]}
          onChange={onViewChange}
        />
        <Button size="sm" onClick={onUploadClick}>
          Upload
        </Button>
      </div>
    </div>
  );
}

function BoardControls({
  groupBy,
  onGroupChange,
}: {
  readonly groupBy: BoardGroupBy;
  readonly onGroupChange: (value: BoardGroupBy) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/70 px-6 py-3 text-sm">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Group by
      </div>
      <SegmentedControl
        value={groupBy}
        options={[
          { id: "status", label: "Status" },
          { id: "owner", label: "Owner" },
          { id: "tag", label: "Tag" },
        ]}
        onChange={onGroupChange}
      />
    </div>
  );
}

function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  readonly value: T;
  readonly options: readonly { id: T; label: string }[];
  readonly onChange: (value: T) => void;
}) {
  return (
    <div className="flex items-center rounded-full border border-slate-200 bg-white p-1 text-sm shadow-sm">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={clsx(
            "rounded-full px-3 py-1.5 text-xs font-semibold transition",
            value === option.id
              ? "bg-slate-900 text-white"
              : "text-slate-500 hover:bg-slate-100 hover:text-slate-700",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function BulkActionsBar({
  selectedCount,
  hasFailed,
  message,
  onClear,
  onAction,
}: {
  readonly selectedCount: number;
  readonly hasFailed: boolean;
  readonly message: string | null;
  readonly onClear: () => void;
  readonly onAction: (label: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/90 px-6 py-3 text-sm">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-slate-900">{selectedCount} selected</span>
        {message ? <span className="text-xs text-slate-500">{message}</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => onAction("Assign owner")}>
          Assign owner
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onAction("Tag")}>
          Tag
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={!hasFailed}
          onClick={() => onAction("Retry processing")}
        >
          Retry processing
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onAction("Archive")}>
          Archive
        </Button>
        <button
          type="button"
          onClick={onClear}
          className="text-xs font-semibold text-slate-400 hover:text-slate-600"
        >
          Clear
        </button>
      </div>
    </div>
  );
}

/* -------------------------------- Grid view ------------------------------- */

function DocumentsGrid({
  items,
  selectedIds,
  activeId,
  onToggleSelection,
  onToggleAll,
  onRowClick,
}: {
  readonly items: readonly DocumentListItem[];
  readonly selectedIds: ReadonlySet<string>;
  readonly activeId: string | null;
  readonly onToggleSelection: (documentId: string, nextValue: boolean) => void;
  readonly onToggleAll: (nextValue: boolean) => void;
  readonly onRowClick: (item: DocumentListItem) => void;
}) {
  const selectableIds = items.filter((item) => item.document).map((item) => item.id);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <div
          className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-400"
          style={{ gridTemplateColumns: GRID_TEMPLATE }}
        >
          <div className="grid items-center gap-3 px-4 py-2" style={{ gridTemplateColumns: GRID_TEMPLATE }}>
            <div className="flex items-center">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(event) => onToggleAll(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                aria-label="Select all documents"
              />
            </div>
            <div>Document</div>
            <div>Status</div>
            <div>Owner</div>
            <div>Tags</div>
            <div>Updated</div>
            <div aria-hidden />
          </div>
        </div>
        <div className="divide-y divide-slate-200">
          {items.map((item) => (
            <DocumentRow
              key={item.id}
              item={item}
              active={item.id === activeId}
              selected={selectedIds.has(item.id)}
              onToggleSelection={onToggleSelection}
              onClick={() => onRowClick(item)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function DocumentRow({
  item,
  active,
  selected,
  onToggleSelection,
  onClick,
}: {
  readonly item: DocumentListItem;
  readonly active: boolean;
  readonly selected: boolean;
  readonly onToggleSelection: (documentId: string, nextValue: boolean) => void;
  readonly onClick: () => void;
}) {
  const status = DISPLAY_STATUS_META[item.status];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onClick();
        }
      }}
      className={clsx(
        "group grid cursor-pointer items-center gap-3 px-4 py-3 text-sm transition",
        active ? "bg-slate-900/5" : "hover:bg-slate-50",
      )}
      style={{ gridTemplateColumns: GRID_TEMPLATE }}
    >
      <div className="flex items-center">
        <input
          type="checkbox"
          disabled={!item.document}
          checked={selected}
          onChange={(event) => onToggleSelection(item.id, event.target.checked)}
          onClick={(event) => event.stopPropagation()}
          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-40"
          aria-label={`Select ${item.name}`}
        />
      </div>
      <div className="flex min-w-0 items-center gap-3">
        <FileIcon className="h-5 w-5 text-slate-400" />
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{item.name}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <MappingBadge mapping={item.mapping} />
            {item.needsAttention ? (
              <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-600">
                Needs attention
              </span>
            ) : null}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
        <span className={clsx("h-2 w-2 rounded-full", status.tone)} aria-hidden />
        <span>{status.label}</span>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-500">
        {item.owner ? <Avatar size="sm" name={item.owner.name} email={item.owner.email ?? undefined} /> : null}
        <span className="truncate">{item.owner?.name ?? "Unassigned"}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <TagList tags={item.tags} />
      </div>
      <div className="text-xs text-slate-500">{formatRelativeTime(item.updatedAt)}</div>
      <div className="flex justify-end">
        <button
          type="button"
          className="rounded-full p-1 text-slate-400 opacity-0 transition hover:bg-slate-100 hover:text-slate-600 group-hover:opacity-100"
          onClick={(event) => event.stopPropagation()}
          aria-label="More actions"
        >
          <MoreIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

/* -------------------------------- Board view ------------------------------- */

function DocumentsBoard({
  items,
  groupBy,
  draggingId,
  onCardClick,
  onUploadFiles,
  onFileDragColumn,
  fileDragColumn,
  sensors,
  onDragStart,
  onDragEnd,
}: {
  readonly items: readonly DocumentListItem[];
  readonly groupBy: BoardGroupBy;
  readonly draggingId: string | null;
  readonly onCardClick: (item: DocumentListItem) => void;
  readonly onUploadFiles: (files: File[], context?: UploadContext) => void;
  readonly onFileDragColumn: (columnId: string | null) => void;
  readonly fileDragColumn: string | null;
  readonly sensors: ReturnType<typeof useSensors>;
  readonly onDragStart: (event: DragStartEvent) => void;
  readonly onDragEnd: (event: DragEndEvent) => void;
}) {
  const columns = useMemo(() => buildBoardColumns(items, groupBy), [groupBy, items]);
  const activeItem = items.find((item) => item.id === draggingId) ?? null;

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className="flex min-h-0 flex-1 overflow-x-auto bg-slate-50">
        <div className="flex min-h-0 flex-1 gap-4 px-6 py-4">
          {columns.map((column) => (
            <BoardColumn
              key={column.id}
              column={column}
              onCardClick={onCardClick}
              onUploadFiles={onUploadFiles}
              onFileDragColumn={onFileDragColumn}
              fileDragColumn={fileDragColumn}
            />
          ))}
        </div>
      </div>
      <DragOverlay>
        {activeItem ? (
          <div className="w-64">
            <BoardCardPreview item={activeItem} compact />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

type BoardColumnDescriptor = {
  readonly id: string;
  readonly label: string;
  readonly tone?: string;
  readonly items: DocumentListItem[];
  readonly groupValue: BoardGroupValue;
};

type BoardGroupValue =
  | { readonly type: "status"; readonly value: DocumentStatus }
  | { readonly type: "owner"; readonly value: OwnerInfo | null }
  | { readonly type: "tag"; readonly value: string | null };

function BoardColumn({
  column,
  onCardClick,
  onUploadFiles,
  onFileDragColumn,
  fileDragColumn,
}: {
  readonly column: BoardColumnDescriptor;
  readonly onCardClick: (item: DocumentListItem) => void;
  readonly onUploadFiles: (files: File[], context?: UploadContext) => void;
  readonly onFileDragColumn: (columnId: string | null) => void;
  readonly fileDragColumn: string | null;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const highlight = isOver || fileDragColumn === column.id;

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!event.dataTransfer.files.length) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      onFileDragColumn(null);
      const files = Array.from(event.dataTransfer.files);
      onUploadFiles(files, getUploadContextForColumn(column.groupValue));
    },
    [column.groupValue, onFileDragColumn, onUploadFiles],
  );

  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "flex min-h-0 w-72 flex-shrink-0 flex-col rounded-2xl border bg-white shadow-sm",
        highlight ? "border-brand-400 ring-2 ring-brand-200" : "border-slate-200",
      )}
      onDragOver={(event) => {
        if (isFileTransfer(event.dataTransfer.types)) {
          event.preventDefault();
          onFileDragColumn(column.id);
        }
      }}
      onDragLeave={(event) => {
        if (isFileTransfer(event.dataTransfer.types)) {
          onFileDragColumn(null);
        }
      }}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          {column.tone ? <span className={clsx("h-2 w-2 rounded-full", column.tone)} aria-hidden /> : null}
          <span className="text-sm font-semibold text-slate-900">{column.label}</span>
        </div>
        <span className="text-xs font-semibold text-slate-400">{column.items.length}</span>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {column.items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-xs text-slate-500">
            Drop files here or drag cards into this column.
          </div>
        ) : (
          column.items.map((item) => (
            <BoardCard key={item.id} item={item} onClick={() => onCardClick(item)} />
          ))
        )}
      </div>
    </div>
  );
}

function BoardCard({
  item,
  onClick,
  compact = false,
}: {
  readonly item: DocumentListItem;
  readonly onClick?: () => void;
  readonly compact?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: item.id });
  const style = {
    transform: CSS.Transform.toString(transform),
  };
  const status = DISPLAY_STATUS_META[item.status];

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={clsx(
        "rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition",
        onClick ? "cursor-pointer hover:border-slate-300" : "cursor-grab",
        isDragging && "opacity-60",
        compact && "p-2",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{item.name}</div>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <span className={clsx("h-2 w-2 rounded-full", status.tone)} aria-hidden />
            <span>{status.label}</span>
          </div>
        </div>
        {item.owner ? <Avatar size="sm" name={item.owner.name} email={item.owner.email ?? undefined} /> : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <TagList tags={item.tags} max={1} />
        <MappingBadge mapping={item.mapping} />
        {item.processedReady ? (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-600">Output ready</span>
        ) : null}
        {item.needsAttention ? (
          <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-600">Needs attention</span>
        ) : null}
      </div>
    </div>
  );
}

function BoardCardPreview({
  item,
  compact = false,
}: {
  readonly item: DocumentListItem;
  readonly compact?: boolean;
}) {
  const status = DISPLAY_STATUS_META[item.status];

  return (
    <div
      className={clsx(
        "rounded-xl border border-slate-200 bg-white p-3 shadow-sm",
        compact && "p-2",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{item.name}</div>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <span className={clsx("h-2 w-2 rounded-full", status.tone)} aria-hidden />
            <span>{status.label}</span>
          </div>
        </div>
        {item.owner ? <Avatar size="sm" name={item.owner.name} email={item.owner.email ?? undefined} /> : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <TagList tags={item.tags} max={1} />
        <MappingBadge mapping={item.mapping} />
        {item.processedReady ? (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-600">Output ready</span>
        ) : null}
        {item.needsAttention ? (
          <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-600">Needs attention</span>
        ) : null}
      </div>
    </div>
  );
}

/* -------------------------------- Preview pane ------------------------------- */

function DocumentInspector({
  document,
  mapping,
  overrides,
}: {
  readonly document: DocumentRecord | null;
  readonly mapping: MappingHealth | null;
  readonly overrides?: DocumentOverride;
}) {
  const [tab, setTab] = useState("preview");
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const appliedStatus = document ? overrides?.status ?? document.status : null;
  const appliedOwner = document ? overrides?.owner ?? deriveOwner(document) : null;
  const appliedTags = document ? overrides?.tags ?? document.tags ?? [] : [];

  useEffect(() => {
    setTab("preview");
  }, [document?.id]);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(null), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const runId = document?.last_run?.run_id ?? null;
  const runQuery = useQuery<RunResource | null>({
    queryKey: runId ? documentsV6Keys.run(runId) : ["documents-v6", "run", "none"],
    queryFn: ({ signal }) => (runId ? fetchRun(runId, signal) : Promise.resolve(null)),
    enabled: Boolean(runId),
    staleTime: 30_000,
  });

  const outputUrl = runQuery.data ? runOutputUrl(runQuery.data) : null;
  const outputMeta = runQuery.data?.output ?? null;

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (!document) {
      return [];
    }
    return [
      {
        id: "retry",
        label: "Retry processing",
        onSelect: () => setNotice("Retry will be available here soon."),
        disabled: appliedStatus !== "failed",
      },
      {
        id: "details",
        label: "View details",
        onSelect: () => setTab("details"),
      },
      {
        id: "download-original",
        label: "Download original",
        onSelect: () => {
          void downloadOriginal(document.workspace_id, document.id).catch(() => {
            setNotice("Unable to download the original file.");
          });
        },
      },
    ];
  }, [appliedStatus, document]);

  if (!document) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="text-sm font-semibold text-slate-900">Select a document</div>
        <div className="mt-2 text-sm text-slate-500">
          Preview processed outputs, inspect details, and download the normalized XLSX.
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span
                className={clsx(
                  "h-2.5 w-2.5 rounded-full",
                  appliedStatus ? getStatusTone(appliedStatus) : "bg-slate-300",
                )}
                aria-hidden
              />
              <h2 className="truncate text-base font-semibold text-slate-900">{document.name}</h2>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>{appliedStatus ? DOCUMENT_STATUS_LABELS[appliedStatus] : "Unknown"}</span>
              <span aria-hidden className="text-slate-300">
                -
              </span>
              <span>{formatBytes(document.byte_size)}</span>
              <span aria-hidden className="text-slate-300">
                -
              </span>
              <span>Updated {formatRelativeTime(document.updated_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={!outputUrl}
              onClick={() => outputUrl && window.open(outputUrl, "_blank", "noopener,noreferrer")}
            >
              Download processed
            </Button>
            <button
              type="button"
              onClick={(event: MouseEvent<HTMLButtonElement>) => {
                const rect = event.currentTarget.getBoundingClientRect();
                setMenuPosition({ x: rect.right + 8, y: rect.bottom });
              }}
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
              aria-label="More actions"
            >
              <MoreIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {notice ? (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500">
            {notice}
          </div>
        ) : null}
        <MappingSummary mapping={mapping} />
        <div className="mt-5 rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <TabsRoot value={tab} onValueChange={setTab}>
              <TabsList className="flex items-center gap-1 rounded-2xl bg-slate-100 p-1">
                <TabsTrigger
                  value="preview"
                  className={clsx(
                    "flex-1 rounded-xl px-3 py-2 text-xs font-semibold transition",
                    tab === "preview"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  Preview
                </TabsTrigger>
                <TabsTrigger
                  value="details"
                  className={clsx(
                    "flex-1 rounded-xl px-3 py-2 text-xs font-semibold transition",
                    tab === "details"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  Details
                </TabsTrigger>
                <TabsTrigger
                  value="history"
                  className={clsx(
                    "flex-1 rounded-xl px-3 py-2 text-xs font-semibold transition",
                    tab === "history"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  History
                </TabsTrigger>
              </TabsList>

              <TabsContent value="preview" className="p-4">
                <PreviewPane
                  document={document}
                  run={runQuery.data ?? null}
                  outputUrl={outputUrl}
                  outputMeta={outputMeta}
                  loadingRun={runQuery.isLoading}
                  status={appliedStatus ?? document.status}
                  onRetry={() => setNotice("Retry will be available here soon.")}
                />
              </TabsContent>
              <TabsContent value="details" className="p-4">
                <DocumentDetails
                  document={document}
                  status={appliedStatus ?? document.status}
                  owner={appliedOwner}
                  tags={appliedTags}
                />
              </TabsContent>
              <TabsContent value="history" className="p-4">
                <DocumentHistory document={document} lastRun={document.last_run} />
              </TabsContent>
            </TabsRoot>
          </div>
        </div>
      </div>

      <ContextMenu
        open={Boolean(menuPosition)}
        position={menuPosition}
        onClose={() => setMenuPosition(null)}
        items={menuItems}
        appearance="light"
      />
    </div>
  );
}

function MappingSummary({ mapping }: { readonly mapping: MappingHealth | null }) {
  if (!mapping) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
        Mapping health will appear here once processing completes.
      </div>
    );
  }

  const showFix = mapping.issues > 0 || mapping.unmapped > 0 || (mapping.score ?? 100) < 100;
  const mappingTone =
    mapping.status === "critical"
      ? "text-rose-600"
      : mapping.status === "warning"
        ? "text-amber-600"
        : mapping.status === "pending"
          ? "text-slate-500"
          : "text-emerald-600";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Mapping health</div>
        <div className={clsx("mt-1 text-sm font-semibold", mappingTone)}>
          {mapping.score === null ? "Mapping pending" : `Mapping: ${mapping.score}%`}
        </div>
        <div className="mt-1 text-xs text-slate-500">
          {mapping.score === null
            ? "Waiting for the latest run to score mappings."
            : mapping.issues > 0 || mapping.unmapped > 0
              ? `${mapping.issues + mapping.unmapped} columns need attention. Next: fix mapping, re-run, preview updated XLSX, download.`
              : "All columns mapped cleanly."}
        </div>
      </div>
      {showFix ? (
        <Button variant="secondary" size="sm" disabled>
          Fix mapping (coming soon)
        </Button>
      ) : null}
    </div>
  );
}

function PreviewPane({
  document,
  run,
  outputUrl,
  outputMeta,
  loadingRun,
  status,
  onRetry,
}: {
  readonly document: DocumentRecord;
  readonly run: RunResource | null;
  readonly outputUrl: string | null;
  readonly outputMeta: RunResource["output"] | null | undefined;
  readonly loadingRun: boolean;
  readonly status: DocumentStatus;
  readonly onRetry: () => void;
}) {
  if (status === "failed") {
    return (
      <PreviewPlaceholder
        title="Processing failed"
        description={document.last_run?.message ?? "We could not normalize this document."}
        actionLabel="Retry"
        onAction={onRetry}
      />
    );
  }

  if (status === "processing") {
    return (
      <PreviewPlaceholder
        title="Processing"
        description="Preview available once the normalized output is ready."
      />
    );
  }

  if (status === "uploaded") {
    return (
      <PreviewPlaceholder
        title="Queued"
        description="Processing will start automatically. Preview will appear here when ready."
      />
    );
  }

  if (status === "archived") {
    return (
      <PreviewPlaceholder
        title="Archived"
        description="This document is archived. Download the processed output if you need it later."
      />
    );
  }

  if (loadingRun) {
    return <PreviewLoading />;
  }

  if (!outputUrl) {
    return (
      <PreviewPlaceholder
        title="No processed output yet"
        description="The normalized XLSX will appear once the run completes."
      />
    );
  }

  return (
    <XlsxPreview
      outputUrl={outputUrl}
      outputMeta={outputMeta ?? null}
      runStatus={run?.status ?? null}
    />
  );
}

function PreviewPlaceholder({
  title,
  description,
  actionLabel,
  onAction,
}: {
  readonly title: string;
  readonly description: string;
  readonly actionLabel?: string;
  readonly onAction?: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-center">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <div className="text-sm text-slate-500">{description}</div>
      {actionLabel ? (
        <div className="flex justify-center">
          <Button size="sm" variant="secondary" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function PreviewLoading() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-center">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      <div className="text-sm text-slate-500">Loading processed workbook...</div>
    </div>
  );
}

function XlsxPreview({
  outputUrl,
  outputMeta,
  runStatus,
}: {
  readonly outputUrl: string;
  readonly outputMeta: RunResource["output"] | null;
  readonly runStatus: RunResource["status"] | null;
}) {
  const workbookQuery = useQuery<WorkbookPreview>({
    queryKey: documentsV6Keys.workbook(outputUrl),
    queryFn: ({ signal }) => fetchWorkbookPreview(outputUrl, signal),
    staleTime: 30_000,
  });

  const [activeSheet, setActiveSheet] = useState<string | null>(null);
  const [findQuery, setFindQuery] = useState("");
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);
  const rowRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const sheets = workbookQuery.data?.sheets ?? [];

  useEffect(() => {
    if (!activeSheet && sheets.length > 0) {
      setActiveSheet(sheets[0]?.name ?? null);
    }
  }, [activeSheet, sheets]);

  const sheet = sheets.find((entry) => entry.name === activeSheet) ?? sheets[0] ?? null;

  const matches = useMemo(() => {
    if (!sheet || !findQuery.trim()) {
      return [] as { row: number; col: number }[];
    }
    const query = findQuery.trim().toLowerCase();
    const found: { row: number; col: number }[] = [];
    sheet.rows.forEach((row, rowIndex) => {
      row.forEach((cell, colIndex) => {
        if (cell.toLowerCase().includes(query)) {
          found.push({ row: rowIndex, col: colIndex });
        }
      });
    });
    return found;
  }, [findQuery, sheet]);

  useEffect(() => {
    setActiveMatchIndex(0);
  }, [findQuery, sheet?.name]);

  useEffect(() => {
    if (!matches.length) {
      return;
    }
    const active = matches[activeMatchIndex % matches.length];
    const target = rowRefs.current.get(active.row);
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeMatchIndex, matches]);

  const matchSet = useMemo(() => {
    return new Set(matches.map((match) => `${match.row}-${match.col}`));
  }, [matches]);

  if (workbookQuery.isLoading) {
    return <PreviewLoading />;
  }

  if (workbookQuery.isError || !sheet) {
    return (
      <PreviewPlaceholder
        title="Preview unavailable"
        description="We could not render the processed output. Try downloading the file instead."
      />
    );
  }

  if (sheet.totalRows === 0) {
    return (
      <PreviewPlaceholder
        title="Sheet is empty"
        description="The processed output does not contain any rows yet."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-emerald-600">
              Processed output
            </div>
            <div className="mt-1 text-xs text-slate-500">
              This is the normalized XLSX output ready for download.
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            {outputMeta?.filename ? <span>{outputMeta.filename}</span> : null}
            {outputMeta?.size_bytes ? (
              <span>{formatBytes(outputMeta.size_bytes)}</span>
            ) : null}
            {runStatus ? <span className="rounded-full bg-slate-100 px-2 py-0.5">{runStatus}</span> : null}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Sheets
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                value={findQuery}
                onChange={(event) => setFindQuery(event.target.value)}
                placeholder="Find in sheet"
                className="h-8 w-44 pl-9 text-xs"
              />
            </div>
            <button
              type="button"
              onClick={() =>
                setActiveMatchIndex((current) =>
                  matches.length ? (current + 1) % matches.length : 0,
                )
              }
              className="rounded-full border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-500 hover:bg-slate-50"
            >
              {matches.length ? `${activeMatchIndex + 1}/${matches.length}` : "No matches"}
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-2">
          {sheets.map((entry) => (
            <button
              key={entry.name}
              type="button"
              onClick={() => setActiveSheet(entry.name)}
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-semibold transition",
                entry.name === sheet.name
                  ? "bg-slate-900 text-white"
                  : "text-slate-500 hover:bg-slate-100",
              )}
            >
              {entry.name}
            </button>
          ))}
        </div>
        <div className="max-h-[28rem] overflow-auto">
          <div className="min-w-max">
            <div
              className="sticky top-0 z-10 grid border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500"
              style={{
                gridTemplateColumns: `repeat(${sheet.headers.length}, minmax(160px,1fr))`,
              }}
            >
              {sheet.headers.map((header, index) => (
                <div key={`${header}-${index}`} className="px-3 py-2">
                  {header || "Untitled"}
                </div>
              ))}
            </div>
            {sheet.rows.map((row, rowIndex) => (
              <div
                key={rowIndex}
                ref={(node) => {
                  if (node) {
                    rowRefs.current.set(rowIndex, node);
                  } else {
                    rowRefs.current.delete(rowIndex);
                  }
                }}
                className="grid border-b border-slate-100 text-sm text-slate-700"
                style={{
                  gridTemplateColumns: `repeat(${sheet.headers.length}, minmax(160px,1fr))`,
                }}
              >
                {row.map((cell, colIndex) => (
                  <div
                    key={`${rowIndex}-${colIndex}`}
                    className={clsx(
                      "px-3 py-2",
                      matchSet.has(`${rowIndex}-${colIndex}`) && "bg-amber-100",
                    )}
                  >
                    {cell || ""}
                  </div>
                ))}
              </div>
            ))}
            {(sheet.truncatedRows || sheet.truncatedColumns) && (
              <div className="px-4 py-3 text-xs text-slate-500">
                Showing first {Math.min(sheet.totalRows, MAX_PREVIEW_ROWS)} rows and {Math.min(sheet.totalColumns, MAX_PREVIEW_COLUMNS)} columns.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DocumentDetails({
  document,
  status,
  owner,
  tags,
}: {
  readonly document: DocumentRecord;
  readonly status: DocumentStatus;
  readonly owner: OwnerInfo | null;
  readonly tags: readonly string[];
}) {
  const resolvedOwner = owner ?? deriveOwner(document);
  const resolvedTags = tags.length > 0 ? tags : document.tags ?? [];

  return (
    <div className="space-y-3 text-sm text-slate-600">
      <DetailRow label="Status" value={DOCUMENT_STATUS_LABELS[status]} />
      <DetailRow label="Owner" value={resolvedOwner?.name ?? "Unassigned"} />
      <DetailRow label="Size" value={formatBytes(document.byte_size)} />
      <DetailRow label="File type" value={document.content_type ?? "--"} />
      <DetailRow label="Tags" value={resolvedTags.join(", ") || "--"} />
      <DetailRow label="Uploaded" value={new Date(document.created_at).toLocaleString()} />
      <DetailRow label="Updated" value={new Date(document.updated_at).toLocaleString()} />
    </div>
  );
}

function DocumentHistory({
  document,
  lastRun,
}: {
  readonly document: DocumentRecord;
  readonly lastRun: DocumentLastRun | null | undefined;
}) {
  return (
    <div className="space-y-4 text-sm text-slate-600">
      <HistoryRow
        title="Uploaded"
        description={`Uploaded by ${document.uploader?.name ?? document.uploader?.email ?? "Unknown"}`}
        timestamp={document.created_at}
      />
      {lastRun ? (
        <HistoryRow
          title={`Run ${lastRun.status}`}
          description={lastRun.message ?? "Latest run activity."}
          timestamp={lastRun.run_at ?? document.updated_at}
        />
      ) : (
        <HistoryRow title="No runs yet" description="Processing will start automatically." timestamp={document.updated_at} />
      )}
    </div>
  );
}

function DetailRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-right font-medium text-slate-700">{value}</div>
    </div>
  );
}

function HistoryRow({
  title,
  description,
  timestamp,
}: {
  readonly title: string;
  readonly description: string;
  readonly timestamp: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <div className="mt-1 text-sm text-slate-500">{description}</div>
      <div className="mt-1 text-xs text-slate-400">{new Date(timestamp).toLocaleString()}</div>
    </div>
  );
}

/* -------------------------------- States & helpers ------------------------------- */

function EmptyState({ onUploadClick }: { readonly onUploadClick: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-6">
      <PageState
        title="No documents yet"
        description="Upload a file to begin processing. We will keep the status up to date automatically."
        action={
          <Button size="sm" onClick={onUploadClick}>
            Upload documents
          </Button>
        }
      />
    </div>
  );
}

function NoResultsState({ query, onClear }: { readonly query: string; readonly onClear: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-6">
      <PageState
        title="No results"
        description={`No documents match "${query}".`}
        action={
          <Button size="sm" variant="secondary" onClick={onClear}>
            Clear search
          </Button>
        }
      />
    </div>
  );
}

function GridSkeleton() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Loading documents...
      </div>
      <div className="divide-y divide-slate-200">
        {Array.from({ length: 8 }).map((_, index) => (
          <div
            key={index}
            className="grid items-center gap-3 px-4 py-3"
            style={{ gridTemplateColumns: GRID_TEMPLATE }}
          >
            <div className="h-4 w-4 rounded bg-slate-200" />
            <div className="h-3 w-40 rounded bg-slate-200" />
            <div className="h-3 w-20 rounded bg-slate-200" />
            <div className="h-3 w-24 rounded bg-slate-200" />
            <div className="h-3 w-24 rounded bg-slate-200" />
            <div className="h-3 w-16 rounded bg-slate-200" />
            <div className="h-3 w-6 rounded bg-slate-200" />
          </div>
        ))}
      </div>
    </div>
  );
}

function BoardSkeleton() {
  return (
    <div className="flex min-h-0 flex-1 overflow-x-auto px-6 py-4">
      <div className="flex gap-4">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="flex h-72 w-72 flex-col rounded-2xl border border-slate-200 bg-white p-4">
            <div className="h-3 w-32 rounded bg-slate-200" />
            <div className="mt-3 flex-1 space-y-3">
              {Array.from({ length: 3 }).map((__, cardIndex) => (
                <div key={cardIndex} className="h-16 rounded-xl bg-slate-100" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadMoreFooter({ isLoading, onLoadMore }: { readonly isLoading: boolean; readonly onLoadMore: () => void }) {
  return (
    <div className="border-t border-slate-200 bg-white px-6 py-3 text-center">
      <Button
        variant="ghost"
        size="sm"
        isLoading={isLoading}
        onClick={onLoadMore}
        disabled={isLoading}
      >
        {isLoading ? "Loading more..." : "Load more documents"}
      </Button>
    </div>
  );
}

function UploadOverlay() {
  return (
    <div className="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-slate-900/20 backdrop-blur-sm">
      <div className="rounded-3xl border border-slate-200 bg-white px-8 py-6 text-center shadow-[0_30px_70px_-60px_rgba(15,23,42,0.7)]">
        <div className="text-sm font-semibold text-slate-900">Drop to upload</div>
        <div className="mt-1 text-sm text-slate-500">We will start processing immediately.</div>
      </div>
    </div>
  );
}

function TagList({ tags, max = 2 }: { readonly tags: readonly string[]; readonly max?: number }) {
  if (!tags || tags.length === 0) {
    return <span className="text-xs text-slate-400">Unlabeled</span>;
  }
  const visible = tags.slice(0, max);
  const remaining = tags.length - visible.length;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {visible.map((tag) => (
        <span
          key={tag}
          className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600"
        >
          {tag}
        </span>
      ))}
      {remaining > 0 ? (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">+{remaining}</span>
      ) : null}
    </div>
  );
}

function MappingBadge({ mapping }: { readonly mapping: MappingHealth | null }) {
  if (!mapping || mapping.score === null) {
    return (
      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">Mapping pending</span>
    );
  }
  const tone =
    mapping.status === "critical"
      ? "bg-rose-50 text-rose-600"
      : mapping.status === "warning"
        ? "bg-amber-50 text-amber-600"
        : "bg-emerald-50 text-emerald-600";
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-[11px] font-semibold", tone)}>
      Mapping {mapping.score}%
    </span>
  );
}

/* -------------------------------- Data hooks ------------------------------- */

function useWorkspaceDocumentsV6(workspaceId: string, sort: string) {
  return useInfiniteQuery<DocumentPage>({
    queryKey: documentsV6Keys.list(workspaceId, sort.trim() || null),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocumentsV6(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          pageSize: DOCUMENTS_PAGE_SIZE,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: workspaceId.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 15_000,
  });
}

async function fetchWorkspaceDocumentsV6(
  workspaceId: string,
  options: { sort: string | null; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<DocumentPage> {
  const query: ListDocumentsQuery = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data;
}

async function fetchWorkbookPreview(url: string, signal?: AbortSignal): Promise<WorkbookPreview> {
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) {
    throw new Error("Unable to fetch processed workbook.");
  }
  const buffer = await response.arrayBuffer();
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheets = workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, blankrows: false }) as unknown[][];
    const totalRows = rows.length;
    const totalColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const truncatedRows = totalRows > MAX_PREVIEW_ROWS;
    const truncatedColumns = totalColumns > MAX_PREVIEW_COLUMNS;
    const visibleRows = rows.slice(0, MAX_PREVIEW_ROWS).map((row) =>
      row.slice(0, MAX_PREVIEW_COLUMNS).map((cell) => normalizeCell(cell)),
    );
    const columnCount = Math.max(visibleRows[0]?.length ?? 0, totalColumns, 1);
    const headers = buildHeaders(visibleRows[0] ?? [], columnCount);
    const bodyRows = visibleRows.slice(1).map((row) => normalizeRow(row, headers.length));
    return {
      name,
      headers,
      rows: bodyRows,
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    } satisfies WorkbookSheet;
  });

  return { sheets };
}

/* -------------------------------- Utilities ------------------------------- */

function parseViewParam(value: string | null): DocumentsView {
  if (value === "board") {
    return "board";
  }
  return "grid";
}

function parseGroupParam(value: string | null): BoardGroupBy {
  if (value === "owner" || value === "tag") {
    return value;
  }
  return "status";
}

function isFileTransfer(types: DataTransfer["types"] | string[] | undefined) {
  return Array.from(types ?? []).includes("Files");
}

function isDocumentStatus(status: DisplayStatus): status is DocumentStatus {
  return Object.prototype.hasOwnProperty.call(DOCUMENT_STATUS_LABELS, status);
}

function matchesSearch(item: DocumentListItem, query: string) {
  const tokens = [item.name, item.owner?.name, item.owner?.email, ...item.tags]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return tokens.includes(query);
}

function getDisplayStatusForUpload(item: UploadItem): DisplayStatus {
  switch (item.status) {
    case "queued":
      return "queued";
    case "uploading":
      return "uploading";
    case "failed":
      return "failed-upload";
    case "cancelled":
      return "cancelled";
    case "succeeded":
      return "uploaded";
    default:
      return "uploaded";
  }
}

function buildDocumentItem(document: DocumentRecord, override?: DocumentOverride): DocumentListItem {
  const status = override?.status ?? document.status;
  const tags = override?.tags ?? document.tags ?? [];
  const owner = override?.owner ?? deriveOwner(document);
  const mapping = deriveMappingHealth(document);

  return {
    id: document.id,
    kind: "document",
    document,
    name: document.name,
    status,
    tags,
    owner,
    updatedAt: document.updated_at,
    mapping,
    processedReady: status === "processed",
    needsAttention: status === "failed" || (mapping?.issues ?? 0) > 0 || (mapping?.unmapped ?? 0) > 0,
    bytes: document.byte_size,
  };
}

function buildUploadItem(item: UploadItem, context?: UploadContext): DocumentListItem {
  const name = item.file.name;
  const owner = context?.owner ?? null;
  const tags = context?.tag ? [context.tag] : [];

  return {
    id: item.id,
    kind: "upload",
    upload: item,
    name,
    status: getDisplayStatusForUpload(item),
    tags,
    owner,
    updatedAt: new Date().toISOString(),
    mapping: null,
    processedReady: false,
    needsAttention: item.status === "failed",
    bytes: item.file.size,
  };
}

function deriveOwner(document: DocumentRecord): OwnerInfo | null {
  const metadata = document.metadata ?? {};
  const ownerFromMetadata = readOwnerFromMetadata(metadata);
  if (ownerFromMetadata) {
    return ownerFromMetadata;
  }
  if (document.uploader?.name || document.uploader?.email) {
    return {
      id: document.uploader.id,
      name: document.uploader.name ?? document.uploader.email ?? "Unassigned",
      email: document.uploader.email ?? null,
      source: "uploader",
    };
  }
  return null;
}

function readOwnerFromMetadata(metadata: Record<string, unknown>): OwnerInfo | null {
  const ownerName = typeof metadata.owner === "string" ? metadata.owner : undefined;
  const ownerEmail = typeof metadata.owner_email === "string" ? metadata.owner_email : undefined;
  if (ownerName || ownerEmail) {
    const name = ownerName ?? ownerEmail ?? "Unassigned";
    return {
      id: ownerEmail ?? ownerName ?? "owner",
      name,
      email: ownerEmail ?? null,
      source: "metadata",
    };
  }
  return null;
}

function deriveMappingHealth(document: DocumentRecord): MappingHealth | null {
  const metadata = document.metadata ?? {};
  const fromMetadata = readMappingFromMetadata(metadata);
  if (fromMetadata) {
    return fromMetadata;
  }
  if (document.status === "uploaded" || document.status === "processing") {
    return { score: null, issues: 0, unmapped: 0, status: "pending" };
  }
  const seed = hashString(document.id);
  if (document.status === "failed") {
    const score = 70 + (seed % 15);
    const issues = 2 + (seed % 4);
    return { score, issues, unmapped: Math.max(1, seed % 3), status: "critical" };
  }
  const score = 92 + (seed % 8);
  const issues = seed % 3;
  const unmapped = issues > 0 ? seed % 2 : 0;
  const status = issues === 0 ? "good" : issues === 1 ? "warning" : "critical";
  return { score, issues, unmapped, status };
}

function readMappingFromMetadata(metadata: Record<string, unknown>): MappingHealth | null {
  const candidate = metadata.mapping ?? metadata.mapping_health ?? metadata.mapping_quality;
  if (candidate && typeof candidate === "object") {
    const record = candidate as Record<string, unknown>;
    const rawScore = typeof record.score === "number" ? record.score : typeof record.health === "number" ? record.health : null;
    const score = rawScore === null ? null : rawScore <= 1 ? Math.round(rawScore * 100) : Math.round(rawScore);
    const issues = typeof record.issues === "number" ? record.issues : 0;
    const unmapped = typeof record.unmapped === "number" ? record.unmapped : 0;
    const status = issues > 2 ? "critical" : issues > 0 ? "warning" : "good";
    return { score, issues, unmapped, status };
  }
  return null;
}

function hashString(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "--";
  }
  const base = 1024;
  const power = Math.min(BYTE_UNITS.length - 1, Math.floor(Math.log(bytes) / Math.log(base)));
  const value = bytes / Math.pow(base, power);
  const formatted = value >= 10 || power === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${formatted} ${BYTE_UNITS[power]}`;
}

const RELATIVE_FORMATTER = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function formatRelativeTime(date: string) {
  const target = new Date(date).getTime();
  const now = Date.now();
  const deltaSeconds = Math.round((target - now) / 1000);
  const absSeconds = Math.abs(deltaSeconds);

  if (absSeconds < 60) {
    return RELATIVE_FORMATTER.format(deltaSeconds, "second");
  }
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (Math.abs(deltaMinutes) < 60) {
    return RELATIVE_FORMATTER.format(deltaMinutes, "minute");
  }
  const deltaHours = Math.round(deltaMinutes / 60);
  if (Math.abs(deltaHours) < 24) {
    return RELATIVE_FORMATTER.format(deltaHours, "hour");
  }
  const deltaDays = Math.round(deltaHours / 24);
  if (Math.abs(deltaDays) < 30) {
    return RELATIVE_FORMATTER.format(deltaDays, "day");
  }
  const deltaMonths = Math.round(deltaDays / 30);
  if (Math.abs(deltaMonths) < 12) {
    return RELATIVE_FORMATTER.format(deltaMonths, "month");
  }
  const deltaYears = Math.round(deltaMonths / 12);
  return RELATIVE_FORMATTER.format(deltaYears, "year");
}

function getStatusTone(status: DocumentStatus) {
  return DISPLAY_STATUS_META[status].tone;
}

function normalizeCell(value: unknown) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Date) {
    return value.toLocaleDateString();
  }
  return String(value);
}

function normalizeRow(row: string[], length: number) {
  if (row.length >= length) {
    return row;
  }
  return row.concat(Array.from({ length: length - row.length }, () => ""));
}

function buildHeaders(raw: string[], totalColumns: number) {
  const trimmed = raw.map((cell) => cell.trim());
  const hasNamed = trimmed.some(Boolean);
  const headerCount = Math.max(trimmed.length, totalColumns);
  const headers = hasNamed ? trimmed : Array.from({ length: headerCount }, (_, index) => columnLabel(index));
  return normalizeRow(headers, headerCount);
}

function columnLabel(index: number) {
  let label = "";
  let n = index + 1;
  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }
  return `Column ${label}`;
}

function buildBoardColumns(items: readonly DocumentListItem[], groupBy: BoardGroupBy): BoardColumnDescriptor[] {
  if (groupBy === "owner") {
    const owners = new Map<string, OwnerInfo | null>();
    owners.set("unassigned", null);
    items.forEach((item) => {
      if (item.owner) {
        owners.set(item.owner.id, item.owner);
      }
    });
    return Array.from(owners.values()).map((owner) => ({
      id: buildBoardColumnId({ type: "owner", value: owner }),
      label: owner?.name ?? "Unassigned",
      items: items.filter((item) => (item.owner?.id ?? "unassigned") === (owner?.id ?? "unassigned")),
      groupValue: { type: "owner", value: owner },
    }));
  }

  if (groupBy === "tag") {
    const tags = new Set<string>();
    items.forEach((item) => {
      item.tags.forEach((tag) => tags.add(tag));
    });
    const entries = [null, ...Array.from(tags.values()).sort()];
    return entries.map((tag) => ({
      id: buildBoardColumnId({ type: "tag", value: tag }),
      label: tag ?? "Untagged",
      items: items.filter((item) => getPrimaryTag(item.tags) === (tag ?? "Untagged")),
      groupValue: { type: "tag", value: tag },
    }));
  }

  return STATUS_COLUMNS.map((status) => ({
    id: buildBoardColumnId({ type: "status", value: status }),
    label: DOCUMENT_STATUS_LABELS[status],
    tone: DISPLAY_STATUS_META[status].tone,
    items: items.filter((item) => resolveStatusBucket(item) === status),
    groupValue: { type: "status", value: status },
  }));
}

function resolveStatusBucket(item: DocumentListItem): DocumentStatus {
  if (isDocumentStatus(item.status)) {
    return item.status;
  }
  return "uploaded";
}

function getPrimaryTag(tags: readonly string[]) {
  if (!tags.length) {
    return "Untagged";
  }
  return tags[0];
}

function buildBoardColumnId(group: BoardGroupValue) {
  if (group.type === "status") {
    return `status:${group.value}`;
  }
  if (group.type === "owner") {
    return `owner:${group.value?.id ?? "unassigned"}`;
  }
  return `tag:${group.value ?? "untagged"}`;
}

function parseBoardDropTarget(id: string, ownerLookup?: Map<string, OwnerInfo>): BoardGroupValue | null {
  const [type, value] = id.split(":");
  if (type === "status" && STATUS_COLUMNS.includes(value as DocumentStatus)) {
    return { type: "status", value: value as DocumentStatus };
  }
  if (type === "owner") {
    const owner = ownerLookup?.get(value);
    return {
      type: "owner",
      value: value === "unassigned" ? null : owner ?? { id: value, name: value, source: "override" },
    };
  }
  if (type === "tag") {
    return { type: "tag", value: value === "untagged" ? null : value };
  }
  return null;
}

function getUploadContextForColumn(group: BoardGroupValue): UploadContext | undefined {
  if (group.type === "owner") {
    return { owner: group.value };
  }
  if (group.type === "tag") {
    return { tag: group.value ?? null };
  }
  return undefined;
}

function isStatusMoveAllowed(current: DocumentStatus, next: DocumentStatus) {
  if (current === next) {
    return true;
  }
  const allowed: Record<DocumentStatus, DocumentStatus[]> = {
    uploaded: ["processing", "archived"],
    processing: ["processed", "failed", "archived"],
    processed: ["archived"],
    failed: ["processing", "archived"],
    archived: ["uploaded"],
  };
  return allowed[current]?.includes(next) ?? false;
}

async function downloadOriginal(workspaceId: string, documentId: string) {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
      parseAs: "blob",
    },
  );
  if (!data) {
    throw new Error("Expected document download payload.");
  }
  const filename = extractFilename(response.headers.get("content-disposition")) ?? `document-${documentId}`;
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function extractFilename(header: string | null) {
  if (!header) return null;
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1] ?? null;
}

/* -------------------------------- Icons ------------------------------- */

function SearchIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx={9} cy={9} r={6} />
      <path d="M13.5 13.5L17 17" strokeLinecap="round" />
    </svg>
  );
}

function FileIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v5a1 1 0 0 0 1 1h5" />
    </svg>
  );
}

function MoreIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <circle cx="10" cy="4" r="1.6" />
      <circle cx="10" cy="10" r="1.6" />
      <circle cx="10" cy="16" r="1.6" />
    </svg>
  );
}
