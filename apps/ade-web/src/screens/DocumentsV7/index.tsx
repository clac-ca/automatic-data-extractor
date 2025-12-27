import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useNotifications } from "@shared/notifications";
import { readPreferredWorkspaceId, useWorkspacesQuery, type WorkspaceProfile } from "@shared/workspaces";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";

type DocumentStatus = "queued" | "processing" | "ready" | "failed";
type ViewMode = "grid" | "board";
type BoardGroup = "owner" | "tag" | "status";
type StatusFilter = "all" | "attention" | "processing" | "ready" | "failed" | "queued";

type MappingHealth = {
  attention: number;
  unmapped: number;
};

type DocumentSheet = {
  id: string;
  name: string;
  columns: string[];
  rows: string[][];
};

type DocumentOutput = {
  fileName: string;
  size: string;
  rows: number;
  columns: number;
  sheets: DocumentSheet[];
  previewAvailable?: boolean;
};

type DocumentError = {
  summary: string;
  detail: string;
  nextStep: string;
};

type DocumentHistoryItem = {
  id: string;
  label: string;
  at: number;
  tone?: "success" | "warning" | "danger" | "info";
};

type DocumentEntry = {
  id: string;
  name: string;
  status: DocumentStatus;
  owner: string | null;
  tags: string[];
  createdAt: number;
  updatedAt: number;
  size: string;
  progress?: number;
  stage?: string;
  etaMinutes?: number;
  output?: DocumentOutput;
  error?: DocumentError;
  mapping: MappingHealth;
  history: DocumentHistoryItem[];
};

type UploadContext = {
  owner?: string | null;
  tag?: string | null;
  status?: DocumentStatus;
};

type SavedView = {
  id: string;
  name: string;
  filters: {
    search: string;
    status: StatusFilter;
    owner: string;
    tags: string[];
  };
  view: ViewMode;
  groupBy: BoardGroup;
};

type BoardColumn = {
  id: string;
  label: string;
  context: UploadContext;
  items: DocumentEntry[];
};

const OWNER_FILTER_ALL = "__all__";
const OWNER_FILTER_UNASSIGNED = "__unassigned__";
const BOARD_UNASSIGNED_ID = "__board_unassigned__";
const BOARD_UNTAGGED_ID = "__board_untagged__";
const STORAGE_KEY = "ade.documents.v7.savedViews";
const PREVIEW_ROW_LIMIT = 7;

const THEME_STYLE: CSSProperties = {
  "--v7-bg": "#f8fafc",
  "--v7-panel": "#f1f5f9",
  "--v7-panel-strong": "#ffffff",
  "--v7-ink": "#0f172a",
  "--v7-muted": "#475569",
  "--v7-border": "#e2e8f0",
  "--v7-accent": "#4f46e5",
  "--v7-accent-strong": "#4338ca",
  "--v7-accent-soft": "#e0e7ff",
  "--v7-warn": "#b45309",
  "--v7-danger": "#b91c1c",
  "--v7-success": "#15803d",
  "--v7-shadow": "0 24px 60px -50px rgba(15, 23, 42, 0.45)",
  background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
} as CSSProperties;

const STATUS_STYLES: Record<
  DocumentStatus,
  {
    label: string;
    pill: string;
    dot: string;
    text: string;
  }
> = {
  ready: {
    label: "Ready",
    pill: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
  },
  processing: {
    label: "Processing",
    pill: "border-amber-200 bg-amber-50 text-amber-700",
    dot: "bg-amber-500",
    text: "text-amber-700",
  },
  failed: {
    label: "Failed",
    pill: "border-rose-200 bg-rose-50 text-rose-700",
    dot: "bg-rose-500",
    text: "text-rose-700",
  },
  queued: {
    label: "Queued",
    pill: "border-slate-200 bg-slate-50 text-slate-600",
    dot: "bg-slate-400",
    text: "text-slate-600",
  },
};

const STATUS_FILTERS: readonly { id: StatusFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs attention" },
  { id: "processing", label: "Processing" },
  { id: "ready", label: "Ready" },
  { id: "failed", label: "Failed" },
  { id: "queued", label: "Queued" },
];

const BOARD_GROUPS: readonly { id: BoardGroup; label: string }[] = [
  { id: "owner", label: "Owner" },
  { id: "tag", label: "Tag" },
  { id: "status", label: "Status" },
];

const SHEET_INVOICES: DocumentSheet = {
  id: "sheet-ap-1",
  name: "Normalized",
  columns: ["invoice_id", "vendor", "amount", "due_date", "category"],
  rows: [
    ["22384", "Northwind", "$12,340.20", "2024-08-04", "Supplies"],
    ["22385", "Meridian", "$1,940.00", "2024-08-07", "Services"],
    ["22386", "Anderson", "$4,118.75", "2024-08-09", "Operations"],
    ["22387", "Silverline", "$820.40", "2024-08-11", "Travel"],
    ["22388", "Fieldstone", "$3,902.10", "2024-08-12", "Supplies"],
    ["22389", "Barton", "$615.00", "2024-08-13", "Utilities"],
  ],
};

const SHEET_INVOICE_EXCEPTIONS: DocumentSheet = {
  id: "sheet-ap-2",
  name: "Exceptions",
  columns: ["invoice_id", "issue", "field", "value"],
  rows: [
    ["22107", "Missing VAT", "tax_rate", ""],
    ["22145", "Out of range", "amount", "$98,200.00"],
    ["22163", "Missing vendor", "vendor", ""],
  ],
};

const SHEET_SALES: DocumentSheet = {
  id: "sheet-sales-1",
  name: "Weekly Summary",
  columns: ["store", "week", "gross_sales", "returns", "net_sales"],
  rows: [
    ["Denver-02", "2024-W36", "$182,330", "$3,250", "$179,080"],
    ["Austin-07", "2024-W36", "$204,120", "$4,980", "$199,140"],
    ["Seattle-01", "2024-W36", "$158,200", "$2,720", "$155,480"],
    ["Miami-05", "2024-W36", "$137,440", "$1,890", "$135,550"],
    ["Raleigh-03", "2024-W36", "$119,980", "$1,110", "$118,870"],
  ],
};

const SHEET_MARKETING: DocumentSheet = {
  id: "sheet-marketing-1",
  name: "Leads",
  columns: ["lead_id", "company", "source", "score", "owner"],
  rows: [
    ["L-0091", "Greyson Labs", "Webinar", "92", "Ava Brooks"],
    ["L-0092", "Tandem Co", "Referral", "88", "Jess Stone"],
    ["L-0093", "Summit Health", "Outbound", "76", "Ravi Patel"],
    ["L-0094", "Orion Retail", "Inbound", "73", "Noah Kim"],
    ["L-0095", "Blueline", "Partner", "66", "Ava Brooks"],
  ],
};

const SHEET_REFUNDS: DocumentSheet = {
  id: "sheet-refunds-1",
  name: "Refunds",
  columns: ["refund_id", "customer", "amount", "reason", "processed_at"],
  rows: [
    ["R-7781", "Barton Logistics", "$1,240.00", "Damaged", "2024-08-22"],
    ["R-7782", "Silverline", "$312.00", "Late delivery", "2024-08-22"],
    ["R-7783", "Meridian", "$2,980.00", "Return", "2024-08-23"],
    ["R-7784", "Northwind", "$410.00", "Billing issue", "2024-08-23"],
  ],
};

const OUTPUT_AP: DocumentOutput = {
  fileName: "Northwind_AP_2024-09_normalized.xlsx",
  size: "220 KB",
  rows: 342,
  columns: 14,
  sheets: [SHEET_INVOICES, SHEET_INVOICE_EXCEPTIONS],
};

const OUTPUT_SALES: DocumentOutput = {
  fileName: "Retail_Wk36_Sales_normalized.xlsx",
  size: "640 KB",
  rows: 1214,
  columns: 12,
  sheets: [SHEET_SALES],
};

const OUTPUT_MARKETING: DocumentOutput = {
  fileName: "Marketing_Leads_Sept_normalized.xlsx",
  size: "182 KB",
  rows: 412,
  columns: 9,
  sheets: [SHEET_MARKETING],
};

const OUTPUT_REFUNDS: DocumentOutput = {
  fileName: "Customer_Refunds_Aug_normalized.xlsx",
  size: "96 KB",
  rows: 88,
  columns: 8,
  sheets: [SHEET_REFUNDS],
};

const OUTPUT_LIBRARY = [OUTPUT_AP, OUTPUT_SALES, OUTPUT_MARKETING, OUTPUT_REFUNDS];

const numberFormatter = new Intl.NumberFormat("en-US");

export default function DocumentsV7Screen() {
  return (
    <RequireSession>
      <DocumentsV7Redirect />
    </RequireSession>
  );
}

function DocumentsV7Redirect() {
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

    const target = `/workspaces/${targetWorkspace.id}/documents-v7${location.search}${location.hash}`;
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
    return <PageState title="Loading Documents v7" variant="loading" />;
  }

  if (workspacesQuery.isError) {
    return (
      <PageState
        title="Unable to load workspaces"
        description="Refresh the page or try again later."
        variant="error"
      />
    );
  }

  return null;
}

export function DocumentsV7Workbench() {
  const session = useSession();
  const { notifyToast } = useNotifications();
  const currentUserLabel = session.user.display_name || session.user.email || "You";
  const initialDocuments = useMemo(() => createSeedDocuments(currentUserLabel), [currentUserLabel]);

  const [documents, setDocuments] = useState<DocumentEntry[]>(() => initialDocuments);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [groupBy, setGroupBy] = useState<BoardGroup>("owner");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [ownerFilter, setOwnerFilter] = useState<string>(OWNER_FILTER_ALL);
  const [tagFilters, setTagFilters] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(() => initialDocuments[0]?.id ?? null);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => readSavedViews());
  const [activeViewId, setActiveViewId] = useState("preset-all");
  const [isSavingView, setIsSavingView] = useState(false);
  const [newViewName, setNewViewName] = useState("");
  const [isGridDragging, setIsGridDragging] = useState(false);
  const [activeDropColumn, setActiveDropColumn] = useState<string | null>(null);

  const notifiedReadyRef = useRef(new Set<string>());
  const searchRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingUploadContextRef = useRef<UploadContext | null>(null);

  const presetViews = useMemo<SavedView[]>(
    () => [
      {
        id: "preset-all",
        name: "All documents",
        filters: { search: "", status: "all", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "owner",
      },
      {
        id: "preset-attention",
        name: "Needs attention",
        filters: { search: "", status: "attention", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "status",
      },
      {
        id: "preset-ready",
        name: "Ready to deliver",
        filters: { search: "", status: "ready", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "owner",
      },
      {
        id: "preset-mine",
        name: "Assigned to me",
        filters: { search: "", status: "all", owner: currentUserLabel, tags: [] },
        view: "board",
        groupBy: "status",
      },
    ],
    [currentUserLabel],
  );

  const allViews = useMemo(() => [...presetViews, ...savedViews], [presetViews, savedViews]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    writeSavedViews(savedViews);
  }, [savedViews]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const nowTimestamp = Date.now();
      const completed: DocumentEntry[] = [];
      setDocuments((previous) =>
        previous.map((doc) => {
          const next = advanceDocument(doc, nowTimestamp);
          if (doc.status !== "ready" && next.status === "ready") {
            completed.push(next);
          }
          return next;
        }),
      );

      if (completed.length > 0) {
        completed.forEach((doc) => {
          if (notifiedReadyRef.current.has(doc.id)) {
            return;
          }
          notifiedReadyRef.current.add(doc.id);
          notifyToast({
            title: "Output ready",
            description: `${doc.name} is ready to download.`,
            intent: "success",
          });
        });
      }
    }, 5000);

    return () => window.clearInterval(interval);
  }, [notifyToast]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      documents.forEach((doc) => {
        if (previous.has(doc.id)) {
          next.add(doc.id);
        }
      });
      return next;
    });
  }, [documents]);

  const normalizedSearch = search.trim().toLowerCase();
  const tagOptions = useMemo(() => {
    const tagSet = new Set<string>();
    documents.forEach((doc) => {
      doc.tags.forEach((tag) => tagSet.add(tag));
    });
    return Array.from(tagSet).sort((a, b) => a.localeCompare(b));
  }, [documents]);

  const ownerOptions = useMemo(() => {
    const ownerSet = new Set<string>();
    documents.forEach((doc) => {
      if (doc.owner) {
        ownerSet.add(doc.owner);
      }
    });
    return Array.from(ownerSet).sort((a, b) => a.localeCompare(b));
  }, [documents]);

  const baseFiltered = useMemo(() => {
    return documents.filter((doc) => {
      const matchesOwner =
        ownerFilter === OWNER_FILTER_ALL
          ? true
          : ownerFilter === OWNER_FILTER_UNASSIGNED
            ? !doc.owner
            : doc.owner === ownerFilter;
      if (!matchesOwner) {
        return false;
      }
      if (tagFilters.length > 0 && !tagFilters.every((tag) => doc.tags.includes(tag))) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      const haystack = [doc.name, doc.owner ?? "", doc.tags.join(" ")].join(" ").toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [documents, normalizedSearch, ownerFilter, tagFilters]);

  const statusCounts = useMemo(() => {
    const counts: Record<StatusFilter, number> = {
      all: baseFiltered.length,
      attention: 0,
      processing: 0,
      ready: 0,
      failed: 0,
      queued: 0,
    };
    baseFiltered.forEach((doc) => {
      if (doc.status === "processing") {
        counts.processing += 1;
      }
      if (doc.status === "ready") {
        counts.ready += 1;
      }
      if (doc.status === "failed") {
        counts.failed += 1;
      }
      if (doc.status === "queued") {
        counts.queued += 1;
      }
      if (isAttention(doc)) {
        counts.attention += 1;
      }
    });
    return counts;
  }, [baseFiltered]);

  const filteredDocuments = useMemo(() => {
    return baseFiltered.filter((doc) => {
      switch (statusFilter) {
        case "attention":
          return isAttention(doc);
        case "processing":
          return doc.status === "processing";
        case "ready":
          return doc.status === "ready";
        case "failed":
          return doc.status === "failed";
        case "queued":
          return doc.status === "queued";
        default:
          return true;
      }
    });
  }, [baseFiltered, statusFilter]);

  const sortedDocuments = useMemo(() => {
    return [...filteredDocuments].sort((a, b) => b.updatedAt - a.updatedAt || a.name.localeCompare(b.name));
  }, [filteredDocuments]);

  useEffect(() => {
    if (sortedDocuments.length === 0) {
      if (activeId !== null) {
        setActiveId(null);
      }
      return;
    }
    if (!activeId || !sortedDocuments.some((doc) => doc.id === activeId)) {
      setActiveId(sortedDocuments[0].id);
    }
  }, [activeId, sortedDocuments]);

  const activeDocument = useMemo(() => documents.find((doc) => doc.id === activeId) ?? null, [documents, activeId]);

  useEffect(() => {
    if (activeDocument?.output?.sheets?.length) {
      setActiveSheetId(activeDocument.output.sheets[0].id);
      return;
    }
    setActiveSheetId(null);
  }, [activeDocument?.id, activeDocument?.output?.sheets?.length]);

  const boardColumns = useMemo<BoardColumn[]>(() => {
    if (groupBy === "status") {
      const statuses: DocumentStatus[] = ["queued", "processing", "ready", "failed"];
      return statuses.map((status) => ({
        id: status,
        label: STATUS_STYLES[status].label,
        context: { status },
        items: filteredDocuments.filter((doc) => doc.status === status),
      }));
    }

    if (groupBy === "tag") {
      if (tagOptions.length === 0) {
        return [
          {
            id: BOARD_UNTAGGED_ID,
            label: "Untagged",
            context: { tag: null },
            items: filteredDocuments.filter((doc) => doc.tags.length === 0),
          },
        ];
      }
      const columns = tagOptions.map((tag) => ({
        id: tag,
        label: tag,
        context: { tag },
        items: filteredDocuments.filter((doc) => doc.tags[0] === tag),
      }));
      columns.push({
        id: BOARD_UNTAGGED_ID,
        label: "Untagged",
        context: { tag: null },
        items: filteredDocuments.filter((doc) => doc.tags.length === 0),
      });
      return columns;
    }

    if (ownerOptions.length === 0) {
      return [
        {
          id: BOARD_UNASSIGNED_ID,
          label: "Unassigned",
          context: { owner: null },
          items: filteredDocuments.filter((doc) => !doc.owner),
        },
      ];
    }

    const columns = ownerOptions.map((owner) => ({
      id: owner,
      label: owner,
      context: { owner },
      items: filteredDocuments.filter((doc) => doc.owner === owner),
    }));
    columns.push({
      id: BOARD_UNASSIGNED_ID,
      label: "Unassigned",
      context: { owner: null },
      items: filteredDocuments.filter((doc) => !doc.owner),
    });
    return columns;
  }, [filteredDocuments, groupBy, ownerOptions, tagOptions]);

  const toggleTagFilter = useCallback((tag: string) => {
    setTagFilters((previous) => (previous.includes(tag) ? previous.filter((item) => item !== tag) : [...previous, tag]));
  }, []);

  const handleSelectAllVisible = useCallback(() => {
    setSelectedIds(new Set(sortedDocuments.map((doc) => doc.id)));
  }, [sortedDocuments]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleApplyView = useCallback(
    (viewId: string) => {
      const view = allViews.find((item) => item.id === viewId);
      if (!view) {
        return;
      }
      setActiveViewId(view.id);
      setSearch(view.filters.search);
      setStatusFilter(view.filters.status);
      setOwnerFilter(view.filters.owner);
      setTagFilters(view.filters.tags);
      setViewMode(view.view);
      setGroupBy(view.groupBy);
      setIsSavingView(false);
      setNewViewName("");
    },
    [allViews],
  );

  const handleSaveView = useCallback(() => {
    const trimmed = newViewName.trim();
    if (!trimmed) {
      return;
    }
    const nextView: SavedView = {
      id: `view-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: trimmed,
      filters: {
        search,
        status: statusFilter,
        owner: ownerFilter,
        tags: tagFilters,
      },
      view: viewMode,
      groupBy,
    };
    setSavedViews((previous) => [...previous, nextView]);
    setActiveViewId(nextView.id);
    setIsSavingView(false);
    setNewViewName("");
    notifyToast({
      title: "View saved",
      description: `"${trimmed}" is ready for reuse.`,
      intent: "success",
    });
  }, [groupBy, newViewName, notifyToast, ownerFilter, search, statusFilter, tagFilters, viewMode]);

  const handleClearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
    setOwnerFilter(OWNER_FILTER_ALL);
    setTagFilters([]);
    setActiveViewId("preset-all");
  }, []);

  const handleDownload = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc) {
        return;
      }
      if (doc.status !== "ready") {
        notifyToast({
          title: "Output not ready",
          description: "Processing needs to finish before downloading the normalized XLSX.",
          intent: "warning",
        });
        return;
      }
      const output = doc.output ?? buildOutputForDocument(doc);
      if (!doc.output) {
        setDocuments((previous) =>
          previous.map((item) => (item.id === doc.id ? { ...item, output } : item)),
        );
      }
      downloadDocument({ ...doc, output });
      notifyToast({
        title: "Download started",
        description: output.fileName,
        intent: "success",
      });
    },
    [notifyToast, setDocuments],
  );

  const handleRetry = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc || doc.status !== "failed") {
        return;
      }
      notifiedReadyRef.current.delete(doc.id);
      setDocuments((previous) =>
        previous.map((item) => (item.id === doc.id ? startProcessing(item, "Retry started") : item)),
      );
      notifyToast({
        title: "Retry started",
        description: `${doc.name} is processing again.`,
        intent: "info",
      });
    },
    [notifyToast, setDocuments],
  );

  const handleMoreActions = useCallback(() => {
    notifyToast({
      title: "More actions coming soon",
      description: "Bulk export, sharing, and automated delivery are on the way.",
      intent: "info",
    });
  }, [notifyToast]);

  const handleFixMapping = useCallback(() => {
    notifyToast({
      title: "Mapping editor coming soon",
      description: "We are polishing the mapping workflow for v7.",
      intent: "info",
    });
  }, [notifyToast]);

  const addDocuments = useCallback((nextDocs: DocumentEntry[]) => {
    if (nextDocs.length === 0) {
      return;
    }
    setDocuments((previous) => [...nextDocs, ...previous]);
    setActiveId((previous) => previous ?? nextDocs[0]?.id ?? null);
  }, []);

  const handleFiles = useCallback(
    (files: FileList | null, context: UploadContext = {}) => {
      if (!files || files.length === 0) {
        return;
      }
      const nowTimestamp = Date.now();
      const newDocs = Array.from(files).map((file, index) =>
        createDocumentFromFile(file, nowTimestamp + index * 1000, context),
      );
      addDocuments(newDocs);
      notifyToast({
        title: `${newDocs.length} file${newDocs.length === 1 ? "" : "s"} added`,
        description: "Processing will begin automatically.",
        intent: "success",
      });
    },
    [addDocuments, notifyToast],
  );

  const openUploadDialog = useCallback((context?: UploadContext) => {
    pendingUploadContextRef.current = context ?? null;
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const context = pendingUploadContextRef.current ?? {};
      pendingUploadContextRef.current = null;
      handleFiles(event.target.files, context);
      event.target.value = "";
    },
    [handleFiles],
  );

  const handleUploadClick = useCallback(() => {
    openUploadDialog();
  }, [openUploadDialog]);

  const handleBulkAssign = useCallback(() => {
    setDocuments((previous) =>
      previous.map((doc) => (selectedIds.has(doc.id) ? { ...doc, owner: currentUserLabel, updatedAt: Date.now() } : doc)),
    );
    if (selectedIds.size > 0) {
      notifyToast({
        title: "Owners updated",
        description: `${selectedIds.size} document${selectedIds.size === 1 ? "" : "s"} assigned to you.`,
        intent: "success",
      });
    }
  }, [currentUserLabel, notifyToast, selectedIds]);

  const handleBulkTag = useCallback(() => {
    setDocuments((previous) =>
      previous.map((doc) =>
        selectedIds.has(doc.id) ? { ...doc, tags: Array.from(new Set(["priority", ...doc.tags])), updatedAt: Date.now() } : doc,
      ),
    );
    if (selectedIds.size > 0) {
      notifyToast({
        title: "Tags updated",
        description: `${selectedIds.size} document${selectedIds.size === 1 ? "" : "s"} tagged priority.`,
        intent: "success",
      });
    }
  }, [notifyToast, selectedIds]);

  const handleBulkRetry = useCallback(() => {
    let retryCount = 0;
    selectedIds.forEach((id) => notifiedReadyRef.current.delete(id));
    setDocuments((previous) =>
      previous.map((doc) => {
        if (selectedIds.has(doc.id) && doc.status === "failed") {
          retryCount += 1;
          return startProcessing(doc, "Retry started");
        }
        return doc;
      }),
    );
    if (retryCount > 0) {
      notifyToast({
        title: "Retry started",
        description: `${retryCount} document${retryCount === 1 ? "" : "s"} reprocessing now.`,
        intent: "info",
      });
    }
  }, [notifyToast, selectedIds]);

  const handleBulkArchive = useCallback(() => {
    setDocuments((previous) => previous.filter((doc) => !selectedIds.has(doc.id)));
    setSelectedIds(new Set());
    if (selectedIds.size > 0) {
      notifyToast({
        title: "Archived",
        description: `${selectedIds.size} document${selectedIds.size === 1 ? "" : "s"} archived.`,
        intent: "info",
      });
    }
  }, [notifyToast, selectedIds]);

  const handleDropGrid = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsGridDragging(false);
      if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
        handleFiles(event.dataTransfer.files);
      }
    },
    [handleFiles],
  );

  const handleGridDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!event.dataTransfer.types.includes("Files")) {
      return;
    }
    event.preventDefault();
    setIsGridDragging(true);
  }, []);

  const handleGridDragLeave = useCallback(() => {
    setIsGridDragging(false);
  }, []);

  const handleDropColumn = useCallback(
    (column: BoardColumn, event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setActiveDropColumn(null);
      if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
        handleFiles(event.dataTransfer.files, column.context);
        return;
      }
      const docId = event.dataTransfer.getData("text/plain");
      if (!docId) {
        return;
      }
      setDocuments((previous) => previous.map((doc) => (doc.id === docId ? applyBoardContext(doc, column, groupBy) : doc)));
    },
    [groupBy, handleFiles],
  );

  const handleDocumentKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (sortedDocuments.length === 0) {
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
        return;
      }
      event.preventDefault();
      const currentIndex = sortedDocuments.findIndex((doc) => doc.id === activeId);
      if (currentIndex < 0) {
        setActiveId(sortedDocuments[0].id);
        return;
      }
      const nextIndex =
        event.key === "ArrowDown" ? Math.min(sortedDocuments.length - 1, currentIndex + 1) : Math.max(0, currentIndex - 1);
      setActiveId(sortedDocuments[nextIndex].id);
    },
    [activeId, sortedDocuments],
  );

  const activeOutput = activeDocument?.output;
  const activeSheet = activeOutput?.sheets.find((sheet) => sheet.id === activeSheetId) ?? activeOutput?.sheets[0];

  const selectedCount = selectedIds.size;
  const allVisibleSelected = sortedDocuments.length > 0 && sortedDocuments.every((doc) => selectedIds.has(doc.id));

  const showNoDocuments = documents.length === 0;
  const showNoResults = documents.length > 0 && sortedDocuments.length === 0;

  return (
    <div className="documents-v7 relative min-h-screen text-[color:var(--v7-ink)]" style={THEME_STYLE}>
      <div className="relative flex min-h-screen flex-col">
        <header className="docs-v7-animate sticky top-0 z-20 border-b border-[color:var(--v7-border)] bg-white/90 backdrop-blur">
          <div className="flex flex-wrap items-center gap-4 px-6 py-4 lg:px-10">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--v7-border)] bg-[color:var(--v7-accent-soft)] text-[color:var(--v7-accent-strong)] shadow-sm">
                <DocumentIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <h1 className="text-lg font-semibold text-[color:var(--v7-ink)]">Documents</h1>
                <p className="text-xs text-[color:var(--v7-muted)]">Daily workbench for processed XLSX</p>
              </div>
            </div>

            <div className="flex min-w-[240px] flex-1 items-center">
              <label className="sr-only" htmlFor="documents-v7-search">
                Search documents
              </label>
              <div className="relative w-full">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--v7-muted)]">
                  <SearchIcon className="h-4 w-4" />
                </span>
                <Input
                  id="documents-v7-search"
                  ref={searchRef}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search by name, owner, or tag"
                  className="pl-9"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center rounded-lg border border-[color:var(--v7-border)] bg-white p-1 text-xs shadow-sm">
                <Button
                  type="button"
                  size="sm"
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  onClick={() => setViewMode("grid")}
                  className={clsx(
                    "h-8 rounded-md px-3 text-xs",
                    viewMode === "grid" ? "shadow-sm" : "text-[color:var(--v7-muted)]",
                  )}
                  aria-pressed={viewMode === "grid"}
                  aria-label="Grid view"
                >
                  <GridIcon className="h-4 w-4" />
                  Grid
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={viewMode === "board" ? "secondary" : "ghost"}
                  onClick={() => setViewMode("board")}
                  className={clsx(
                    "h-8 rounded-md px-3 text-xs",
                    viewMode === "board" ? "shadow-sm" : "text-[color:var(--v7-muted)]",
                  )}
                  aria-pressed={viewMode === "board"}
                  aria-label="Board view"
                >
                  <BoardIcon className="h-4 w-4" />
                  Board
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <label className="sr-only" htmlFor="documents-v7-view-select">
                  Saved view
                </label>
                <Select
                  id="documents-v7-view-select"
                  value={activeViewId}
                  onChange={(event) => handleApplyView(event.target.value)}
                  className="min-w-[11rem] text-xs"
                >
                  {allViews.map((view) => (
                    <option key={view.id} value={view.id}>
                      {view.name}
                    </option>
                  ))}
                </Select>

                {isSavingView ? (
                  <div className="flex items-center gap-2">
                    <Input
                      value={newViewName}
                      onChange={(event) => setNewViewName(event.target.value)}
                      placeholder="Name this view"
                      className="w-40 text-xs"
                    />
                    <Button
                      type="button"
                      onClick={handleSaveView}
                      size="sm"
                      className="text-xs"
                    >
                      Save
                    </Button>
                    <Button
                      type="button"
                      onClick={() => {
                        setIsSavingView(false);
                        setNewViewName("");
                      }}
                      size="sm"
                      variant="ghost"
                      className="text-xs"
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button
                    type="button"
                    onClick={() => setIsSavingView(true)}
                    size="sm"
                    variant="secondary"
                    className="text-xs"
                  >
                    Save view
                  </Button>
                )}
              </div>

              <Button type="button" onClick={handleUploadClick} size="md" className="gap-2">
                <UploadIcon className="h-4 w-4" />
                Upload
              </Button>
              <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileInputChange} />
            </div>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-0 lg:flex-row">
          <section className="docs-v7-animate relative flex min-h-0 flex-1 flex-col border-r border-[color:var(--v7-border)] bg-[color:var(--v7-panel)]">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--v7-border)] px-6 py-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--v7-muted)]">Work queue</p>
                <p className="text-sm font-semibold text-[color:var(--v7-ink)]">
                  {sortedDocuments.length} documents in view
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {STATUS_FILTERS.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    onClick={() => setStatusFilter(filter.id)}
                    className={clsx(
                      "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                      statusFilter === filter.id
                        ? "border-[color:var(--v7-accent)] bg-[color:var(--v7-accent-soft)] text-[color:var(--v7-accent-strong)]"
                        : "border-transparent bg-white text-[color:var(--v7-muted)] hover:text-[color:var(--v7-ink)]",
                    )}
                    aria-pressed={statusFilter === filter.id}
                  >
                    {filter.label}
                    <span className="text-[11px] text-[color:var(--v7-muted)]">
                      {numberFormatter.format(statusCounts[filter.id])}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4 border-b border-[color:var(--v7-border)] px-6 py-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[color:var(--v7-muted)]">Owner</span>
                <Select
                  value={ownerFilter}
                  onChange={(event) => setOwnerFilter(event.target.value)}
                  className="w-40 text-xs"
                >
                  <option value={OWNER_FILTER_ALL}>All owners</option>
                  {ownerOptions.map((owner) => (
                    <option key={owner} value={owner}>
                      {owner}
                    </option>
                  ))}
                  <option value={OWNER_FILTER_UNASSIGNED}>Unassigned</option>
                </Select>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-[color:var(--v7-muted)]">Tags</span>
                {tagOptions.length === 0 ? (
                  <span className="text-xs text-[color:var(--v7-muted)]">No tags yet</span>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    {tagOptions.map((tag) => {
                      const isSelected = tagFilters.includes(tag);
                      return (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => toggleTagFilter(tag)}
                          className={clsx(
                            "rounded-full border px-3 py-1 text-xs font-semibold transition",
                            isSelected
                              ? "border-[color:var(--v7-accent)] bg-[color:var(--v7-accent-soft)] text-[color:var(--v7-accent-strong)]"
                              : "border-transparent bg-white text-[color:var(--v7-muted)] hover:text-[color:var(--v7-ink)]",
                          )}
                          aria-pressed={isSelected}
                        >
                          {tag}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {(search || statusFilter !== "all" || ownerFilter !== OWNER_FILTER_ALL || tagFilters.length > 0) && (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="text-xs font-semibold text-[color:var(--v7-accent-strong)]"
                >
                  Clear filters
                </button>
              )}
            </div>

            {selectedCount > 0 ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--v7-border)] bg-white/70 px-6 py-3 text-xs">
                <div className="flex items-center gap-2 font-semibold text-[color:var(--v7-ink)]">
                  <span>{selectedCount} selected</span>
                  <button type="button" onClick={handleClearSelection} className="text-[color:var(--v7-muted)]">
                    Clear
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" onClick={handleBulkAssign} size="sm" variant="secondary" className="rounded-full text-xs">
                    Assign to me
                  </Button>
                  <Button type="button" onClick={handleBulkTag} size="sm" variant="secondary" className="rounded-full text-xs">
                    Tag priority
                  </Button>
                  <Button type="button" onClick={handleBulkRetry} size="sm" variant="secondary" className="rounded-full text-xs">
                    Retry
                  </Button>
                  <Button type="button" onClick={handleBulkArchive} size="sm" variant="secondary" className="rounded-full text-xs">
                    Archive
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="relative flex min-h-0 flex-1 flex-col">
              {viewMode === "grid" ? (
                <div
                  className="relative flex min-h-0 flex-1 flex-col"
                  onDrop={handleDropGrid}
                  onDragOver={handleGridDragOver}
                  onDragLeave={handleGridDragLeave}
                  aria-label="Document list drop zone"
                >
                  {isGridDragging ? (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 backdrop-blur-sm">
                      <div className="rounded-2xl border border-dashed border-[color:var(--v7-accent)] bg-white px-6 py-4 text-sm font-semibold text-[color:var(--v7-accent-strong)] shadow-sm">
                        Drop files to upload into this workspace
                      </div>
                    </div>
                  ) : null}

                  <div className="hidden border-b border-[color:var(--v7-border)] px-6 py-2 text-xs uppercase tracking-[0.18em] text-[color:var(--v7-muted)] md:grid md:grid-cols-[auto_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,0.6fr)]">
                    <div>
                      <input
                        type="checkbox"
                        checked={allVisibleSelected}
                        onChange={(event) => (event.target.checked ? handleSelectAllVisible() : handleClearSelection())}
                        aria-label="Select all visible documents"
                      />
                    </div>
                    <div>Document</div>
                    <div>Status</div>
                    <div>Owner</div>
                    <div>Tags</div>
                    <div className="text-right">Updated</div>
                  </div>

                  <div className="flex-1 overflow-y-auto px-6 py-2" onKeyDown={handleDocumentKeyDown} tabIndex={0} role="list" aria-label="Document list">
                    {showNoDocuments ? (
                      <EmptyState
                        title="No documents yet"
                        description="Upload your first batch to start the processing loop."
                        action={{ label: "Upload files", onClick: handleUploadClick }}
                      />
                    ) : showNoResults ? (
                      <EmptyState
                        title="No results in this view"
                        description="Try clearing filters or adjusting the search."
                        action={{ label: "Clear filters", onClick: handleClearFilters }}
                      />
                    ) : (
                      <div className="flex flex-col gap-2">
                        {sortedDocuments.map((doc) => (
                          <div
                            key={doc.id}
                            role="listitem"
                            tabIndex={0}
                            onClick={() => setActiveId(doc.id)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setActiveId(doc.id);
                              }
                            }}
                            className={clsx(
                              "group flex flex-col gap-3 rounded-2xl border px-4 py-3 shadow-sm transition md:grid md:grid-cols-[auto_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,0.6fr)] md:items-center",
                              activeId === doc.id
                                ? "border-[color:var(--v7-accent)] bg-white"
                                : "border-[color:var(--v7-border)] bg-white/80 hover:border-[color:var(--v7-accent)]",
                            )}
                          >
                            <div className="flex items-center">
                              <input
                                type="checkbox"
                                checked={selectedIds.has(doc.id)}
                                onChange={() => handleToggleSelect(doc.id)}
                                onClick={(event) => event.stopPropagation()}
                                aria-label={`Select ${doc.name}`}
                              />
                            </div>

                            <div className="flex items-center gap-3">
                              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[color:var(--v7-border)] bg-[color:var(--v7-panel)]">
                                <DocumentIcon className="h-4 w-4 text-[color:var(--v7-muted)]" />
                              </div>
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-[color:var(--v7-ink)]">{doc.name}</p>
                                <p className="text-xs text-[color:var(--v7-muted)]">Uploaded {formatRelativeTime(now, doc.createdAt)}</p>
                              </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <StatusPill status={doc.status} />
                              {doc.status === "processing" ? (
                                <span className="text-[11px] text-[color:var(--v7-muted)]">
                                  {doc.progress ?? 0}% - {doc.stage ?? "Processing"}
                                </span>
                              ) : null}
                              <MappingBadge mapping={doc.mapping} />
                            </div>

                            <div className="text-xs font-semibold text-[color:var(--v7-muted)]">{doc.owner ?? "Unassigned"}</div>

                            <div className="flex flex-wrap items-center gap-1 text-xs text-[color:var(--v7-muted)]">
                              {doc.tags.length === 0 ? (
                                <span className="text-[11px]">No tags</span>
                              ) : (
                                <>
                                  {doc.tags.slice(0, 2).map((tag) => (
                                    <span key={tag} className="rounded-full border border-[color:var(--v7-border)] bg-[color:var(--v7-panel)] px-2 py-0.5 text-[11px] font-semibold">
                                      {tag}
                                    </span>
                                  ))}
                                  {doc.tags.length > 2 ? (
                                    <span className="text-[11px] text-[color:var(--v7-muted)]">+{doc.tags.length - 2}</span>
                                  ) : null}
                                </>
                              )}
                            </div>

                            <div className="flex items-center justify-between text-xs text-[color:var(--v7-muted)] md:justify-end">
                              <span>{formatRelativeTime(now, doc.updatedAt)}</span>
                              <div className="flex items-center gap-2 opacity-0 transition group-hover:opacity-100">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-7 rounded-full p-0"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleDownload(doc);
                                  }}
                                  aria-label={`Download ${doc.name}`}
                                  disabled={doc.status !== "ready"}
                                >
                                  <DownloadIcon className="h-3 w-3" />
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-7 rounded-full p-0"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleRetry(doc);
                                  }}
                                  aria-label={`Retry ${doc.name}`}
                                  disabled={doc.status !== "failed"}
                                >
                                  <RetryIcon className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--v7-border)] px-6 py-3 text-xs">
                    <div className="flex items-center gap-2 font-semibold text-[color:var(--v7-muted)]">
                      <span>Group by</span>
                      <div className="flex items-center rounded-full border border-[color:var(--v7-border)] bg-white px-1 py-1">
                        {BOARD_GROUPS.map((group) => (
                          <button
                            key={group.id}
                            type="button"
                            onClick={() => setGroupBy(group.id)}
                            className={clsx(
                              "rounded-full px-3 py-1 text-xs font-semibold transition",
                              groupBy === group.id
                                ? "bg-[color:var(--v7-accent-soft)] text-[color:var(--v7-accent-strong)]"
                                : "text-[color:var(--v7-muted)] hover:text-[color:var(--v7-ink)]",
                            )}
                            aria-pressed={groupBy === group.id}
                          >
                            {group.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <span className="text-[color:var(--v7-muted)]">Drag cards between columns or drop files into a column</span>
                  </div>

                  <div className="flex-1 overflow-x-auto px-6 py-4">
                    <div className="flex min-h-full gap-4">
                      {boardColumns.map((column) => (
                        <div key={column.id} className="flex w-72 min-w-[18rem] flex-col">
                          <div className="mb-3 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {groupBy === "status" ? (
                                <span className={clsx("h-2.5 w-2.5 rounded-full", STATUS_STYLES[column.id as DocumentStatus].dot)} aria-hidden />
                              ) : groupBy === "owner" ? (
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[color:var(--v7-accent-soft)] text-[10px] font-semibold text-[color:var(--v7-accent-strong)]">
                                  {column.label === "Unassigned" ? "?" : getInitials(column.label)}
                                </span>
                              ) : (
                                <TagIcon className="h-4 w-4 text-[color:var(--v7-muted)]" />
                              )}
                              <div>
                                <p className="text-sm font-semibold text-[color:var(--v7-ink)]">{column.label}</p>
                                <p className="text-xs text-[color:var(--v7-muted)]">{column.items.length} items</p>
                              </div>
                            </div>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-7 rounded-full px-2 text-[11px]"
                              aria-label={`Upload directly to ${column.label}`}
                              onClick={() => openUploadDialog(column.context)}
                            >
                              + Upload
                            </Button>
                          </div>

                          <div
                            className={clsx(
                              "flex min-h-[12rem] flex-1 flex-col gap-3 rounded-2xl border border-dashed px-3 py-3 transition",
                              activeDropColumn === column.id
                                ? "border-[color:var(--v7-accent)] bg-[color:var(--v7-accent-soft)]/40"
                                : "border-[color:var(--v7-border)] bg-white/80",
                            )}
                            onDragOver={(event) => {
                              event.preventDefault();
                              setActiveDropColumn(column.id);
                            }}
                            onDragLeave={() => setActiveDropColumn(null)}
                            onDrop={(event) => handleDropColumn(column, event)}
                            aria-label={`Board column ${column.label}`}
                          >
                            {column.items.length === 0 ? (
                              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-xs text-[color:var(--v7-muted)]">
                                <p>No items yet</p>
                                <p>Drop files here to auto-assign</p>
                              </div>
                            ) : (
                              column.items.map((doc) => (
                                <div
                                  key={doc.id}
                                  draggable
                                  onDragStart={(event) => {
                                    event.dataTransfer.setData("text/plain", doc.id);
                                    event.dataTransfer.effectAllowed = "move";
                                  }}
                                  onClick={() => setActiveId(doc.id)}
                                  className={clsx(
                                    "flex flex-col gap-3 rounded-2xl border bg-white px-3 py-3 shadow-sm transition",
                                    activeId === doc.id ? "border-[color:var(--v7-accent)]" : "border-[color:var(--v7-border)] hover:border-[color:var(--v7-accent)]",
                                  )}
                                  role="button"
                                  aria-label={`Open ${doc.name}`}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div>
                                      <p className="text-sm font-semibold text-[color:var(--v7-ink)]">{doc.name}</p>
                                      <p className="text-xs text-[color:var(--v7-muted)]">Updated {formatRelativeTime(now, doc.updatedAt)}</p>
                                    </div>
                                    <span className={clsx("h-2.5 w-2.5 rounded-full", STATUS_STYLES[doc.status].dot)} aria-hidden />
                                  </div>
                                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-[color:var(--v7-muted)]">
                                    <span className="font-semibold">{doc.owner ?? "Unassigned"}</span>
                                    {doc.tags.length > 0 ? (
                                      <span className="rounded-full border border-[color:var(--v7-border)] bg-[color:var(--v7-panel)] px-2 py-0.5">
                                        {doc.tags[0]}
                                        {doc.tags.length > 1 ? ` +${doc.tags.length - 1}` : ""}
                                      </span>
                                    ) : null}
                                    {isAttention(doc) ? (
                                      <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-700">
                                        Needs mapping
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          <aside className="docs-v7-animate flex min-h-0 w-full flex-col bg-white lg:w-[38%]">
            <div className="flex items-start justify-between gap-4 border-b border-[color:var(--v7-border)] px-6 py-5">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--v7-muted)]">Preview</p>
                <h2 className="truncate text-lg font-semibold text-[color:var(--v7-ink)]">
                  {activeDocument ? activeDocument.name : "Select a document"}
                </h2>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[color:var(--v7-muted)]">
                  {activeDocument ? (
                    <>
                      <StatusPill status={activeDocument.status} />
                      <span>{getStatusDescription(activeDocument)}</span>
                    </>
                  ) : (
                    <span>Choose a file to inspect the processed output.</span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  className="gap-2 text-xs"
                  onClick={() => handleDownload(activeDocument)}
                  disabled={!activeDocument || activeDocument.status !== "ready"}
                  aria-label="Download processed XLSX"
                >
                  <DownloadIcon className="h-4 w-4" />
                  Download processed XLSX
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="text-xs"
                  onClick={() => handleRetry(activeDocument)}
                  disabled={!activeDocument || activeDocument.status !== "failed"}
                >
                  Retry
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-xs"
                  aria-label="More actions"
                  onClick={handleMoreActions}
                >
                  More
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5">
              {!activeDocument ? (
                <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--v7-border)] bg-[color:var(--v7-panel)] px-6 text-center text-sm text-[color:var(--v7-muted)]">
                  <p className="text-sm font-semibold text-[color:var(--v7-ink)]">Preview is ready when you are.</p>
                  <p>Select a document from the left to inspect its processed output.</p>
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  <section className="rounded-2xl border border-[color:var(--v7-border)] bg-white px-4 py-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs uppercase tracking-[0.2em] text-[color:var(--v7-muted)]">Summary</h3>
                      <span className="text-xs text-[color:var(--v7-muted)]">Updated {formatRelativeTime(now, activeDocument.updatedAt)}</span>
                    </div>
                    <dl className="mt-4 grid gap-3 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-[color:var(--v7-muted)]">Owner</dt>
                        <dd className="font-semibold text-[color:var(--v7-ink)]">{activeDocument.owner ?? "Unassigned"}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-[color:var(--v7-muted)]">Tags</dt>
                        <dd className="flex flex-wrap items-center justify-end gap-2 text-xs">
                          {activeDocument.tags.length === 0 ? (
                            <span className="text-[color:var(--v7-muted)]">No tags</span>
                          ) : (
                            activeDocument.tags.map((tag) => (
                              <span key={tag} className="rounded-full border border-[color:var(--v7-border)] bg-[color:var(--v7-panel)] px-2 py-0.5 font-semibold">
                                {tag}
                              </span>
                            ))
                          )}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-[color:var(--v7-muted)]">Mapping health</dt>
                        <dd className="text-right text-xs font-semibold text-[color:var(--v7-ink)]">{getMappingHealthLabel(activeDocument.mapping)}</dd>
                      </div>
                      {activeDocument.status === "processing" ? (
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-[color:var(--v7-muted)]">Progress</dt>
                          <dd className="text-xs font-semibold text-[color:var(--v7-ink)]">
                            {activeDocument.progress ?? 0}% - {activeDocument.stage ?? "Processing"}
                          </dd>
                        </div>
                      ) : null}
                    </dl>
                  </section>

                  <section className="rounded-2xl border border-[color:var(--v7-border)] bg-white px-4 py-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs uppercase tracking-[0.2em] text-[color:var(--v7-muted)]">Processed output</h3>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 rounded-full px-3 text-[11px]"
                        disabled
                        onClick={handleFixMapping}
                        aria-label="Fix mapping (coming soon)"
                        title="Coming soon"
                      >
                        Fix mapping
                      </Button>
                    </div>

                    {activeDocument.status === "ready" && activeDocument.output ? (
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[color:var(--v7-muted)]">
                        <span className="font-semibold text-[color:var(--v7-ink)]">{activeDocument.output.fileName}</span>
                        <span>
                          {activeDocument.output.size} - {numberFormatter.format(activeDocument.output.rows)} rows -{" "}
                          {numberFormatter.format(activeDocument.output.columns)} cols
                        </span>
                      </div>
                    ) : null}

                    <div className="mt-4 rounded-2xl border border-[color:var(--v7-border)] bg-[color:var(--v7-panel)]">
                      {activeDocument.status === "ready" ? (
                        activeDocument.output ? (
                          activeDocument.output.previewAvailable === false ? (
                            <div className="flex flex-col gap-2 px-4 py-6 text-sm text-[color:var(--v7-muted)]">
                              <p className="font-semibold text-[color:var(--v7-ink)]">Preview unavailable for this output</p>
                              <p>The processed XLSX is ready to download, but the preview is too large to render here.</p>
                            </div>
                          ) : (
                            <div>
                              <div className="flex flex-wrap items-center gap-2 border-b border-[color:var(--v7-border)] px-3 py-2 text-xs">
                                {activeDocument.output.sheets.map((sheet) => (
                                  <button
                                    key={sheet.id}
                                    type="button"
                                    onClick={() => setActiveSheetId(sheet.id)}
                                    className={clsx(
                                      "rounded-full px-3 py-1 font-semibold transition",
                                      activeSheetId === sheet.id
                                        ? "bg-[color:var(--v7-accent-soft)] text-[color:var(--v7-accent-strong)]"
                                        : "text-[color:var(--v7-muted)] hover:text-[color:var(--v7-ink)]",
                                    )}
                                  >
                                    {sheet.name}
                                  </button>
                                ))}
                              </div>
                              {activeSheet ? (
                                <div className="max-h-72 overflow-auto">
                                  <PreviewTable sheet={activeSheet} />
                                </div>
                              ) : (
                                <div className="px-4 py-6 text-sm text-[color:var(--v7-muted)]">Select a sheet to preview.</div>
                              )}
                              <div className="border-t border-[color:var(--v7-border)] px-4 py-2 text-[11px] text-[color:var(--v7-muted)]">
                                Showing {Math.min(PREVIEW_ROW_LIMIT, activeSheet?.rows.length ?? 0)} of{" "}
                                {numberFormatter.format(activeDocument.output.rows)} rows
                              </div>
                            </div>
                          )
                        ) : (
                          <div className="px-4 py-6 text-sm text-[color:var(--v7-muted)]">Output not generated yet. Try reprocessing to generate the XLSX.</div>
                        )
                      ) : activeDocument.status === "failed" ? (
                        <div className="flex flex-col gap-3 px-4 py-6 text-sm text-[color:var(--v7-muted)]">
                          <p className="font-semibold text-[color:var(--v7-danger)]">{activeDocument.error?.summary ?? "Processing failed"}</p>
                          <p>{activeDocument.error?.detail ?? "We could not complete normalization for this file."}</p>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="danger"
                              className="text-xs"
                              onClick={() => handleRetry(activeDocument)}
                            >
                              Retry now
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              className="text-xs"
                              disabled
                              onClick={handleFixMapping}
                            >
                              Fix mapping (soon)
                            </Button>
                          </div>
                          <p className="text-xs text-[color:var(--v7-muted)]">{activeDocument.error?.nextStep ?? "Retry now or fix mapping later."}</p>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-3 px-4 py-6 text-sm text-[color:var(--v7-muted)]">
                          <p className="font-semibold text-[color:var(--v7-ink)]">
                            {activeDocument.status === "processing" ? "Processing output" : "Queued for processing"}
                          </p>
                          <p>
                            {activeDocument.stage ?? "Preparing normalized output"} -{" "}
                            {activeDocument.etaMinutes ? `${activeDocument.etaMinutes} min ETA` : "Updating soon"}
                          </p>
                          <div className="h-2 overflow-hidden rounded-full bg-white">
                            <div className="docs-v7-shimmer h-full bg-[linear-gradient(90deg,var(--v7-accent-soft),var(--v7-accent),var(--v7-accent-soft))]" style={{ width: `${activeDocument.progress ?? 12}%` }} />
                          </div>
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="rounded-2xl border border-[color:var(--v7-border)] bg-white px-4 py-4 shadow-sm">
                    <h3 className="text-xs uppercase tracking-[0.2em] text-[color:var(--v7-muted)]">History</h3>
                    <div className="mt-4 flex flex-col gap-3 text-xs text-[color:var(--v7-muted)]">
                      {activeDocument.history.map((event) => (
                        <div key={event.id} className="flex items-start gap-3">
                          <span
                            className={clsx(
                              "mt-1.5 h-2 w-2 rounded-full",
                              event.tone === "success"
                                ? "bg-emerald-500"
                                : event.tone === "warning"
                                  ? "bg-amber-500"
                                  : event.tone === "danger"
                                    ? "bg-rose-500"
                                    : "bg-slate-400",
                            )}
                          />
                          <div className="flex flex-1 items-center justify-between gap-3">
                            <span className="font-semibold text-[color:var(--v7-ink)]">{event.label}</span>
                            <span>{formatTime(event.at)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[color:var(--v7-border)] bg-white/70 px-8 py-12 text-center">
      <p className="text-sm font-semibold text-[color:var(--v7-ink)]">{title}</p>
      <p className="text-sm text-[color:var(--v7-muted)]">{description}</p>
      {action ? (
        <Button type="button" onClick={action.onClick} size="sm" className="text-xs">
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: DocumentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}

function MappingBadge({ mapping }: { mapping: MappingHealth }) {
  if (mapping.attention === 0 && mapping.unmapped === 0) {
    return null;
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
      <AlertIcon className="h-3 w-3" />
      {mapping.attention > 0 ? `${mapping.attention} columns need attention` : `${mapping.unmapped} unmapped columns`}
    </span>
  );
}

function PreviewTable({ sheet }: { sheet: DocumentSheet }) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 bg-[color:var(--v7-panel)] text-[color:var(--v7-muted)]">
        <tr>
          {sheet.columns.map((column) => (
            <th key={column} className="px-3 py-2 font-semibold uppercase tracking-wide">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.slice(0, PREVIEW_ROW_LIMIT).map((row, rowIndex) => (
          <tr key={`${sheet.id}-${rowIndex}`} className="border-t border-[color:var(--v7-border)]">
            {row.map((cell, cellIndex) => (
              <td key={`${sheet.id}-${rowIndex}-${cellIndex}`} className="px-3 py-2 text-[color:var(--v7-ink)]">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function createSeedDocuments(currentUserLabel: string): DocumentEntry[] {
  const now = Date.now();
  const minutes = (value: number) => now - value * 60000;
  const hours = (value: number) => now - value * 3600000;

  return [
    {
      id: "doc-101",
      name: "Northwind_AP_2024-09.xlsx",
      status: "ready",
      owner: "Ava Brooks",
      tags: ["invoices", "north"],
      createdAt: minutes(46),
      updatedAt: minutes(2),
      size: "1.4 MB",
      mapping: { attention: 0, unmapped: 0 },
      output: OUTPUT_AP,
      history: [
        { id: "doc-101-1", label: "Uploaded by Ava Brooks", at: minutes(46) },
        { id: "doc-101-2", label: "Processing started", at: minutes(35), tone: "info" },
        { id: "doc-101-3", label: "Output ready", at: minutes(2), tone: "success" },
      ],
    },
    {
      id: "doc-102",
      name: "Retail_Wk36_Sales.csv",
      status: "processing",
      owner: "Ravi Patel",
      tags: ["retail", "weekly"],
      createdAt: minutes(80),
      updatedAt: minutes(4),
      size: "780 KB",
      progress: 68,
      stage: "Normalizing 14 columns",
      etaMinutes: 3,
      mapping: { attention: 0, unmapped: 0 },
      history: [
        { id: "doc-102-1", label: "Uploaded by Ravi Patel", at: minutes(80) },
        { id: "doc-102-2", label: "Queued", at: minutes(62) },
        { id: "doc-102-3", label: "Processing", at: minutes(12), tone: "info" },
      ],
    },
    {
      id: "doc-103",
      name: "Claims_0911_Batch.xlsx",
      status: "failed",
      owner: "Noah Kim",
      tags: ["claims", "urgent"],
      createdAt: minutes(110),
      updatedAt: minutes(12),
      size: "2.3 MB",
      mapping: { attention: 3, unmapped: 1 },
      error: {
        summary: "Missing policy_id in row 18",
        detail: "Validation rule failed: policy_id must be present for every record.",
        nextStep: "Retry now or fix mapping rules when ready.",
      },
      history: [
        { id: "doc-103-1", label: "Uploaded by Noah Kim", at: minutes(110) },
        { id: "doc-103-2", label: "Processing started", at: minutes(92) },
        { id: "doc-103-3", label: "Validation failed", at: minutes(12), tone: "danger" },
      ],
    },
    {
      id: "doc-104",
      name: "Payroll_0315.csv",
      status: "queued",
      owner: null,
      tags: ["payroll"],
      createdAt: minutes(9),
      updatedAt: minutes(9),
      size: "640 KB",
      stage: "Waiting for processing",
      etaMinutes: 8,
      mapping: { attention: 0, unmapped: 0 },
      history: [
        { id: "doc-104-1", label: "Uploaded just now", at: minutes(9) },
        { id: "doc-104-2", label: "Queued", at: minutes(8) },
      ],
    },
    {
      id: "doc-105",
      name: "Hospital_Admissions_Q3.xlsx",
      status: "ready",
      owner: "Jess Stone",
      tags: ["health", "quarterly"],
      createdAt: hours(6),
      updatedAt: minutes(31),
      size: "4.6 MB",
      mapping: { attention: 0, unmapped: 2 },
      output: {
        ...OUTPUT_SALES,
        fileName: "Hospital_Admissions_Q3_normalized.xlsx",
        previewAvailable: false,
      },
      history: [
        { id: "doc-105-1", label: "Uploaded by Jess Stone", at: hours(6) },
        { id: "doc-105-2", label: "Processing completed", at: minutes(31), tone: "success" },
      ],
    },
    {
      id: "doc-106",
      name: "Logistics_SLA_Tracker.xlsx",
      status: "processing",
      owner: "Ava Brooks",
      tags: ["logistics", "sla"],
      createdAt: minutes(52),
      updatedAt: minutes(7),
      size: "1.1 MB",
      progress: 42,
      stage: "Reconciling service levels",
      etaMinutes: 6,
      mapping: { attention: 0, unmapped: 0 },
      history: [
        { id: "doc-106-1", label: "Uploaded by Ava Brooks", at: minutes(52) },
        { id: "doc-106-2", label: "Processing started", at: minutes(16) },
      ],
    },
    {
      id: "doc-107",
      name: "Marketing_Leads_Sept.csv",
      status: "ready",
      owner: "Ravi Patel",
      tags: ["marketing", "leads"],
      createdAt: hours(3),
      updatedAt: minutes(18),
      size: "510 KB",
      mapping: { attention: 1, unmapped: 2 },
      output: OUTPUT_MARKETING,
      history: [
        { id: "doc-107-1", label: "Uploaded by Ravi Patel", at: hours(3) },
        { id: "doc-107-2", label: "Output ready", at: minutes(18), tone: "success" },
      ],
    },
    {
      id: "doc-108",
      name: "Supplier_Prices_RevB.xlsx",
      status: "failed",
      owner: "Jess Stone",
      tags: ["pricing", "suppliers"],
      createdAt: hours(4),
      updatedAt: minutes(26),
      size: "1.9 MB",
      mapping: { attention: 2, unmapped: 4 },
      error: {
        summary: "Unmapped columns detected",
        detail: "Four supplier fields are missing mapping rules for the RevB template.",
        nextStep: "Fix mapping when the editor is available, then retry.",
      },
      history: [
        { id: "doc-108-1", label: "Uploaded by Jess Stone", at: hours(4) },
        { id: "doc-108-2", label: "Processing failed", at: minutes(26), tone: "danger" },
      ],
    },
    {
      id: "doc-109",
      name: "Fleet_Maintenance_Log.csv",
      status: "queued",
      owner: null,
      tags: ["fleet"],
      createdAt: minutes(22),
      updatedAt: minutes(22),
      size: "420 KB",
      stage: "Queued for processing",
      mapping: { attention: 0, unmapped: 0 },
      history: [{ id: "doc-109-1", label: "Uploaded from drop zone", at: minutes(22) }],
    },
    {
      id: "doc-110",
      name: "Customer_Refunds_Aug.xlsx",
      status: "ready",
      owner: currentUserLabel,
      tags: ["refunds", "finance"],
      createdAt: hours(2),
      updatedAt: minutes(6),
      size: "980 KB",
      mapping: { attention: 0, unmapped: 0 },
      output: OUTPUT_REFUNDS,
      history: [
        { id: "doc-110-1", label: "Uploaded by you", at: hours(2) },
        { id: "doc-110-2", label: "Output ready", at: minutes(6), tone: "success" },
      ],
    },
  ];
}

function createDocumentFromFile(file: File, nowTimestamp: number, context: UploadContext): DocumentEntry {
  const id = `doc-${nowTimestamp}-${Math.random().toString(16).slice(2)}`;
  const status = context.status ?? "queued";
  const output =
    status === "ready"
      ? {
          ...OUTPUT_LIBRARY[hashString(id) % OUTPUT_LIBRARY.length],
          fileName: buildOutputFileName(file.name),
        }
      : undefined;
  const progress = status === "ready" ? 100 : status === "processing" ? 12 : undefined;
  const stage =
    status === "ready"
      ? "Output ready"
      : status === "processing"
        ? "Parsing input"
        : "Queued for processing";

  return {
    id,
    name: file.name,
    status,
    owner: context.owner ?? null,
    tags: context.tag ? [context.tag] : [],
    createdAt: nowTimestamp,
    updatedAt: nowTimestamp,
    size: formatBytes(file.size),
    mapping: { attention: 0, unmapped: 0 },
    output,
    progress,
    stage,
    etaMinutes: status === "processing" ? 6 : undefined,
    history: [{ id: `doc-${nowTimestamp}-1`, label: "Uploaded just now", at: nowTimestamp }],
  };
}

function startProcessing(doc: DocumentEntry, label: string, nowTimestamp = Date.now()): DocumentEntry {
  return {
    ...doc,
    status: "processing",
    progress: doc.progress ?? 8,
    stage: "Normalizing columns",
    etaMinutes: 6,
    updatedAt: nowTimestamp,
    error: undefined,
    history: appendHistory(doc.history, createHistoryEntry(doc.id, label, nowTimestamp, "info")),
  };
}

function advanceDocument(doc: DocumentEntry, nowTimestamp: number): DocumentEntry {
  if (doc.status === "queued") {
    if (nowTimestamp - doc.updatedAt < 60000) {
      return doc;
    }
    return startProcessing(doc, "Processing started", nowTimestamp);
  }

  if (doc.status === "processing") {
    const current = doc.progress ?? 5;
    const nextProgress = Math.min(100, current + randomInt(6, 16));
    if (nextProgress >= 100) {
      return {
        ...doc,
        status: "ready",
        progress: 100,
        stage: "Output ready",
        etaMinutes: undefined,
        updatedAt: nowTimestamp,
        output: doc.output ?? buildOutputForDocument(doc),
        history: appendHistory(doc.history, createHistoryEntry(doc.id, "Output ready", nowTimestamp, "success")),
      };
    }
    return {
      ...doc,
      progress: nextProgress,
      stage: getProcessingStage(nextProgress),
      etaMinutes: Math.max(1, Math.ceil((100 - nextProgress) / 18)),
      updatedAt: nowTimestamp,
    };
  }

  return doc;
}

function buildOutputForDocument(doc: DocumentEntry): DocumentOutput {
  const base = OUTPUT_LIBRARY[hashString(doc.id) % OUTPUT_LIBRARY.length];
  return {
    ...base,
    fileName: buildOutputFileName(doc.name),
  };
}

function buildOutputFileName(name: string) {
  const base = name.replace(/\.[^.]+$/, "");
  return `${base}_normalized.xlsx`;
}

function downloadDocument(doc: DocumentEntry) {
  if (!doc.output) {
    return;
  }
  const sheet = doc.output.sheets[0];
  const csv = buildCsv(sheet);
  const blob = new Blob([csv], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const fileName = doc.output.fileName || buildOutputFileName(doc.name);
  triggerDownload(blob, fileName);
}

function buildCsv(sheet: DocumentSheet) {
  const rows = [sheet.columns, ...sheet.rows];
  return rows.map((row) => row.map((cell) => escapeCsv(String(cell))).join(",")).join("\n");
}

function escapeCsv(value: string) {
  if (value.includes(",") || value.includes("\"") || value.includes("\n")) {
    return `"${value.replace(/\"/g, "\"\"")}"`;
  }
  return value;
}

function triggerDownload(blob: Blob, fileName: string) {
  if (typeof window === "undefined") {
    return;
  }
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
}

function createHistoryEntry(
  docId: string,
  label: string,
  nowTimestamp: number,
  tone?: DocumentHistoryItem["tone"],
): DocumentHistoryItem {
  return { id: `${docId}-${nowTimestamp}`, label, at: nowTimestamp, tone };
}

function appendHistory(history: DocumentHistoryItem[], entry: DocumentHistoryItem) {
  const next = [...history, entry];
  return next.length > 6 ? next.slice(next.length - 6) : next;
}

function getProcessingStage(progress: number) {
  if (progress < 25) {
    return "Parsing input";
  }
  if (progress < 55) {
    return "Normalizing columns";
  }
  if (progress < 80) {
    return "Validating output";
  }
  return "Finalizing output";
}

function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function hashString(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function applyBoardContext(doc: DocumentEntry, column: BoardColumn, groupBy: BoardGroup): DocumentEntry {
  const updatedAt = Date.now();
  if (groupBy === "owner") {
    return { ...doc, owner: column.context.owner ?? null, updatedAt };
  }
  if (groupBy === "tag") {
    const tag = column.context.tag ?? null;
    if (!tag) {
      return { ...doc, tags: [], updatedAt };
    }
    return { ...doc, tags: [tag, ...doc.tags.filter((item) => item !== tag)], updatedAt };
  }
  if (groupBy === "status" && column.context.status) {
    return applyStatusChange(doc, column.context.status, updatedAt);
  }
  return doc;
}

function applyStatusChange(doc: DocumentEntry, status: DocumentStatus, updatedAt: number): DocumentEntry {
  if (status === doc.status) {
    return doc;
  }
  if (status === "ready") {
    return {
      ...doc,
      status: "ready",
      progress: 100,
      stage: "Output ready",
      etaMinutes: undefined,
      updatedAt,
      error: undefined,
      output: doc.output ?? buildOutputForDocument(doc),
      history: appendHistory(doc.history, createHistoryEntry(doc.id, "Marked ready", updatedAt, "success")),
    };
  }
  if (status === "processing") {
    return {
      ...doc,
      status: "processing",
      progress: 12,
      stage: "Normalizing columns",
      etaMinutes: 6,
      updatedAt,
      error: undefined,
      history: appendHistory(doc.history, createHistoryEntry(doc.id, "Processing restarted", updatedAt, "info")),
    };
  }
  if (status === "queued") {
    return {
      ...doc,
      status: "queued",
      progress: undefined,
      stage: "Queued for processing",
      etaMinutes: 6,
      updatedAt,
      error: undefined,
      history: appendHistory(doc.history, createHistoryEntry(doc.id, "Moved to queue", updatedAt)),
    };
  }
  return {
    ...doc,
    status: "failed",
    progress: undefined,
    stage: undefined,
    etaMinutes: undefined,
    updatedAt,
    error: doc.error ?? {
      summary: "Processing failed",
      detail: "We hit a validation issue while normalizing this file.",
      nextStep: "Retry now or fix mapping later.",
    },
    history: appendHistory(doc.history, createHistoryEntry(doc.id, "Marked failed", updatedAt, "danger")),
  };
}

function isAttention(doc: DocumentEntry) {
  return doc.status === "failed" || doc.mapping.attention > 0 || doc.mapping.unmapped > 0;
}

function getStatusDescription(doc: DocumentEntry) {
  switch (doc.status) {
    case "ready":
      return "Processed XLSX ready to download.";
    case "processing":
      return doc.stage ? `${doc.stage}.` : "Processing in progress.";
    case "failed":
      return doc.error?.summary ?? "Needs attention.";
    case "queued":
      return "Queued and waiting to start.";
    default:
      return "";
  }
}

function getMappingHealthLabel(mapping: MappingHealth) {
  if (mapping.attention > 0) {
    return `${mapping.attention} columns need attention`;
  }
  if (mapping.unmapped > 0) {
    return `${mapping.unmapped} unmapped columns`;
  }
  return "Mapping healthy";
}

function formatRelativeTime(nowTimestamp: number, timestamp: number) {
  const diff = Math.max(0, nowTimestamp - timestamp);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function formatBytes(bytes: number) {
  if (bytes === 0) {
    return "0 B";
  }
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${sizes[i]}`;
}

function getInitials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function readSavedViews(): SavedView[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    return [];
  }
}

function writeSavedViews(views: SavedView[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v5a1 1 0 0 0 1 1h5" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M11 4a7 7 0 1 1 0 14a7 7 0 0 1 0-14Z" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 16V4" />
      <path d="m6 10 6-6 6 6" />
      <path d="M4 20h16" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 4v12" />
      <path d="m6 10 6 6 6-6" />
      <path d="M4 20h16" />
    </svg>
  );
}

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M20 12a8 8 0 1 1-2.34-5.66" />
      <path d="M20 4v6h-6" />
    </svg>
  );
}

function GridIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function BoardIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="4" y="4" width="7" height="16" rx="1.5" />
      <rect x="13" y="4" width="7" height="9" rx="1.5" />
      <rect x="13" y="15" width="7" height="5" rx="1.5" />
    </svg>
  );
}

function TagIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M3 11V4a1 1 0 0 1 1-1h7l9 9-7 7-9-9Z" />
      <path d="M7.5 7.5h.01" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.6 2.5 18a1 1 0 0 0 .9 1.5h17.2a1 1 0 0 0 .9-1.5l-7.8-14.4a1 1 0 0 0-1.4 0Z" />
    </svg>
  );
}
