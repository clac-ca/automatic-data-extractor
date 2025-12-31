import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@app/navigation/history";

import { Button } from "@components/ui/button";
import { ContextMenu } from "@components/ui/context-menu";
import { Select } from "@components/ui/select";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@components/ui/tabs";
import type { RunResource } from "@schema";

import { MAX_PREVIEW_ROWS } from "../data";
import type {
  DocumentComment,
  DocumentEntry,
  RunMetricsResource,
  WorkspacePerson,
  WorkbookPreview,
  WorkbookSheet,
} from "../types";
import { columnLabel, formatRelativeTime, shortId } from "../utils";
import {
  ChatIcon,
  CloseIcon,
  DownloadIcon,
  FolderMinusIcon,
  FolderOpenIcon,
  LinkIcon,
  MoreIcon,
  OpenInNewIcon,
  RefreshIcon,
  UserIcon,
} from "@components/icons";
import { CommentsPanel } from "./CommentsPanel";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "./PeoplePicker";
import { TagPicker } from "./TagPicker";

type DetailsPanelTab = "details" | "notes";

export function DocumentsPreviewPane({
  workspaceId,
  document,
  now,
  activeSheetId,
  onSheetChange,

  runs,
  runsLoading: _runsLoading,
  selectedRunId,
  onSelectRun,
  activeRun,
  runLoading,
  runMetrics,

  outputUrl,
  onDownloadOutput,
  onDownloadOriginal,
  onReprocess,
  onArchive,
  onRestore,
  processingPaused,

  people,
  currentUserKey,
  currentUserLabel,
  onAssign,
  onPickUp,
  onCopyLink,
  comments,
  onAddComment,
  onEditComment,
  onDeleteComment,

  onTagsChange,

  workbook,
  workbookLoading,
  workbookError,

  onClose,
  detailsRequestId,
  detailsRequestTab,
  onDetailsRequestHandled,
}: {
  workspaceId: string;
  document: DocumentEntry | null;
  now: number;
  activeSheetId: string | null;
  onSheetChange: (id: string) => void;

  runs: RunResource[];
  runsLoading: boolean;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  activeRun: RunResource | null;
  runLoading: boolean;
  runMetrics: RunMetricsResource | null;

  outputUrl: string | null;
  onDownloadOutput: (doc: DocumentEntry | null) => void;
  onDownloadOriginal: (doc: DocumentEntry | null) => void;
  onReprocess: (doc: DocumentEntry | null) => void;
  onArchive: (doc: DocumentEntry | null) => void;
  onRestore: (doc: DocumentEntry | null) => void;
  processingPaused: boolean;

  people: WorkspacePerson[];
  currentUserKey: string;
  currentUserLabel: string;
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onPickUp: (documentId: string) => void;
  onCopyLink: (doc: DocumentEntry | null) => void;

  comments: DocumentComment[];
  onAddComment: (docId: string, body: string, mentions: { key: string; label: string }[]) => void;
  onEditComment: (docId: string, commentId: string, body: string, mentions: { key: string; label: string }[]) => void;
  onDeleteComment: (docId: string, commentId: string) => void;

  onTagsChange: (documentId: string, nextTags: string[]) => void;

  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  onClose: () => void;
  detailsRequestId?: string | null;
  detailsRequestTab?: DetailsPanelTab | null;
  onDetailsRequestHandled?: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsTab, setDetailsTab] = useState<DetailsPanelTab>("details");
  const navigate = useNavigate();

  // Close details when switching documents (keeps the preview feeling stable/intentional)
  useEffect(() => {
    setDetailsOpen(false);
    setDetailsTab("details");
  }, [document?.id]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      event.stopPropagation();
      onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const sheets = workbook?.sheets ?? [];
  const selectedSheetId = activeSheetId ?? sheets[0]?.name ?? "";
  const activeSheet = sheets.find((sheet) => sheet.name === selectedSheetId) ?? sheets[0];

  const runOptions = useMemo(() => {
    return runs.slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  }, [runs]);

  const effectiveRun = activeRun ?? (selectedRunId ? runOptions.find((r) => r.id === selectedRunId) ?? null : null) ?? runOptions[0] ?? null;

  const hasOutput = effectiveRun?.status === "succeeded" && Boolean(outputUrl);
  const runLink = effectiveRun ? `/workspaces/${workspaceId}/runs?run=${effectiveRun.id}` : null;
  const runtimeSummary = buildRuntimeSummary(effectiveRun);

  const canDownloadOutput = Boolean(document?.record && outputUrl);
  const canDownloadOriginal = Boolean(document?.record);
  const canReprocess = Boolean(document?.record && activeRun?.configuration_id && !processingPaused);

  const openDetails = (tab: DetailsPanelTab) => {
    setDetailsTab(tab);
    setDetailsOpen(true);
  };

  useEffect(() => {
    if (!detailsRequestId || detailsRequestId !== document?.id) return;
    setDetailsTab(detailsRequestTab ?? "details");
    setDetailsOpen(true);
    onDetailsRequestHandled?.();
  }, [detailsRequestId, detailsRequestTab, document?.id, onDetailsRequestHandled]);

  return (
    <div className="relative flex min-h-0 w-full flex-col">
      {/* Body: preview-first */}
      <div className="px-6 py-2">
        {!document ? (
          <div className="flex min-h-[14rem] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-background px-6 text-center text-sm text-muted-foreground">
            <p className="text-sm font-semibold text-foreground">Preview is ready when you are.</p>
            <p>Select a document from the list to see its processed output.</p>
          </div>
        ) : (
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
            <div className="relative bg-background/40">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card/90 px-4 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => onDownloadOutput(document)}
                    disabled={!canDownloadOutput}
                    title={canDownloadOutput ? "Download output" : "Output not ready"}
                  >
                    Download output
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => onDownloadOriginal(document)}
                    disabled={!canDownloadOriginal}
                    title={canDownloadOriginal ? "Download original" : "Original unavailable"}
                  >
                    Download original
                  </Button>
                  <IconButton
                    ariaLabel="Copy link"
                    title="Copy link"
                    onClick={() => onCopyLink(document)}
                    disabled={!document.record}
                  >
                    <LinkIcon className="h-4 w-4" />
                  </IconButton>
                </div>

                <div className="flex items-center gap-2">
                  {runMetrics || runtimeSummary ? (
                    <PreviewMetricsInline metrics={runMetrics} runtime={runtimeSummary} />
                  ) : null}
                  {runOptions.length > 1 ? (
                    <Select
                      value={selectedRunId ?? runOptions[0]?.id ?? ""}
                      onChange={(event) => onSelectRun(event.target.value)}
                      className="h-7 min-w-[9rem] text-[11px] shadow-sm"
                      aria-label="Select run"
                    >
                      {runOptions.map((run) => (
                        <option key={run.id} value={run.id}>
                          {shortId(run.id)} · {formatRunStatus(run.status)}
                        </option>
                      ))}
                    </Select>
                  ) : null}
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-muted-foreground transition hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() => {
                      if (runLink) navigate(runLink);
                    }}
                    disabled={!runLink}
                    aria-label="Open run details"
                    title="Open run details"
                  >
                    Run details
                    <OpenInNewIcon className="h-3 w-3" />
                  </button>
                  <PreviewActionsMenu
                    document={document}
                    canDownloadOutput={canDownloadOutput}
                    canDownloadOriginal={canDownloadOriginal}
                    canReprocess={canReprocess}
                    onDownloadOutput={onDownloadOutput}
                    onDownloadOriginal={onDownloadOriginal}
                    onCopyLink={onCopyLink}
                    onReprocess={onReprocess}
                    onArchive={onArchive}
                    onRestore={onRestore}
                    onOpenDetails={() => openDetails("details")}
                    onOpenNotes={() => openDetails("notes")}
                    onClosePreview={onClose}
                  />
                </div>
              </div>

              {hasOutput ? (
                !outputUrl ? (
                  <PreviewMessage title="Output link unavailable">
                    We could not load the processed output link yet. Try again in a moment.
                  </PreviewMessage>
                ) : workbookLoading ? (
                  <PreviewMessage title="Loading preview">
                    Fetching the processed workbook for review.
                  </PreviewMessage>
                ) : workbookError ? (
                  <PreviewMessage title="Preview unavailable">
                    The XLSX is ready to download, but we could not render the preview.
                  </PreviewMessage>
                ) : activeSheet ? (
                  <div>
                    <TabsRoot value={selectedSheetId} onValueChange={onSheetChange}>
                      {sheets.map((sheet) => (
                        <TabsContent key={sheet.name} value={sheet.name} className="max-h-[30rem] overflow-auto">
                          <PreviewTable sheet={sheet} />
                        </TabsContent>
                      ))}

                      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-card px-3 py-1">
                        <TabsList className="flex flex-wrap items-center gap-1 overflow-x-auto text-[11px] text-muted-foreground">
                          {sheets.map((sheet) => (
                            <TabsTrigger
                              key={sheet.name}
                              value={sheet.name}
                              className={clsx(
                                "rounded-t-md border border-transparent px-3 py-1 font-semibold transition",
                                selectedSheetId === sheet.name
                                  ? "-mt-px border-border bg-background text-foreground shadow-sm"
                                  : "text-muted-foreground hover:text-foreground",
                              )}
                            >
                              {sheet.name}
                            </TabsTrigger>
                          ))}
                        </TabsList>
                      </div>
                    </TabsRoot>

                    {(activeSheet.truncatedRows || activeSheet.truncatedColumns) ? (
                      <div className="border-t border-border bg-card px-4 py-2 text-[11px] text-muted-foreground">
                        Showing first {Math.min(activeSheet.totalRows, MAX_PREVIEW_ROWS)} rows
                        {activeSheet.truncatedColumns ? ` and ${activeSheet.headers.length} columns` : ""}.
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <PreviewMessage title="Preview unavailable">
                    The processed XLSX is ready to download, but we cannot render a preview here.
                  </PreviewMessage>
                )
              ) : effectiveRun?.status === "failed" ? (
                <PreviewMessage title={effectiveRun.failure_message ?? "Run failed"}>
                  {effectiveRun.failure_stage ?? "We could not complete normalization for this file."}
                </PreviewMessage>
              ) : runLoading ? (
                <PreviewMessage title="Loading run output">
                  Fetching the latest run status.
                </PreviewMessage>
              ) : (
                <PreviewMessage title={resolvePreviewTitle(document)}>
                  {document.stage ?? "Preparing normalized output"}
                </PreviewMessage>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Details drawer (progressive disclosure) */}
      {detailsOpen && document ? (
        <DetailsDrawer
          tab={detailsTab}
          onTabChange={setDetailsTab}
          document={document}
          workspaceId={workspaceId}
          now={now}
          people={people}
          currentUserKey={currentUserKey}
          currentUserLabel={currentUserLabel}
          onAssign={onAssign}
          onPickUp={onPickUp}
          onTagsChange={onTagsChange}
          comments={comments}
          onAddComment={onAddComment}
          onEditComment={onEditComment}
          onDeleteComment={onDeleteComment}
          onClose={() => setDetailsOpen(false)}
        />
      ) : null}
    </div>
  );
}

function PreviewMessage({ title, children }: { title: string; children: string }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-4 text-sm text-muted-foreground">
      <p className="font-semibold text-foreground">{title}</p>
      <p>{children}</p>
    </div>
  );
}

function resolvePreviewTitle(document: DocumentEntry) {
  if (document.queue_state === "waiting" && document.queue_reason === "processing_paused") {
    return "Processing paused";
  }
  if (document.queue_state === "waiting") return "Waiting to start";
  if (document.queue_state === "queued" || document.status === "queued") return "Queued for processing";
  if (document.status === "processing") return "Processing output";
  return "Processing output";
}

const METRICS_NUMBER_FORMATTER = new Intl.NumberFormat();

function formatMetricNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return METRICS_NUMBER_FORMATTER.format(value);
}

function pluralize(label: string, value: number) {
  return value === 1 ? label : `${label}s`;
}

function buildValidationSummary(metrics: RunMetricsResource) {
  const total = metrics.validation_issues_total;
  if (typeof total !== "number") return null;
  const totalLabel = formatMetricNumber(total);
  if (!totalLabel) return null;
  const severity = metrics.validation_max_severity;
  const label = severity === "error" || severity === "warning" || severity === "info" ? severity : "issue";
  if (total === 0) return totalLabel;
  return `${totalLabel} ${pluralize(label, total)}`;
}

function buildColumnsSummary(metrics: RunMetricsResource) {
  const mapped = metrics.column_count_mapped;
  const unmapped = metrics.column_count_unmapped;

  if (typeof mapped === "number" || typeof unmapped === "number") {
    const mappedLabel = typeof mapped === "number" ? formatMetricNumber(mapped) : null;
    const unmappedLabel = typeof unmapped === "number" ? formatMetricNumber(unmapped) : null;
    const parts: string[] = [];
    if (mappedLabel) parts.push(`${mappedLabel} mapped`);
    if (unmappedLabel) parts.push(`${unmappedLabel} unmapped`);
    if (parts.length > 0) return `Columns ${parts.join(" / ")}`;
  }

  const total = metrics.column_count_total;
  if (typeof total !== "number") return null;
  const totalLabel = formatMetricNumber(total);
  if (!totalLabel) return null;
  return `Columns ${totalLabel}`;
}

function formatDurationSeconds(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  if (minutes <= 0) return `${remaining}s`;
  return `${minutes}m ${remaining}s`;
}

function buildRuntimeSummary(run: RunResource | null) {
  if (!run) return null;
  const seconds = run.duration_seconds;
  if (typeof seconds !== "number" || Number.isNaN(seconds)) return null;
  return `Runtime ${formatDurationSeconds(seconds)}`;
}

function PreviewMetricsInline({
  metrics,
  runtime,
}: {
  metrics: RunMetricsResource | null;
  runtime?: string | null;
}) {
  const validation = metrics ? buildValidationSummary(metrics) : null;
  const columns = metrics ? buildColumnsSummary(metrics) : null;
  const parts = [validation ? `Validation ${validation}` : null, columns, runtime].filter(Boolean) as string[];

  if (parts.length === 0) return null;

  return (
    <span className="hidden lg:inline-flex items-center text-[11px] text-muted-foreground">
      {parts.join(" | ")}
    </span>
  );
}

type RunStatus = RunResource["status"];

const RUN_STATUS_STYLES: Record<
  RunStatus,
  {
    label: string;
  }
> = {
  queued: {
    label: "Queued",
  },
  running: {
    label: "Running",
  },
  succeeded: {
    label: "Succeeded",
  },
  failed: {
    label: "Failed",
  },
  cancelled: {
    label: "Cancelled",
  },
};

function formatRunStatus(status: RunStatus) {
  return RUN_STATUS_STYLES[status]?.label ?? status;
}

function PreviewTable({ sheet }: { sheet: WorkbookSheet }) {
  const columnCount = sheet.headers.length;

  return (
    <table className="min-w-full w-max text-left text-xs">
      <thead className="sticky top-0 z-10 border-b border-border bg-background/95 text-muted-foreground backdrop-blur">
        <tr>
          {Array.from({ length: columnCount }).map((_, index) => {
            const column = sheet.headers[index] ?? "";
            const label = column || columnLabel(index);
            return (
              <th
                key={`${sheet.name}-h-${index}`}
                className="max-w-[22rem] truncate px-3 py-2 text-[11px] font-semibold"
                title={label}
              >
                {label}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody className="bg-card">
        {sheet.rows.map((row, rowIndex) => (
          <tr key={`${sheet.name}-${rowIndex}`} className={clsx("border-t border-border", rowIndex % 2 === 1 && "bg-background/40")}>
            {Array.from({ length: columnCount }).map((_, cellIndex) => {
              const cell = row[cellIndex] ?? "";
              return (
                <td
                  key={`${sheet.name}-${rowIndex}-${cellIndex}`}
                  className="max-w-[22rem] truncate px-3 py-2 text-foreground"
                  title={cell}
                >
                  {cell}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function IconButton({
  children,
  onClick,
  disabled,
  ariaLabel,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  ariaLabel: string;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      title={title ?? ariaLabel}
      className={clsx(
        "inline-flex h-9 w-9 items-center justify-center rounded-md border border-transparent bg-transparent text-muted-foreground transition",
        "hover:border-border hover:bg-background hover:text-muted-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-card disabled:hover:text-muted-foreground",
      )}
    >
      {children}
    </button>
  );
}

function PreviewActionsMenu({
  document,
  canDownloadOutput,
  canDownloadOriginal,
  canReprocess,
  onDownloadOutput,
  onDownloadOriginal,
  onCopyLink,
  onReprocess,
  onArchive,
  onRestore,
  onOpenDetails,
  onOpenNotes,
  onClosePreview,
}: {
  document: DocumentEntry;
  canDownloadOutput: boolean;
  canDownloadOriginal: boolean;
  canReprocess: boolean;
  onDownloadOutput: (doc: DocumentEntry | null) => void;
  onDownloadOriginal: (doc: DocumentEntry | null) => void;
  onCopyLink: (doc: DocumentEntry | null) => void;
  onReprocess: (doc: DocumentEntry | null) => void;
  onArchive: (doc: DocumentEntry | null) => void;
  onRestore: (doc: DocumentEntry | null) => void;
  onOpenDetails: () => void;
  onOpenNotes: () => void;
  onClosePreview: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const isArchived = document.status === "archived";
  const canArchive = Boolean(document.record);

  return (
    <>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card/90 text-muted-foreground shadow-sm backdrop-blur transition hover:bg-background"
        onClick={(event) => {
          event.stopPropagation();
          setPosition({ x: event.clientX, y: event.clientY });
          setOpen(true);
        }}
        aria-label="Preview actions"
      >
        <MoreIcon className="h-4 w-4" />
      </button>

      <ContextMenu
        open={open}
        position={position}
        onClose={() => setOpen(false)}
        appearance="light"
        items={[
          {
            id: "open-details",
            label: "Open details",
            onSelect: onOpenDetails,
            icon: <UserIcon className="h-4 w-4" />,
          },
          {
            id: "open-notes",
            label: "Open notes",
            onSelect: onOpenNotes,
            icon: <ChatIcon className="h-4 w-4" />,
          },
          {
            id: "download-output",
            label: "Download output",
            onSelect: () => onDownloadOutput(document),
            disabled: !canDownloadOutput,
            icon: <DownloadIcon className="h-4 w-4" />,
            dividerAbove: true,
          },
          {
            id: "download-original",
            label: "Download original",
            onSelect: () => onDownloadOriginal(document),
            disabled: !canDownloadOriginal,
            icon: <DownloadIcon className="h-4 w-4" />,
          },
          {
            id: "copy-link",
            label: "Copy link",
            onSelect: () => onCopyLink(document),
            disabled: !document.record,
            icon: <LinkIcon className="h-4 w-4" />,
          },
          {
            id: "reprocess",
            label: "Reprocess",
            onSelect: () => onReprocess(document),
            disabled: !canReprocess,
            icon: <RefreshIcon className="h-4 w-4" />,
          },
          {
            id: isArchived ? "restore" : "archive",
            label: isArchived ? "Restore document" : "Archive document",
            onSelect: () => (isArchived ? onRestore(document) : onArchive(document)),
            disabled: !canArchive,
            icon: isArchived ? <FolderOpenIcon className="h-4 w-4" /> : <FolderMinusIcon className="h-4 w-4" />,
            dividerAbove: true,
          },
          {
            id: "close-preview",
            label: "Close preview",
            onSelect: onClosePreview,
            icon: <CloseIcon className="h-4 w-4" />,
            dividerAbove: false,
          },
        ]}
      />
    </>
  );
}

function DetailsDrawer({
  tab,
  onTabChange,
  document,
  workspaceId,
  now,
  people,
  currentUserKey,
  currentUserLabel,
  onAssign,
  onPickUp,
  onTagsChange,
  comments,
  onAddComment,
  onEditComment,
  onDeleteComment,
  onClose,
}: {
  tab: DetailsPanelTab;
  onTabChange: (tab: DetailsPanelTab) => void;

  document: DocumentEntry;
  workspaceId: string;
  now: number;

  people: WorkspacePerson[];
  currentUserKey: string;
  currentUserLabel: string;

  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onPickUp: (documentId: string) => void;
  onTagsChange: (documentId: string, nextTags: string[]) => void;

  comments: DocumentComment[];
  onAddComment: (docId: string, body: string, mentions: { key: string; label: string }[]) => void;
  onEditComment: (docId: string, commentId: string, body: string, mentions: { key: string; label: string }[]) => void;
  onDeleteComment: (docId: string, commentId: string) => void;

  onClose: () => void;
}) {
  return (
    <div className="absolute inset-0 z-20" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-overlay/10"
        onClick={onClose}
        role="presentation"
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="absolute inset-y-0 right-0 flex w-full max-w-[26rem] flex-col border-l border-border bg-card shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Document details"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">Details</p>
            <p className="truncate text-[11px] text-muted-foreground" title={document.name}>
              {document.name}
            </p>
          </div>
          <IconButton ariaLabel="Close details" title="Close" onClick={onClose}>
            <CloseIcon className="h-4 w-4" />
          </IconButton>
        </div>

        <div className="border-b border-border bg-background px-3 py-2">
          <div className="flex items-center gap-2 text-xs">
            {(["details", "notes"] as const).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => onTabChange(key)}
                className={clsx(
                  "rounded-full px-3 py-1 font-semibold transition",
                  tab === key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={tab === key}
              >
                {key === "details"
                  ? "Details"
                  : `Notes${document.comment_count ? ` (${document.comment_count})` : ""}`}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-auto px-4 py-4">
          {tab === "details" ? (
            <div className="flex flex-col gap-5">
              <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background">
                    <UserIcon className="h-4 w-4 text-muted-foreground" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">Assignee</p>
                    <p className="truncate text-sm font-semibold text-foreground">
                      {document.assignee_label ?? "Unassigned"}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {!document.assignee_key ? (
                    <Button type="button" size="sm" onClick={() => onPickUp(document.id)} className="text-xs">
                      Pick up
                    </Button>
                  ) : document.assignee_key !== currentUserKey ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => onPickUp(document.id)}
                      className="text-xs"
                    >
                      Assign to me
                    </Button>
                  ) : null}

                  <PeoplePicker
                    people={people}
                    value={[document.assignee_key ?? unassignedKey()]}
                    onChange={(keys) => onAssign(document.id, normalizeSingleAssignee(keys))}
                    placeholder="Assign…"
                    includeUnassigned
                    buttonClassName="min-w-0 max-w-[16rem] text-xs"
                  />
                </div>
              </section>

              <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Metadata</h3>
                  <span className="text-[11px] text-muted-foreground">
                    Updated {formatRelativeTime(now, document.updated_at)}
                  </span>
                </div>

                <dl className="mt-4 grid gap-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">Uploader</dt>
                    <dd className="font-semibold text-foreground">{document.uploader_label ?? "Unassigned"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">Size</dt>
                    <dd className="font-semibold text-foreground">{document.size_label}</dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Tags</h3>
                  <span className="text-[11px] text-muted-foreground">Shared</span>
                </div>

                <div className="mt-3">
                  <TagPicker
                    workspaceId={workspaceId}
                    selected={document.tags}
                    onToggle={(tag) => {
                      const nextTags = document.tags.includes(tag)
                        ? document.tags.filter((t) => t !== tag)
                        : [...document.tags, tag];
                      onTagsChange(document.id, nextTags);
                    }}
                    placeholder={document.tags.length ? "Edit tags" : "Add tags"}
                    disabled={!document.record}
                  />
                </div>
              </section>

              <section className="rounded-2xl border border-border bg-background px-4 py-3 text-xs text-muted-foreground">
                <p className="font-semibold text-foreground">Tip</p>
                <p className="mt-1">
                  Keep the preview clean: use <span className="font-semibold">Notes</span> for context,
                  and <span className="font-semibold">Tags</span> for retrieval.
                </p>
              </section>
            </div>
          ) : (
            <CommentsPanel
              now={now}
              comments={comments}
              people={people}
              currentUserKey={currentUserKey}
              currentUserLabel={currentUserLabel}
              onAdd={(body, mentions) => onAddComment(document.id, body, mentions)}
              onEdit={(commentId, body, mentions) => onEditComment(document.id, commentId, body, mentions)}
              onDelete={(commentId) => onDeleteComment(document.id, commentId)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
