import { useMemo, useState, type ButtonHTMLAttributes, type CSSProperties } from "react";
import clsx from "clsx";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";

type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

type DocumentOutput = {
  id: string;
  name: string;
  format: "CSV" | "XLSX";
  size: string;
  rows: number;
  columns: number;
  columnsPreview: string[];
  rowsPreview: string[][];
  note?: string;
};

type DocumentEntry = {
  id: string;
  name: string;
  status: DocumentStatus;
  uploader: string;
  uploadedAt: string;
  updatedAt: string;
  size: string;
  source: string;
  tags: string[];
  config: string;
  runTime: string;
  progress?: number;
  stage?: string;
  eta?: string;
  expectedOutputs?: number;
  outputs?: DocumentOutput[];
  error?: {
    summary: string;
    detail: string;
    lastAttempt: string;
  };
};

const THEME_STYLE = {
  "--v3-bg": "#f5f1ea",
  "--v3-surface": "#fffdfa",
  "--v3-surface-strong": "#ffffff",
  "--v3-surface-muted": "#fbf7f0",
  "--v3-ink": "#1f262a",
  "--v3-muted": "#5d6b73",
  "--v3-line": "#e4dfd4",
  "--v3-accent": "#0f766e",
  "--v3-accent-strong": "#0b615a",
  "--v3-accent-soft": "#d6efe7",
  "--v3-warning": "#d97706",
  "--v3-danger": "#b42318",
  "--v3-shadow": "0 32px 80px -60px rgb(var(--color-shadow) / 0.65)",
  background: "radial-gradient(120% 120% at 5% 0%, #fff4e3 0%, #f5f1ea 45%, #efe9e0 100%)",
} as CSSProperties;

const STATUS_STYLES: Record<
  DocumentStatus,
  {
    label: string;
    pill: string;
    stripe: string;
    icon: string;
    badge: string;
    text: string;
  }
> = {
  ready: {
    label: "Ready",
    pill: "border-emerald-200 bg-emerald-50 text-emerald-700",
    stripe: "bg-emerald-500",
    icon: "text-emerald-600",
    badge: "bg-emerald-50/80 border-emerald-100",
    text: "text-emerald-700",
  },
  processing: {
    label: "Processing",
    pill: "border-amber-200 bg-amber-50 text-amber-700",
    stripe: "bg-amber-500",
    icon: "text-amber-600",
    badge: "bg-amber-50/80 border-amber-100",
    text: "text-amber-700",
  },
  failed: {
    label: "Failed",
    pill: "border-rose-200 bg-rose-50 text-rose-700",
    stripe: "bg-rose-500",
    icon: "text-rose-600",
    badge: "bg-rose-50/80 border-rose-100",
    text: "text-rose-700",
  },
  uploaded: {
    label: "Queued",
    pill: "border-border bg-background text-muted-foreground",
    stripe: "bg-muted-foreground",
    icon: "text-muted-foreground",
    badge: "bg-background/80 border-border",
    text: "text-muted-foreground",
  },
};

const DOCUMENTS: DocumentEntry[] = [
  {
    id: "doc-1",
    name: "Invoice_22384.xlsx",
    status: "ready",
    uploader: "Ava Brooks",
    uploadedAt: "Today 8:14 AM",
    updatedAt: "2m ago",
    size: "1.4 MB",
    source: "Email intake",
    tags: ["invoices", "north"],
    config: "AP Invoices v3",
    runTime: "1m 14s",
    outputs: [
      {
        id: "out-1",
        name: "Invoices_Normalized",
        format: "CSV",
        size: "86 KB",
        rows: 342,
        columns: 14,
        columnsPreview: ["invoice_id", "vendor", "amount", "due_date"],
        rowsPreview: [
          ["22384", "Northwind", "$12,340.20", "2024-08-04"],
          ["22385", "Meridian", "$1,940.00", "2024-08-07"],
          ["22386", "Anderson", "$4,118.75", "2024-08-09"],
        ],
        note: "Top 3 rows",
      },
      {
        id: "out-2",
        name: "Invoice_Exceptions",
        format: "CSV",
        size: "6 KB",
        rows: 9,
        columns: 4,
        columnsPreview: ["invoice_id", "issue", "field", "value"],
        rowsPreview: [
          ["22107", "Missing VAT", "tax_rate", ""],
          ["22145", "Out of range", "amount", "$98,200.00"],
        ],
      },
    ],
  },
  {
    id: "doc-2",
    name: "Retail_Weekly_Sales.csv",
    status: "processing",
    uploader: "Ravi Patel",
    uploadedAt: "Today 8:02 AM",
    updatedAt: "3m ago",
    size: "780 KB",
    source: "SFTP drop",
    tags: ["weekly", "retail"],
    config: "Sales Normalizer",
    runTime: "2m 08s",
    progress: 62,
    stage: "Normalizing 14 columns",
    eta: "2m remaining",
    expectedOutputs: 1,
  },
  {
    id: "doc-3",
    name: "Claim_Batch_0911.pdf",
    status: "failed",
    uploader: "Noah Kim",
    uploadedAt: "Today 7:41 AM",
    updatedAt: "12m ago",
    size: "2.3 MB",
    source: "Portal upload",
    tags: ["claims", "urgent"],
    config: "Claims v2",
    runTime: "48s",
    error: {
      summary: "Missing policy_id in row 18",
      detail: "Validation rule: policy_id must be present for every record.",
      lastAttempt: "Retry 12m ago",
    },
  },
  {
    id: "doc-4",
    name: "Payroll_0315.csv",
    status: "uploaded",
    uploader: "Jess Stone",
    uploadedAt: "Just now",
    updatedAt: "Queued",
    size: "640 KB",
    source: "Drag and drop",
    tags: ["payroll"],
    config: "Payroll Standard",
    runTime: "--",
    expectedOutputs: 2,
  },
  {
    id: "doc-5",
    name: "Vendor_Master_2024.xlsx",
    status: "ready",
    uploader: "Grace Lin",
    uploadedAt: "Today 6:58 AM",
    updatedAt: "28m ago",
    size: "4.8 MB",
    source: "OneDrive sync",
    tags: ["vendors", "master"],
    config: "Vendor Master v1",
    runTime: "2m 02s",
    outputs: [
      {
        id: "out-3",
        name: "Vendors_Normalized",
        format: "XLSX",
        size: "112 KB",
        rows: 1120,
        columns: 22,
        columnsPreview: ["vendor_id", "name", "status", "country"],
        rowsPreview: [
          ["V-1132", "Apex Supply", "active", "US"],
          ["V-1133", "Metro Parts", "active", "CA"],
          ["V-1134", "Summit Co", "hold", "US"],
        ],
        note: "Sample rows",
      },
      {
        id: "out-4",
        name: "Vendor_Changes",
        format: "CSV",
        size: "14 KB",
        rows: 62,
        columns: 5,
        columnsPreview: ["vendor_id", "change", "field", "old", "new"],
        rowsPreview: [
          ["V-0991", "updated", "status", "hold", "active"],
          ["V-1022", "updated", "payment_terms", "Net30", "Net45"],
        ],
      },
    ],
  },
  {
    id: "doc-6",
    name: "Inventory_Q3_Recon.xlsx",
    status: "processing",
    uploader: "Mason Lee",
    uploadedAt: "Today 6:40 AM",
    updatedAt: "18m ago",
    size: "1.9 MB",
    source: "Batch upload",
    tags: ["inventory", "recon"],
    config: "Inventory Reconcile",
    runTime: "3m 10s",
    progress: 38,
    stage: "Matching SKU list",
    eta: "5m remaining",
    expectedOutputs: 2,
  },
];

const STATUS_FILTERS: Array<{ id: DocumentStatus; label: string }> = [
  { id: "ready", label: "Ready" },
  { id: "processing", label: "Processing" },
  { id: "failed", label: "Failed" },
  { id: "uploaded", label: "Queued" },
];

export default function DocumentsV3Screen() {
  return (
    <RequireSession>
      <DocumentsV3Content />
    </RequireSession>
  );
}

export function DocumentsV3Content() {
  const session = useSession();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilters, setStatusFilters] = useState<Set<DocumentStatus>>(() => new Set());
  const initialExpanded = DOCUMENTS.find((doc) => doc.status === "ready")?.id;
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    () => new Set(initialExpanded ? [initialExpanded] : []),
  );
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());

  const statusCounts = useMemo(() => {
    return DOCUMENTS.reduce(
      (acc, doc) => {
        acc[doc.status] += 1;
        return acc;
      },
      { uploaded: 0, processing: 0, ready: 0, failed: 0 },
    );
  }, []);

  const normalizedSearch = searchQuery.trim().toLowerCase();
  const filteredDocuments = useMemo(() => {
    return DOCUMENTS.filter((doc) => {
      const matchesStatus = statusFilters.size === 0 || statusFilters.has(doc.status);
      if (!matchesStatus) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      const matchesText =
        doc.name.toLowerCase().includes(normalizedSearch) ||
        doc.uploader.toLowerCase().includes(normalizedSearch) ||
        doc.tags.some((tag) => tag.toLowerCase().includes(normalizedSearch)) ||
        doc.config.toLowerCase().includes(normalizedSearch);
      return matchesText;
    });
  }, [normalizedSearch, statusFilters]);

  const selectedVisibleCount = useMemo(
    () => filteredDocuments.filter((doc) => selectedIds.has(doc.id)).length,
    [filteredDocuments, selectedIds],
  );
  const allVisibleSelected = filteredDocuments.length > 0 && selectedVisibleCount === filteredDocuments.length;
  const hasActiveFilters = statusFilters.size > 0 || normalizedSearch.length > 0;

  const viewCounts = useMemo(() => {
    return filteredDocuments.reduce(
      (acc, doc) => {
        acc[doc.status] += 1;
        return acc;
      },
      { uploaded: 0, processing: 0, ready: 0, failed: 0 },
    );
  }, [filteredDocuments]);

  const displayName = session.user.display_name || session.user.email || "there";
  const { ready: readyCount, processing: processingCount, failed: failedCount } = statusCounts;
  const systemMood = failedCount > 0 ? "Needs attention" : processingCount > 0 ? "Processing" : "Calm";
  const systemMessage =
    failedCount > 0
      ? `${failedCount} failed, check the error cards.`
      : processingCount > 0
        ? `${processingCount} active runs in flight.`
        : "Outputs are flowing cleanly.";

  const handleToggleStatus = (status: DocumentStatus) => {
    setStatusFilters((current) => {
      const next = new Set(current);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
  };

  const handleToggleExpand = (id: string) => {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSelectAllVisible = (checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      filteredDocuments.forEach((doc) => {
        if (checked) {
          next.add(doc.id);
        } else {
          next.delete(doc.id);
        }
      });
      return next;
    });
  };

  const handleClearFilters = () => {
    setStatusFilters(new Set());
    setSearchQuery("");
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  return (
    <div className="documents-v3 relative min-h-screen text-[color:var(--v3-ink)]" style={THEME_STYLE}>
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 right-[-10%] h-72 w-72 rounded-full bg-[color:var(--v3-accent-soft)] blur-3xl opacity-70" />
        <div className="absolute left-[-15%] top-24 h-80 w-80 rounded-full bg-[#f3e6d5] blur-3xl opacity-70" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(255,255,255,0.75),transparent_60%)]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-6xl flex-col px-4 pb-16 pt-10 sm:px-6 lg:px-10">
        <header className="docs-v3-animate space-y-6" style={{ "--delay": "40ms" } as CSSProperties}>
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-[0.3em] text-[color:var(--v3-muted)]">
                <span className="inline-flex items-center gap-2 rounded-full bg-[color:var(--v3-surface)] px-3 py-1 shadow-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--v3-accent)] opacity-30" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-[color:var(--v3-accent-strong)]" />
                  </span>
                  Live feed
                </span>
                <span className="text-[0.65rem] tracking-[0.3em]">Updated 12s ago</span>
              </div>
              <h1 className="docs-v3-title text-4xl font-semibold tracking-tight text-[color:var(--v3-ink)] sm:text-5xl">
                Documents
              </h1>
              <p className="text-sm text-[color:var(--v3-muted)]">
                Hi {displayName}. {readyCount} ready, {processingCount} processing, {failedCount} need attention.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <ActionButton variant="primary">
                <UploadIcon className="h-4 w-4" />
                Upload
              </ActionButton>
              <ActionButton variant="outline">New intake</ActionButton>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex min-w-[240px] flex-1 items-center gap-2 rounded-full border border-[color:var(--v3-line)] bg-card/80 px-4 py-2 text-sm shadow-sm">
              <SearchIcon className="h-4 w-4 text-[color:var(--v3-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search the live feed"
                className="w-full bg-transparent text-sm text-[color:var(--v3-ink)] placeholder:text-[color:var(--v3-muted)] focus:outline-none"
                aria-label="Search documents"
              />
              {searchQuery ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="rounded-full px-2 py-1 text-xs font-semibold text-[color:var(--v3-muted)] transition hover:bg-[color:var(--v3-surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]"
                >
                  Clear
                </button>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {STATUS_FILTERS.map((filter) => (
                <FilterChip
                  key={filter.id}
                  label={filter.label}
                  count={statusCounts[filter.id]}
                  status={filter.id}
                  active={statusFilters.has(filter.id)}
                  onClick={() => handleToggleStatus(filter.id)}
                />
              ))}
              {hasActiveFilters ? (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[color:var(--v3-muted)] transition hover:border-[color:var(--v3-line)] hover:bg-card/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]"
                >
                  Reset
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--v3-muted)]">
              <StatusRhythm documents={DOCUMENTS} />
              <span className="rounded-full border border-[color:var(--v3-line)] bg-card/70 px-3 py-1">
                System mood: {systemMood}
              </span>
              <span>{systemMessage}</span>
            </div>
            <div className="text-xs text-[color:var(--v3-muted)]">Sort: Most recent</div>
          </div>
        </header>

        <section
          className="docs-v3-animate mt-8 overflow-hidden rounded-[28px] border border-[color:var(--v3-line)] bg-[color:var(--v3-surface)] shadow-[var(--v3-shadow)]"
          style={{ "--delay": "120ms" } as CSSProperties}
        >
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--v3-line)] px-5 py-4 sm:px-6">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={allVisibleSelected}
                onChange={(event) => handleSelectAllVisible(event.target.checked)}
                className="h-4 w-4 rounded border-[color:var(--v3-line)] accent-[color:var(--v3-accent)]"
                aria-label="Select all documents in view"
              />
              <div>
                <p className="text-sm font-semibold text-[color:var(--v3-ink)]">Stream</p>
                <p className="text-xs text-[color:var(--v3-muted)]">{filteredDocuments.length} documents in view</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--v3-muted)]">
              <span>{viewCounts.processing} processing</span>
              <span>{viewCounts.failed} failed</span>
              <span>{viewCounts.ready} ready</span>
            </div>
          </div>

          <div className="space-y-4 px-5 py-5 sm:px-6">
            {selectedVisibleCount > 0 ? (
              <InlineSelectionBar count={selectedVisibleCount} onClear={handleClearSelection} />
            ) : null}

            {filteredDocuments.length > 0 ? (
              <SystemPulseCard processing={viewCounts.processing} failed={viewCounts.failed} />
            ) : null}

            {filteredDocuments.length === 0 ? (
              <EmptyState onReset={hasActiveFilters ? handleClearFilters : undefined} />
            ) : (
              <div className="space-y-4">
                {filteredDocuments.map((doc, index) => (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    index={index}
                    expanded={expandedIds.has(doc.id)}
                    selected={selectedIds.has(doc.id)}
                    onToggleExpand={() => handleToggleExpand(doc.id)}
                    onToggleSelect={() => handleToggleSelect(doc.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

interface DocumentRowProps {
  readonly doc: DocumentEntry;
  readonly index: number;
  readonly expanded: boolean;
  readonly selected: boolean;
  readonly onToggleExpand: () => void;
  readonly onToggleSelect: () => void;
}

function DocumentRow({ doc, index, expanded, selected, onToggleExpand, onToggleSelect }: DocumentRowProps) {
  const statusStyle = STATUS_STYLES[doc.status];
  const panelId = `${doc.id}-details`;
  const outputCount = doc.outputs?.length ?? 0;

  return (
    <article
      className="docs-v3-animate relative overflow-hidden rounded-2xl border border-[color:var(--v3-line)] bg-card/80"
      style={{ "--delay": `${180 + index * 70}ms` } as CSSProperties}
    >
      <span className={clsx("absolute left-0 top-0 h-full w-1.5", statusStyle.stripe)} aria-hidden />
      <div className="flex flex-col gap-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-start gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="mt-1 h-4 w-4 rounded border-[color:var(--v3-line)] accent-[color:var(--v3-accent)]"
            aria-label={`Select ${doc.name}`}
          />
          <div className="flex min-w-[220px] flex-1 items-start gap-3">
            <div
              className={clsx(
                "flex h-11 w-11 items-center justify-center rounded-2xl border",
                statusStyle.badge,
              )}
            >
              <StatusIcon status={doc.status} className={clsx("h-5 w-5", statusStyle.icon)} />
            </div>
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={onToggleExpand}
                className="flex w-full flex-col text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]"
                aria-expanded={expanded}
                aria-controls={panelId}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-base font-semibold text-[color:var(--v3-ink)]">
                    {doc.name}
                  </span>
                  {doc.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-[color:var(--v3-line)] bg-card/70 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[color:var(--v3-muted)]">
                  <span>{doc.uploader}</span>
                  <span>{doc.size}</span>
                  <span>{doc.uploadedAt}</span>
                  <span>{doc.source}</span>
                </div>
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={doc.status} />
            <span className="text-xs text-[color:var(--v3-muted)]">{doc.updatedAt}</span>
            <button
              type="button"
              onClick={onToggleExpand}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[color:var(--v3-line)] bg-card/80 text-[color:var(--v3-muted)] transition hover:bg-[color:var(--v3-surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]"
              aria-label={expanded ? `Collapse ${doc.name}` : `Expand ${doc.name}`}
              aria-expanded={expanded}
            >
              <ChevronIcon className={clsx("h-4 w-4 transition", expanded && "rotate-180")} />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--v3-muted)]">
          {doc.status === "ready" ? (
            <>
              <span className={clsx("rounded-full border px-2 py-1", statusStyle.pill)}>{statusStyle.label}</span>
              <span>{outputCount} outputs</span>
              {doc.outputs?.[0] ? (
                <span>
                  Primary output: {doc.outputs[0].rows} rows, {doc.outputs[0].columns} columns
                </span>
              ) : null}
            </>
          ) : null}
          {doc.status === "processing" ? (
            <>
              <span className={clsx("rounded-full border px-2 py-1", statusStyle.pill)}>{statusStyle.label}</span>
              <span>{doc.stage}</span>
              <span>{doc.eta}</span>
            </>
          ) : null}
          {doc.status === "failed" ? (
            <>
              <span className={clsx("rounded-full border px-2 py-1", statusStyle.pill)}>{statusStyle.label}</span>
              <span className="text-rose-700">{doc.error?.summary}</span>
            </>
          ) : null}
          {doc.status === "uploaded" ? (
            <>
              <span className={clsx("rounded-full border px-2 py-1", statusStyle.pill)}>{statusStyle.label}</span>
              <span>Queued for processing</span>
              <span>{doc.expectedOutputs} outputs expected</span>
            </>
          ) : null}
        </div>

        {expanded ? <DocumentExpanded doc={doc} panelId={panelId} /> : null}
      </div>
    </article>
  );
}

function DocumentExpanded({ doc, panelId }: { readonly doc: DocumentEntry; readonly panelId: string }) {
  if (doc.status === "ready" && doc.outputs?.length) {
    const [primary, ...secondary] = doc.outputs;

    return (
      <div id={panelId} className="mt-4 space-y-4">
        <div className="rounded-2xl border border-[color:var(--v3-line)] bg-card/90 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">
                Processed output
              </p>
              <h3 className="text-lg font-semibold text-[color:var(--v3-ink)]">{primary.name}</h3>
              <p className="text-xs text-[color:var(--v3-muted)]">
                {primary.rows} rows, {primary.columns} columns, {primary.size}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ActionButton variant="primary" size="sm">
                <DownloadIcon className="h-4 w-4" />
                Download {primary.format}
              </ActionButton>
              <ActionButton variant="ghost" size="sm">
                Open run
              </ActionButton>
            </div>
          </div>

          <PreviewTable output={primary} />

          {secondary.length > 0 ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {secondary.map((output) => (
                <div
                  key={output.id}
                  className="rounded-xl border border-[color:var(--v3-line)] bg-[color:var(--v3-surface-muted)] p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[color:var(--v3-ink)]">{output.name}</p>
                      <p className="text-xs text-[color:var(--v3-muted)]">
                        {output.rows} rows, {output.columns} columns
                      </p>
                    </div>
                    <ActionButton variant="outline" size="sm">
                      Download
                    </ActionButton>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div className="rounded-2xl border border-[color:var(--v3-line)] bg-card/80 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">Run notes</p>
            <div className="mt-3 grid gap-2 text-xs text-[color:var(--v3-muted)]">
              <div className="flex items-center justify-between">
                <span>Config</span>
                <span className="font-semibold text-[color:var(--v3-ink)]">{doc.config}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Runtime</span>
                <span className="font-semibold text-[color:var(--v3-ink)]">{doc.runTime}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Source</span>
                <span className="font-semibold text-[color:var(--v3-ink)]">{doc.source}</span>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-[color:var(--v3-line)] bg-[color:var(--v3-surface-muted)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">
              Original file
            </p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--v3-ink)]">{doc.name}</p>
            <p className="text-xs text-[color:var(--v3-muted)]">
              Uploaded {doc.uploadedAt} by {doc.uploader}
            </p>
            <ActionButton variant="outline" size="sm" className="mt-3">
              Download original
            </ActionButton>
          </div>
        </div>
      </div>
    );
  }

  if (doc.status === "processing") {
    return (
      <div id={panelId} className="mt-4 space-y-4">
        <div className="rounded-2xl border border-[color:var(--v3-line)] bg-card/90 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">
                Processing output
              </p>
              <h3 className="text-lg font-semibold text-[color:var(--v3-ink)]">{doc.stage}</h3>
              <p className="text-xs text-[color:var(--v3-muted)]">{doc.eta}</p>
            </div>
            <span className="text-sm font-semibold text-[color:var(--v3-accent)]">{doc.progress}%</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-[color:var(--v3-line)]">
            <div
              className="h-full rounded-full bg-[color:var(--v3-accent)]"
              style={{ width: `${doc.progress}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-[color:var(--v3-muted)]">
            <span>Config: {doc.config}</span>
            <span>Runtime so far: {doc.runTime}</span>
            <span>{doc.expectedOutputs} outputs expected</span>
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--v3-line)] bg-[color:var(--v3-surface-muted)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">
                Live preview
              </p>
              <p className="text-sm text-[color:var(--v3-ink)]">Streaming rows as they land.</p>
            </div>
            <ActionButton variant="ghost" size="sm">
              Pause
            </ActionButton>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-[color:var(--v3-muted)]">
            <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-[color:var(--v3-accent)]" />
            Sampling partial output...
          </div>
        </div>
      </div>
    );
  }

  if (doc.status === "failed" && doc.error) {
    return (
      <div id={panelId} className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-600">Validation failed</p>
          <h3 className="mt-2 text-lg font-semibold text-rose-900">{doc.error.summary}</h3>
          <p className="mt-2 text-sm text-rose-800">{doc.error.detail}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton variant="danger" size="sm">
              <RetryIcon className="h-4 w-4" />
              Retry
            </ActionButton>
            <ActionButton variant="outline" size="sm">
              Review mapping
            </ActionButton>
          </div>
        </div>
        <div className="rounded-2xl border border-[color:var(--v3-line)] bg-card/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">
            Last attempt
          </p>
          <p className="mt-2 text-sm font-semibold text-[color:var(--v3-ink)]">{doc.error.lastAttempt}</p>
          <div className="mt-3 space-y-2 text-xs text-[color:var(--v3-muted)]">
            <div>Config: {doc.config}</div>
            <div>Source: {doc.source}</div>
            <div>Uploaded by {doc.uploader}</div>
          </div>
          <ActionButton variant="outline" size="sm" className="mt-3">
            Download original
          </ActionButton>
        </div>
      </div>
    );
  }

  return (
    <div id={panelId} className="mt-4 rounded-2xl border border-[color:var(--v3-line)] bg-card/80 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v3-muted)]">Queued</p>
      <h3 className="mt-2 text-lg font-semibold text-[color:var(--v3-ink)]">Waiting for a processing slot</h3>
      <p className="text-sm text-[color:var(--v3-muted)]">
        We will start this run shortly and keep the feed updated.
      </p>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-[color:var(--v3-muted)]">
        <span>Config: {doc.config}</span>
        <span>{doc.expectedOutputs} outputs expected</span>
      </div>
      <ActionButton variant="ghost" size="sm" className="mt-3">
        Cancel
      </ActionButton>
    </div>
  );
}

function PreviewTable({ output }: { readonly output: DocumentOutput }) {
  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-[color:var(--v3-line)] bg-card">
      <div className="flex items-center justify-between border-b border-[color:var(--v3-line)] bg-[color:var(--v3-surface-muted)] px-3 py-2 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-[color:var(--v3-muted)]">
        <span>Preview</span>
        {output.note ? <span>{output.note}</span> : null}
      </div>
      <table className="w-full text-left text-xs">
        <thead className="bg-card">
          <tr>
            {output.columnsPreview.map((column) => (
              <th
                key={column}
                className="border-b border-[color:var(--v3-line)] px-3 py-2 font-semibold text-[color:var(--v3-muted)]"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {output.rowsPreview.map((row, rowIndex) => (
            <tr key={`${output.id}-row-${rowIndex}`} className="border-b border-[color:var(--v3-line)]">
              {row.map((cell, cellIndex) => (
                <td key={`${output.id}-cell-${rowIndex}-${cellIndex}`} className="px-3 py-2 text-[color:var(--v3-ink)]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusRhythm({ documents }: { readonly documents: DocumentEntry[] }) {
  const sample = documents.slice(0, 24);
  const remaining = documents.length - sample.length;
  return (
    <div className="flex items-end gap-1">
      {sample.map((doc) => (
        <span
          key={`rhythm-${doc.id}`}
          className={clsx("h-6 w-2 rounded-full", STATUS_STYLES[doc.status].stripe)}
          aria-hidden
        />
      ))}
      {remaining > 0 ? (
        <span className="ml-1 text-[0.6rem] font-semibold text-[color:var(--v3-muted)]">+{remaining}</span>
      ) : null}
    </div>
  );
}

function StatusBadge({ status }: { readonly status: DocumentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.stripe)} aria-hidden />
      {style.label}
    </span>
  );
}

interface FilterChipProps {
  readonly label: string;
  readonly count: number;
  readonly status: DocumentStatus;
  readonly active: boolean;
  readonly onClick: () => void;
}

function FilterChip({ label, count, status, active, onClick }: FilterChipProps) {
  const style = STATUS_STYLES[status];
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]",
        active
          ? clsx("border-transparent bg-card/90 shadow-sm", style.text)
          : "border-[color:var(--v3-line)] bg-card/70 text-[color:var(--v3-muted)]",
      )}
      aria-pressed={active}
    >
      <span className={clsx("h-2 w-2 rounded-full", style.stripe)} aria-hidden />
      {label}
      <span className="rounded-full bg-card px-2 py-0.5 text-[0.6rem] font-semibold text-[color:var(--v3-muted)]">
        {count}
      </span>
    </button>
  );
}

function InlineSelectionBar({ count, onClear }: { readonly count: number; readonly onClear: () => void }) {
  return (
    <div className="rounded-2xl border border-[color:var(--v3-line)] bg-[color:var(--v3-surface-muted)] px-4 py-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="font-semibold text-[color:var(--v3-ink)]">{count} selected</span>
        <span className="h-4 w-px bg-[color:var(--v3-line)]" />
        <ActionButton variant="primary" size="sm">
          Download outputs
        </ActionButton>
        <ActionButton variant="outline" size="sm">
          Archive
        </ActionButton>
        <ActionButton variant="ghost" size="sm">
          Retry
        </ActionButton>
        <button
          type="button"
          onClick={onClear}
          className="text-xs font-semibold text-[color:var(--v3-muted)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)]"
        >
          Clear selection
        </button>
      </div>
    </div>
  );
}

function SystemPulseCard({ processing, failed }: { readonly processing: number; readonly failed: number }) {
  const isCalm = processing === 0 && failed === 0;
  const hasErrors = failed > 0;
  return (
    <div
      className={clsx(
        "rounded-2xl border px-4 py-3 text-sm",
        isCalm
          ? "border-emerald-200 bg-emerald-50/80 text-emerald-800"
          : hasErrors
            ? "border-rose-200 bg-rose-50/80 text-rose-800"
            : "border-amber-200 bg-amber-50/80 text-amber-800",
      )}
    >
      {isCalm
        ? "All clear. The queue is quiet and outputs are ready."
        : hasErrors
          ? `Attention: ${failed} failed document${failed === 1 ? "" : "s"} need review.`
          : `Processing ${processing} document${processing === 1 ? "" : "s"}. Outputs will appear inline.`}
    </div>
  );
}

function EmptyState({ onReset }: { readonly onReset?: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-[color:var(--v3-line)] bg-card/70 px-6 py-10 text-center">
      <p className="text-lg font-semibold text-[color:var(--v3-ink)]">No documents in view</p>
      <p className="mt-2 text-sm text-[color:var(--v3-muted)]">
        Try clearing filters or upload a new file to start the flow.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <ActionButton variant="primary">Upload</ActionButton>
        {onReset ? (
          <ActionButton variant="outline" onClick={onReset}>
            Reset filters
          </ActionButton>
        ) : null}
      </div>
    </div>
  );
}

type ActionButtonVariant = "primary" | "outline" | "ghost" | "danger";
type ActionButtonSize = "sm" | "md";

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ActionButtonVariant;
  readonly size?: ActionButtonSize;
}

const ACTION_VARIANTS: Record<ActionButtonVariant, string> = {
  primary: "bg-[color:var(--v3-accent)] text-white hover:bg-[color:var(--v3-accent-strong)]",
  outline: "border border-[color:var(--v3-line)] text-[color:var(--v3-ink)] hover:bg-[color:var(--v3-surface-muted)]",
  ghost: "text-[color:var(--v3-ink)] hover:bg-[color:var(--v3-surface-muted)]",
  danger: "bg-[color:var(--v3-danger)] text-white hover:brightness-95",
};

const ACTION_SIZES: Record<ActionButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

function ActionButton({
  variant = "primary",
  size = "md",
  className,
  children,
  type = "button",
  ...props
}: ActionButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v3-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v3-bg)]",
        ACTION_VARIANTS[variant],
        ACTION_SIZES[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function StatusIcon({ status, className }: { readonly status: DocumentStatus; readonly className?: string }) {
  switch (status) {
    case "ready":
      return (
        <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M5 10.5l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "processing":
      return (
        <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
          <path d="M10 4v3" strokeLinecap="round" />
          <path d="M10 13v3" strokeLinecap="round" />
          <path d="M4 10h3" strokeLinecap="round" />
          <path d="M13 10h3" strokeLinecap="round" />
          <path d="M6.2 6.2l2.2 2.2" strokeLinecap="round" />
          <path d="M11.6 11.6l2.2 2.2" strokeLinecap="round" />
          <path d="M13.8 6.2l-2.2 2.2" strokeLinecap="round" />
          <path d="M8.4 11.6l-2.2 2.2" strokeLinecap="round" />
        </svg>
      );
    case "failed":
      return (
        <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M6 6l8 8" strokeLinecap="round" />
          <path d="M14 6l-8 8" strokeLinecap="round" />
        </svg>
      );
    case "uploaded":
    default:
      return (
        <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
          <path d="M10 4v8" strokeLinecap="round" />
          <path d="M6 8l4-4 4 4" strokeLinecap="round" />
          <path d="M4 14h12" strokeLinecap="round" />
        </svg>
      );
  }
}

function ChevronIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" />
      <path d="M13.5 13.5L17 17" strokeLinecap="round" />
    </svg>
  );
}

function DownloadIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M10 4v8" strokeLinecap="round" />
      <path d="M6 10l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16h12" strokeLinecap="round" />
    </svg>
  );
}

function UploadIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M10 14V6" strokeLinecap="round" />
      <path d="M6 10l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16h12" strokeLinecap="round" />
    </svg>
  );
}

function RetryIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 10a6 6 0 0 1 10.3-4.1" strokeLinecap="round" />
      <path d="M14.5 3.5v4h-4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 10a6 6 0 0 1-10.3 4.1" strokeLinecap="round" />
    </svg>
  );
}
