import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import clsx from "clsx";

import { useSession } from "../../features/auth/context/SessionContext";
import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import { useUploadDocumentsMutation } from "../../features/documents/hooks/useUploadDocumentsMutation";
import { useDeleteDocumentsMutation } from "../../features/documents/hooks/useDeleteDocumentsMutation";
import { downloadWorkspaceDocument } from "../../features/documents/api";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import type { WorkspaceDocumentSummary } from "../../shared/types/documents";
import type { SessionUser } from "../../shared/types/auth";
import { PageState } from "../components/PageState";
import { Alert, Button, Input } from "../../ui";
import { trackEvent } from "../../shared/telemetry/events";
import { ApiError } from "../../shared/api/client";

const OWNER_FILTER_OPTIONS = [
  { value: "mine", label: "My Documents" },
  { value: "all", label: "All Documents" },
] as const;

type OwnerFilter = (typeof OWNER_FILTER_OPTIONS)[number]["value"];

type DocumentStatus = "inbox" | "processing" | "completed" | "failed" | "archived";
type StatusFilter = DocumentStatus | "all";

const STATUS_FILTER_OPTIONS: readonly { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "inbox", label: "Inbox" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "archived", label: "Archived" },
];

const STATUS_LABELS: Record<DocumentStatus, string> = {
  inbox: "Inbox",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  archived: "Archived",
};

const STATUS_BADGE_STYLE: Record<DocumentStatus, string> = {
  inbox: "bg-indigo-100 text-indigo-700",
  processing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-danger-100 text-danger-700",
  archived: "bg-slate-200 text-slate-700",
};

const SUPPORTED_FILE_EXTENSIONS = [".pdf", ".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".xlsb"] as const;
const SUPPORTED_FILE_EXTENSION_SET = new Set(
  SUPPORTED_FILE_EXTENSIONS.map((value) => value.toLowerCase()),
);
const SUPPORTED_FILE_TYPES_LABEL = "PDF, CSV, TSV, XLS, XLSX, XLSM, XLSB";

interface DocumentTicket {
  readonly id: string;
  readonly name: string;
  readonly status: DocumentStatus;
  readonly source: string;
  readonly tags: readonly string[];
  readonly uploadedAt: Date;
  readonly byteSize: number;
  readonly contentType: string | null;
  readonly uploaderName: string;
  readonly uploaderId: string | null;
  readonly uploaderEmail: string | null;
  readonly lastRunLabel: string;
  readonly lastRunAt: Date | null;
  readonly metadata: Record<string, unknown>;
  readonly summary: WorkspaceDocumentSummary;
}

type StatusCounts = Record<StatusFilter, number>;

type FeedbackTone = "info" | "success" | "warning" | "danger";

interface FeedbackState {
  readonly tone: FeedbackTone;
  readonly message: string;
}

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const session = useSession();
  const currentUser = session.user;

  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id);
  const uploadDocuments = useUploadDocumentsMutation(workspace.id);
  const deleteDocuments = useDeleteDocumentsMutation(workspace.id);
  const { openInspector } = useWorkspaceChrome();

  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>("mine");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!currentUser.user_id && ownerFilter === "mine") {
      setOwnerFilter("all");
    }
  }, [currentUser.user_id, ownerFilter]);

  useEffect(() => {
    if (!feedback || typeof window === "undefined") {
      return;
    }
    const timer = window.setTimeout(() => setFeedback(null), 6000);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  const tickets = useMemo<readonly DocumentTicket[]>(
    () => (documentsQuery.data ?? []).map((document) => buildDocumentTicket(document)),
    [documentsQuery.data],
  );

  const statusCounts = useMemo<StatusCounts>(() => computeStatusCounts(tickets), [tickets]);

  const visibleTickets = useMemo(() => {
    const trimmedQuery = searchTerm.trim().toLowerCase();
    return tickets.filter((ticket) => {
      if (ownerFilter === "mine" && !belongsToCurrentUser(ticket, currentUser)) {
        return false;
      }
      if (statusFilter !== "all" && ticket.status !== statusFilter) {
        return false;
      }
      if (trimmedQuery.length > 0 && !ticketMatchesQuery(ticket, trimmedQuery)) {
        return false;
      }
      return true;
    });
  }, [tickets, ownerFilter, statusFilter, searchTerm, currentUser]);

  const sortedTickets = useMemo(
    () => [...visibleTickets].sort(sortTicketsByUploadedAt),
    [visibleTickets],
  );

  const handleOwnerFilterChange = useCallback(
    (value: OwnerFilter) => {
      setOwnerFilter(value);
      trackDocumentsEvent("filter_owner", workspace.id, { owner: value });
    },
    [workspace.id],
  );

  const handleStatusFilterChange = useCallback(
    (value: StatusFilter) => {
      setStatusFilter(value);
      trackDocumentsEvent("filter_status", workspace.id, { status: value });
    },
    [workspace.id],
  );

  const handleSearchChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  }, []);

  const handleUploadButtonClick = useCallback(() => {
    setFeedback(null);
    fileInputRef.current?.click();
    trackDocumentsEvent("start_upload", workspace.id);
  }, [workspace.id]);

  const handleFilesSelected = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) {
        return;
      }

      const { accepted, rejected } = partitionSupportedFiles(files);
      if (accepted.length === 0) {
        setFeedback({
          tone: "warning",
          message: `No supported files detected. Supported types: ${SUPPORTED_FILE_TYPES_LABEL}.`,
        });
        return;
      }

      setFeedback(null);

      try {
        const uploaded = await uploadDocuments.mutateAsync({ files: accepted });
        const count = uploaded.length;
        const label = count === 1 ? accepted[0]?.name ?? "Document" : `${count} documents`;
        const skipped = rejected.length
          ? ` ${rejected.length} file${rejected.length === 1 ? "" : "s"} skipped (unsupported type).`
          : "";
        setFeedback({
          tone: "success",
          message: `${label} uploaded.${skipped}`,
        });
        trackDocumentsEvent(count === 1 ? "upload" : "bulk_upload", workspace.id, {
          documentId: uploaded[0]?.id,
          count,
        });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to upload documents. Try again."),
        });
      }
    },
    [uploadDocuments, workspace.id],
  );

  const handleFileInputChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files ? Array.from(event.target.files) : [];
      event.target.value = "";
      if (files.length === 0) {
        return;
      }
      await handleFilesSelected(files);
    },
    [handleFilesSelected],
  );

  const handleDownloadTicket = useCallback(
    async (ticket: DocumentTicket) => {
      try {
        setFeedback(null);
        setDownloadingId(ticket.id);
        const { blob, filename } = await downloadWorkspaceDocument(workspace.id, ticket.id);
        triggerBrowserDownload(blob, filename);
        trackDocumentsEvent("download", workspace.id, { documentId: ticket.id });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to download document. Try again."),
        });
      } finally {
        setDownloadingId(null);
      }
    },
    [workspace.id],
  );

  const handleDeleteTicket = useCallback(
    async (ticket: DocumentTicket) => {
      if (typeof window !== "undefined") {
        const confirmed = window.confirm(`Delete ${ticket.name}? This action cannot be undone.`);
        if (!confirmed) {
          return;
        }
      }

      try {
        setFeedback(null);
        setDeletingId(ticket.id);
        await deleteDocuments.mutateAsync([ticket.id]);
        setFeedback({ tone: "success", message: "Document deleted." });
        trackDocumentsEvent("delete", workspace.id, { documentId: ticket.id });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to delete document. Try again."),
        });
      } finally {
        setDeletingId(null);
      }
    },
    [deleteDocuments, workspace.id],
  );

  const handleViewTicket = useCallback(
    (ticket: DocumentTicket) => {
      openInspector({
        title: ticket.name,
        content: <DocumentInspector ticket={ticket} />,
      });
      trackDocumentsEvent("view_details", workspace.id, { documentId: ticket.id });
    },
    [openInspector, workspace.id],
  );

  const hasTickets = tickets.length > 0;
  const hasVisibleTickets = sortedTickets.length > 0;
  const showSwitchToAll = ownerFilter === "mine" && hasTickets && !hasVisibleTickets;

  if (documentsQuery.isLoading) {
    return (
      <PageState
        title="Loading documents"
        description="Fetching workspace documents."
        variant="loading"
      />
    );
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <section className="space-y-6">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={SUPPORTED_FILE_EXTENSIONS.join(",")}
        className="hidden"
        onChange={handleFileInputChange}
      />

      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-slate-900">Document tickets</h1>
          <p className="text-sm text-slate-600">
            Review document uploads, track extraction progress, and manage workspace files from a ticket-style grid.
          </p>
        </div>
        <Button onClick={handleUploadButtonClick} isLoading={uploadDocuments.isPending}>
          Upload documents
        </Button>
      </header>

      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      {!hasTickets ? (
        <PageState
          title="No documents yet"
          description="Upload spreadsheets and PDFs to start processing your workspace data."
          action={
            <Button onClick={handleUploadButtonClick} isLoading={uploadDocuments.isPending}>
              Upload documents
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          <DocumentToolbar
            ownerFilter={ownerFilter}
            statusFilter={statusFilter}
            statusCounts={statusCounts}
            searchValue={searchTerm}
            onOwnerFilterChange={handleOwnerFilterChange}
            onStatusFilterChange={handleStatusFilterChange}
            onSearchChange={handleSearchChange}
          />

          {hasVisibleTickets ? (
            <DocumentTicketGrid
              tickets={sortedTickets}
              onOpen={handleViewTicket}
              onDownload={handleDownloadTicket}
              onDelete={handleDeleteTicket}
              downloadingId={downloadingId}
              deletingId={deletingId}
            />
          ) : (
            <PageState
              title={
                ownerFilter === "mine"
                  ? "No documents uploaded by you yet"
                  : "No documents match your filters"
              }
              description={
                ownerFilter === "mine"
                  ? "Switch to All Documents to browse everything uploaded to this workspace or start an upload."
                  : "Adjust your filters or clear the search query to see more documents."
              }
              action={
                showSwitchToAll ? (
                  <Button variant="secondary" onClick={() => setOwnerFilter("all")}>
                    View all documents
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setStatusFilter("all");
                      setSearchTerm("");
                    }}
                  >
                    Clear filters
                  </Button>
                )
              }
            />
          )}
        </div>
      )}
    </section>
  );
}

interface DocumentToolbarProps {
  readonly ownerFilter: OwnerFilter;
  readonly statusFilter: StatusFilter;
  readonly statusCounts: StatusCounts;
  readonly searchValue: string;
  readonly onOwnerFilterChange: (value: OwnerFilter) => void;
  readonly onStatusFilterChange: (value: StatusFilter) => void;
  readonly onSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

function DocumentToolbar({
  ownerFilter,
  statusFilter,
  statusCounts,
  searchValue,
  onOwnerFilterChange,
  onStatusFilterChange,
  onSearchChange,
}: DocumentToolbarProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-soft">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <OwnerFilterSelect value={ownerFilter} onChange={onOwnerFilterChange} />
        <div className="w-full max-w-xs">
          <Input
            type="search"
            value={searchValue}
            onChange={onSearchChange}
            placeholder="Search documents"
            aria-label="Search documents"
          />
        </div>
      </div>
      <div className="mt-4">
        <StatusFilterChips
          value={statusFilter}
          counts={statusCounts}
          onChange={onStatusFilterChange}
        />
      </div>
    </div>
  );
}

interface OwnerFilterSelectProps {
  readonly value: OwnerFilter;
  readonly onChange: (value: OwnerFilter) => void;
}

function OwnerFilterSelect({ value, onChange }: OwnerFilterSelectProps) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold text-slate-600 md:flex-row md:items-center">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Showing</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as OwnerFilter)}
        className="mt-1 w-48 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white md:ml-3 md:mt-0"
      >
        {OWNER_FILTER_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface StatusFilterChipsProps {
  readonly value: StatusFilter;
  readonly counts: StatusCounts;
  readonly onChange: (value: StatusFilter) => void;
}

function StatusFilterChips({ value, counts, onChange }: StatusFilterChipsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {STATUS_FILTER_OPTIONS.map((option) => {
        const isActive = option.value === value;
        const count = counts[option.value] ?? 0;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
              isActive
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
            )}
          >
            <span>{option.label}</span>
            <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

interface DocumentTicketGridProps {
  readonly tickets: readonly DocumentTicket[];
  readonly onOpen: (ticket: DocumentTicket) => void;
  readonly onDownload: (ticket: DocumentTicket) => void;
  readonly onDelete: (ticket: DocumentTicket) => void;
  readonly downloadingId: string | null;
  readonly deletingId: string | null;
}

function DocumentTicketGrid({
  tickets,
  onOpen,
  onDownload,
  onDelete,
  downloadingId,
  deletingId,
}: DocumentTicketGridProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
      {tickets.map((ticket) => (
        <DocumentTicketCard
          key={ticket.id}
          ticket={ticket}
          onOpen={() => onOpen(ticket)}
          onDownload={() => onDownload(ticket)}
          onDelete={() => onDelete(ticket)}
          isDownloading={downloadingId === ticket.id}
          isDeleting={deletingId === ticket.id}
        />
      ))}
    </div>
  );
}

interface DocumentTicketCardProps {
  readonly ticket: DocumentTicket;
  readonly onOpen: () => void;
  readonly onDownload: () => void;
  readonly onDelete: () => void;
  readonly isDownloading: boolean;
  readonly isDeleting: boolean;
}

function DocumentTicketCard({
  ticket,
  onOpen,
  onDownload,
  onDelete,
  isDownloading,
  isDeleting,
}: DocumentTicketCardProps) {
  const lastRunSummary = ticket.lastRunAt
    ? `${ticket.lastRunLabel} • ${formatRelativeTime(ticket.lastRunAt)}`
    : ticket.lastRunLabel;

  return (
    <article className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-soft transition hover:-translate-y-1 hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <StatusBadge status={ticket.status} />
        <span className="text-xs font-medium text-slate-400">
          Uploaded {formatRelativeTime(ticket.uploadedAt)}
        </span>
      </div>

      <button
        type="button"
        onClick={onOpen}
        className="mt-4 text-left text-lg font-semibold text-slate-900 transition hover:text-brand-600"
      >
        <span className="line-clamp-2 break-words">{ticket.name}</span>
      </button>

      <dl className="mt-4 space-y-2 text-sm text-slate-600">
        <DefinitionRow label="Uploader">{ticket.uploaderName}</DefinitionRow>
        <DefinitionRow label="Source">{ticket.source}</DefinitionRow>
        <DefinitionRow label="File size">{formatFileSize(ticket.byteSize)}</DefinitionRow>
        <DefinitionRow label="Last run">{lastRunSummary}</DefinitionRow>
      </dl>

      {ticket.tags.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {ticket.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between pt-6">
        <Button variant="ghost" size="sm" onClick={onOpen}>
          View details
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onDownload}
            isLoading={isDownloading}
          >
            Download
          </Button>
          <Button variant="danger" size="sm" onClick={onDelete} isLoading={isDeleting}>
            Delete
          </Button>
        </div>
      </div>
    </article>
  );
}

interface DefinitionRowProps {
  readonly label: string;
  readonly children: ReactNode;
}

function DefinitionRow({ label, children }: DefinitionRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm font-medium text-slate-800">{children}</dd>
    </div>
  );
}

interface DocumentInspectorProps {
  readonly ticket: DocumentTicket;
}

function DocumentInspector({ ticket }: DocumentInspectorProps) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</h3>
        <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-3 text-sm text-slate-600">
          <InspectorField label="Status">
            <StatusBadge status={ticket.status} />
          </InspectorField>
          <InspectorField label="Uploader">{ticket.uploaderName}</InspectorField>
          <InspectorField label="Uploaded">
            {formatDateTime(ticket.uploadedAt)}
          </InspectorField>
          <InspectorField label="File size">{formatFileSize(ticket.byteSize)}</InspectorField>
          <InspectorField label="Content type">
            {ticket.contentType ?? "Unknown"}
          </InspectorField>
          <InspectorField label="Last run">
            {ticket.lastRunAt ? (
              <span>
                {ticket.lastRunLabel}
                <span className="ml-1 text-slate-500">
                  ({formatDateTime(ticket.lastRunAt)})
                </span>
              </span>
            ) : (
              ticket.lastRunLabel
            )}
          </InspectorField>
        </dl>
      </section>

      {ticket.tags.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {ticket.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600"
              >
                {tag}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
        {Object.keys(ticket.metadata).length === 0 ? (
          <p className="text-sm text-slate-500">No metadata attached.</p>
        ) : (
          <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900/90 p-3 text-xs text-slate-100">
            {JSON.stringify(ticket.metadata, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}

interface InspectorFieldProps {
  readonly label: string;
  readonly children: ReactNode;
}

function InspectorField({ label, children }: InspectorFieldProps) {
  return (
    <>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-800">{children}</dd>
    </>
  );
}

interface StatusBadgeProps {
  readonly status: DocumentStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        STATUS_BADGE_STYLE[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

function computeStatusCounts(tickets: readonly DocumentTicket[]): StatusCounts {
  const counts: StatusCounts = {
    all: tickets.length,
    inbox: 0,
    processing: 0,
    completed: 0,
    failed: 0,
    archived: 0,
  };

  for (const ticket of tickets) {
    counts[ticket.status] += 1;
  }

  return counts;
}

function belongsToCurrentUser(ticket: DocumentTicket, user: SessionUser): boolean {
  if (!user) {
    return false;
  }

  if (ticket.uploaderId && user.user_id && ticket.uploaderId === user.user_id) {
    return true;
  }

  const normalizedName = (user.display_name ?? "").trim().toLowerCase();
  if (normalizedName && ticket.uploaderName.trim().toLowerCase() === normalizedName) {
    return true;
  }

  const normalizedEmail = user.email.trim().toLowerCase();
  if (ticket.uploaderEmail && ticket.uploaderEmail.trim().toLowerCase() === normalizedEmail) {
    return true;
  }

  return false;
}

function ticketMatchesQuery(ticket: DocumentTicket, query: string) {
  const target = [
    ticket.name,
    ticket.source,
    ticket.uploaderName,
    ticket.uploaderEmail ?? "",
    ...ticket.tags,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return target.includes(query);
}

function sortTicketsByUploadedAt(a: DocumentTicket, b: DocumentTicket) {
  const delta = b.uploadedAt.getTime() - a.uploadedAt.getTime();
  if (delta !== 0) {
    return delta;
  }
  return a.name.localeCompare(b.name);
}

function buildDocumentTicket(document: WorkspaceDocumentSummary): DocumentTicket {
  const metadata = document.metadata ?? {};
  const status = extractStatus(metadata);
  const source = extractString(metadata, ["source", "ingestSource"], "Manual upload");
  const tags = extractTags(metadata);
  const uploadedAt = safeDate(document.createdAt ?? document.updatedAt ?? new Date().toISOString());
  const { name, id, email } = extractUploader(metadata);
  const lastRun = extractLastRun(metadata);

  return {
    id: document.id,
    name: document.name,
    status,
    source,
    tags,
    uploadedAt,
    byteSize: document.byteSize,
    contentType: document.contentType,
    uploaderName: name,
    uploaderId: id,
    uploaderEmail: email,
    lastRunLabel: lastRun.result,
    lastRunAt: lastRun.timestamp,
    metadata,
    summary: document,
  };
}

function extractStatus(metadata: Record<string, unknown>): DocumentStatus {
  if (metadata.archived === true) {
    return "archived";
  }

  const rawStatus = extractString(metadata, ["status", "state"], "");
  switch (rawStatus.toLowerCase()) {
    case "inbox":
      return "inbox";
    case "processing":
    case "running":
      return "processing";
    case "failed":
    case "error":
      return "failed";
    case "archived":
      return "archived";
    case "completed":
    case "succeeded":
    case "success":
      return "completed";
    default:
      break;
  }

  if (metadata.processing === true) {
    return "processing";
  }
  if (metadata.failed === true) {
    return "failed";
  }

  return "completed";
}

function extractString(
  metadata: Record<string, unknown>,
  keys: readonly string[],
  fallback: string,
): string {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return fallback;
}

function extractTags(metadata: Record<string, unknown>): readonly string[] {
  const raw = metadata.tags ?? metadata.labels;
  if (Array.isArray(raw)) {
    return raw
      .map((value) => (typeof value === "string" ? value.trim() : String(value)))
      .filter((value) => value.length > 0);
  }
  if (typeof raw === "string" && raw.trim().length > 0) {
    return raw
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
  }
  return [];
}

function extractUploader(metadata: Record<string, unknown>) {
  const name = extractString(
    metadata,
    ["uploader", "uploadedBy", "createdBy", "owner", "ownerName"],
    "Unknown",
  );
  const id = extractOptionalString(metadata, [
    "uploaderId",
    "uploader_id",
    "uploadedById",
    "uploaded_by_id",
    "createdById",
    "created_by_id",
    "ownerId",
    "owner_id",
  ]);
  const email = extractOptionalString(metadata, [
    "uploaderEmail",
    "uploadedByEmail",
    "createdByEmail",
    "ownerEmail",
    "email",
  ]);
  return { name, id, email };
}

function extractOptionalString(metadata: Record<string, unknown>, keys: readonly string[]) {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return null;
}

function extractLastRun(metadata: Record<string, unknown>) {
  const raw = (metadata.lastRun ?? metadata.last_run) as
    | Record<string, unknown>
    | undefined;
  if (raw && typeof raw === "object") {
    const result = extractString(raw, ["result", "status", "outcome"], "Unknown");
    const timestampValue = raw.timestamp ?? raw.completedAt ?? raw.completed_at;
    const timestamp =
      typeof timestampValue === "string" && timestampValue.length > 0
        ? safeDate(timestampValue)
        : null;
    return {
      result: capitalize(result),
      timestamp,
    };
  }
  return { result: "Not started", timestamp: null };
}

function capitalize(value: string) {
  if (value.length === 0) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function safeDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return new Date();
  }
  return date;
}

function partitionSupportedFiles(files: readonly File[]) {
  const accepted: File[] = [];
  const rejected: File[] = [];
  for (const file of files) {
    const extension = getExtension(file.name);
    if (extension && SUPPORTED_FILE_EXTENSION_SET.has(extension)) {
      accepted.push(file);
    } else {
      rejected.push(file);
    }
  }
  return { accepted, rejected };
}

function getExtension(filename: string) {
  const index = filename.lastIndexOf(".");
  if (index === -1) {
    return "";
  }
  return filename.slice(index).toLowerCase();
}

function resolveApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.problem?.detail ?? error.message ?? fallback;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function formatDateTime(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatRelativeTime(date: Date) {
  const now = Date.now();
  const value = date.getTime();
  const deltaSeconds = Math.round((value - now) / 1000);

  const divisions: readonly [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.34524, "week"],
    [12, "month"],
    [Number.POSITIVE_INFINITY, "year"],
  ];

  let remainder = deltaSeconds;
  let unit: Intl.RelativeTimeFormatUnit = "second";

  for (const [amount, nextUnit] of divisions) {
    if (Math.abs(remainder) < amount) {
      unit = nextUnit;
      break;
    }
    remainder /= amount;
    unit = nextUnit;
  }

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  return formatter.format(Math.round(remainder), unit);
}

function trackDocumentsEvent(
  action: string,
  workspaceId: string,
  payload: Record<string, unknown> = {},
) {
  trackEvent({
    name: `documents.${action}`,
    payload: { workspaceId, ...payload },
  });
}
