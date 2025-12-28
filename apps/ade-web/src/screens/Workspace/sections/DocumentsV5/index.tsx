import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type MutableRefObject } from "react";

import clsx from "clsx";

import { useSearchParams } from "@app/nav/urlState";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { client, resolveApiUrl } from "@shared/api/client";
import { ApiError } from "@shared/api/errors";
import { fetchTagCatalog, patchDocumentTags, uploadWorkspaceDocument } from "@shared/documents";
import { fetchRun, runLogsUrl, type RunResource } from "@shared/runs/api";
import { useUploadQueue } from "@shared/uploads/queue";
import type { components, paths } from "@schema";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type DocumentPage = components["schemas"]["DocumentPage"];
type RunPage = components["schemas"]["RunPage"];
type TagCatalogPage = components["schemas"]["TagCatalogPage"];

type ListDocumentsQueryBase = paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];
type DocumentFilters = Partial<{
  q: string;
  status_in: string;
  tags: string;
  tags_match: "any" | "all";
}>;
type DocumentsV5Query = ListDocumentsQueryBase & DocumentFilters;

type DocumentsV5StateFilter = "all" | "in-progress" | "ready" | "attention" | "archived";

const STATE_FILTERS: readonly {
  readonly id: DocumentsV5StateFilter;
  readonly label: string;
  readonly statuses?: readonly DocumentStatus[];
}[] = [
  { id: "all", label: "All" },
  { id: "in-progress", label: "In progress", statuses: ["uploaded", "processing"] },
  { id: "ready", label: "Ready", statuses: ["processed"] },
  { id: "attention", label: "Needs attention", statuses: ["failed"] },
  { id: "archived", label: "Archived", statuses: ["archived"] },
] as const;

const LIST_PAGE_SIZE = 50;

const documentsV5Keys = {
  root: () => ["documents-v5"] as const,
  workspace: (workspaceId: string) => [...documentsV5Keys.root(), workspaceId] as const,
  list: (workspaceId: string, filters: { q: string; state: DocumentsV5StateFilter; tags: string }) =>
    [...documentsV5Keys.workspace(workspaceId), "list", filters] as const,
  detail: (workspaceId: string, documentId: string) =>
    [...documentsV5Keys.workspace(workspaceId), "detail", documentId] as const,
  runsForDocument: (workspaceId: string, documentId: string) =>
    [...documentsV5Keys.workspace(workspaceId), "runs", documentId] as const,
  run: (runId: string) => [...documentsV5Keys.root(), "run", runId] as const,
  tagCatalog: (workspaceId: string, q: string) => [...documentsV5Keys.workspace(workspaceId), "tags", q] as const,
};

type DemoOutput = {
  readonly kind: "csv" | "json" | "pdf" | "none";
  readonly filename?: string;
  readonly contentType?: string;
  readonly text?: string;
  readonly note?: string;
};

const DEMO_WORKSPACE_ID = "demo-workspace";
const DEMO_DOCS: readonly DocumentRecord[] = [
  {
    id: "demo-doc-1",
    workspace_id: DEMO_WORKSPACE_ID,
    name: "Invoice_123.pdf",
    content_type: "application/pdf",
    byte_size: 872_112,
    metadata: {},
    status: "failed",
    source: "manual_upload",
    expires_at: "2099-01-01T00:00:00Z",
    created_at: "2025-12-23T10:20:00Z",
    updated_at: "2025-12-23T10:22:00Z",
    tags: ["Finance", "Urgent"],
    uploader: { id: "demo-user-1", name: "Sarah Parker", email: "sarah@example.com" },
    last_run: {
      run_id: "demo-run-1",
      status: "failed",
      run_at: "2025-12-23T10:22:00Z",
      message: "Validation failed. Column “amount” is missing.",
    },
  },
  {
    id: "demo-doc-2",
    workspace_id: DEMO_WORKSPACE_ID,
    name: "Vendor_Master.csv",
    content_type: "text/csv",
    byte_size: 642_331,
    metadata: {},
    status: "processed",
    source: "manual_upload",
    expires_at: "2099-01-01T00:00:00Z",
    created_at: "2025-12-23T09:57:00Z",
    updated_at: "2025-12-23T10:03:00Z",
    tags: ["Ops"],
    uploader: { id: "demo-user-2", name: "Alex Chen", email: "alex@example.com" },
    last_run: {
      run_id: "demo-run-2",
      status: "succeeded",
      run_at: "2025-12-23T10:03:00Z",
      message: "Processed output ready.",
    },
  },
  {
    id: "demo-doc-3",
    workspace_id: DEMO_WORKSPACE_ID,
    name: "Intake_Batch_12_24.xlsx",
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    byte_size: 2_401_223,
    metadata: {},
    status: "processing",
    source: "manual_upload",
    expires_at: "2099-01-01T00:00:00Z",
    created_at: "2025-12-23T10:08:00Z",
    updated_at: "2025-12-23T10:14:00Z",
    tags: [],
    uploader: { id: "demo-user-3", name: "Jamie Rivera", email: "jamie@example.com" },
    last_run: {
      run_id: "demo-run-3",
      status: "running",
      run_at: "2025-12-23T10:14:00Z",
      message: "Normalizing sheets…",
    },
  },
] as const;

const DEMO_OUTPUTS: Record<string, DemoOutput> = {
  "demo-run-1": {
    kind: "none",
    note: "No processed output was produced. Fix the input and try again.",
  },
  "demo-run-2": {
    kind: "csv",
    filename: "Vendor_Master_normalized.csv",
    contentType: "text/csv",
    text: [
      "vendor_id,vendor_name,active,updated_at",
      "101,Acme Supply,true,2025-12-23",
      "102,Northwind,false,2025-12-22",
      "103,Globex,true,2025-12-21",
    ].join("\n"),
  },
  "demo-run-3": {
    kind: "none",
    note: "Processing… output will appear here automatically once ready.",
  },
};

function parseStateFilter(value: string | null): DocumentsV5StateFilter {
  if (!value) return "all";
  return (STATE_FILTERS.some((filter) => filter.id === value) ? value : "all") as DocumentsV5StateFilter;
}

function parseTagsCsv(value: string | null) {
  if (!value) return [];
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function toTagsCsv(tags: readonly string[]) {
  return tags.map((tag) => tag.trim()).filter(Boolean).join(",");
}

function formatBytes(bytes: number) {
  const value = Math.max(0, bytes);
  const units = ["B", "KB", "MB", "GB"] as const;
  let unitIndex = 0;
  let display = value;
  while (display >= 1024 && unitIndex < units.length - 1) {
    display /= 1024;
    unitIndex += 1;
  }
  const precision = unitIndex === 0 ? 0 : display < 10 ? 1 : 0;
  return `${display.toFixed(precision)} ${units[unitIndex]}`;
}

const absoluteTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

function statusBadge(status: DocumentStatus) {
  switch (status) {
    case "uploaded":
      return { label: "Queued", classes: "bg-muted text-foreground" };
    case "processing":
      return { label: "Processing", classes: "bg-amber-100 text-amber-800" };
    case "processed":
      return { label: "Ready", classes: "bg-emerald-100 text-emerald-800" };
    case "failed":
      return { label: "Needs attention", classes: "bg-rose-100 text-rose-800" };
    case "archived":
      return { label: "Archived", classes: "bg-muted text-muted-foreground" };
    default:
      return { label: status, classes: "bg-muted text-foreground" };
  }
}

function describeError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You don’t have access to documents in this workspace.";
    }
    if (error.status >= 500) {
      return "The server is having trouble right now. Try again in a moment.";
    }
    return error.problem?.detail ?? error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

async function fetchDocumentsPage(
  workspaceId: string,
  options: {
    readonly page: number;
    readonly q: string;
    readonly state: DocumentsV5StateFilter;
    readonly tags: readonly string[];
  },
  signal?: AbortSignal,
): Promise<DocumentPage> {
  const state = STATE_FILTERS.find((filter) => filter.id === options.state);
  const statuses = state?.statuses ?? [];
  const q = options.q.trim();

  const query: DocumentsV5Query = {
    page: Math.max(1, Math.floor(options.page)),
    page_size: LIST_PAGE_SIZE,
    include_total: options.page === 1,
    sort: "-created_at",
    ...(q.length >= 2 ? { q } : {}),
    ...(statuses.length > 0 ? { status_in: statuses.join(",") } : {}),
    ...(options.tags.length > 0 ? { tags: options.tags.join(","), tags_match: "any" } : {}),
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data as DocumentPage;
}

async function fetchDocument(workspaceId: string, documentId: string, signal?: AbortSignal): Promise<DocumentRecord> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    signal,
  });

  if (!data) {
    throw new Error("Document not found.");
  }

  return data as DocumentRecord;
}

async function fetchLatestRunId(workspaceId: string, documentId: string, signal?: AbortSignal): Promise<string | null> {
  const query: paths["/api/v1/workspaces/{workspace_id}/runs"]["get"]["parameters"]["query"] = {
    page: 1,
    page_size: 1,
    input_document_id: documentId,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/runs", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  const page = data as RunPage | undefined;
  const first = page?.items?.[0];
  return first?.id ?? null;
}

function runOutputDownloadUrl(runId: string) {
  return resolveApiUrl(`/api/v1/runs/${runId}/output/download`);
}

async function downloadRunOutput(runId: string, signal?: AbortSignal) {
  const { data, response } = await client.GET("/api/v1/runs/{run_id}/output/download", {
    params: { path: { run_id: runId } },
    parseAs: "blob",
    signal,
  });

  if (!data) {
    throw new Error("Output is not available.");
  }

  const header = response.headers.get("content-disposition");
  const filename = parseFilename(header) ?? `run-${runId}-output`;
  const contentType = response.headers.get("content-type") ?? "application/octet-stream";
  return { blob: data, filename, contentType };
}

function parseFilename(header: string | null) {
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

function triggerDownload(blob: Blob, filename: string) {
  if (typeof document === "undefined") {
    return;
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function parseCsvPreview(text: string, options?: { maxRows?: number; maxColumns?: number }) {
  const maxRows = options?.maxRows ?? 25;
  const maxColumns = options?.maxColumns ?? 12;
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  const pushField = () => {
    row.push(field);
    field = "";
  };
  const pushRow = () => {
    if (rows.length >= maxRows) return;
    rows.push(row.slice(0, maxColumns));
    row = [];
  };

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (inQuotes) {
      if (char === "\"") {
        const next = text[i + 1];
        if (next === "\"") {
          field += "\"";
          i += 1;
          continue;
        }
        inQuotes = false;
        continue;
      }
      field += char;
      continue;
    }

    if (char === "\"") {
      inQuotes = true;
      continue;
    }

    if (char === ",") {
      pushField();
      continue;
    }

    if (char === "\n") {
      pushField();
      pushRow();
      if (rows.length >= maxRows) break;
      continue;
    }

    if (char === "\r") {
      const next = text[i + 1];
      if (next === "\n") {
        i += 1;
      }
      pushField();
      pushRow();
      if (rows.length >= maxRows) break;
      continue;
    }

    field += char;
  }

  if (rows.length < maxRows && (field.length > 0 || row.length > 0)) {
    pushField();
    pushRow();
  }

  return rows;
}

export default function WorkspaceDocumentsV5Route() {
  const { workspace } = useWorkspaceContext();
  const workspaceId = workspace.id;
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const demoMode = searchParams.get("demo") === "1";
  const state = parseStateFilter(searchParams.get("state"));
  const q = searchParams.get("q") ?? "";
  const selectedId = searchParams.get("selected");
  const selectedTags = useMemo(() => parseTagsCsv(searchParams.get("tags")), [searchParams]);

  const filters = useMemo(
    () => ({
      q,
      state,
      tags: toTagsCsv(selectedTags),
    }),
    [q, selectedTags, state],
  );

  const documentsQuery = useInfiniteQuery({
    queryKey: documentsV5Keys.list(workspaceId, filters),
    queryFn: ({ pageParam, signal }) => fetchDocumentsPage(workspaceId, { page: pageParam, q, state, tags: selectedTags }, signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: !demoMode && workspaceId.length > 0,
    staleTime: 5_000,
    refetchInterval: (query) => {
      const pages = query.state.data?.pages ?? [];
      const hasActive = pages.some((page) => (page.items ?? []).some((doc) => doc.status === "uploaded" || doc.status === "processing"));
      return hasActive ? 5_000 : 15_000;
    },
  });

  const demoDocuments = useMemo(() => {
    if (!demoMode) return [];
    const normalizedQuery = q.trim().toLowerCase();
    const stateStatuses = STATE_FILTERS.find((filter) => filter.id === state)?.statuses ?? [];
    return DEMO_DOCS.filter((doc) => {
      if (stateStatuses.length > 0 && !stateStatuses.includes(doc.status)) return false;
      if (selectedTags.length > 0) {
        const tagSet = new Set((doc.tags ?? []).map((tag) => tag.toLowerCase()));
        if (!selectedTags.some((tag) => tagSet.has(tag.toLowerCase()))) return false;
      }
      if (normalizedQuery.length >= 2 && !doc.name.toLowerCase().includes(normalizedQuery)) return false;
      return true;
    });
  }, [demoMode, q, selectedTags, state]);

  const documents: DocumentRecord[] = useMemo(() => {
    if (demoMode) return [...demoDocuments];
    return documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [];
  }, [demoDocuments, demoMode, documentsQuery.data?.pages]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }
    if (demoMode) {
      if (!documents.some((doc) => doc.id === selectedId)) {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.delete("selected");
          return next;
        }, { replace: true });
      }
      return;
    }
    if (documentsQuery.isSuccess && !documents.some((doc) => doc.id === selectedId)) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete("selected");
        return next;
      }, { replace: true });
    }
  }, [demoMode, documents, documentsQuery.isSuccess, selectedId, setSearchParams]);

  const selectedFromList = useMemo(
    () => (selectedId ? documents.find((doc) => doc.id === selectedId) ?? null : null),
    [documents, selectedId],
  );

  const documentQuery = useQuery({
    queryKey: selectedId ? documentsV5Keys.detail(workspaceId, selectedId) : ["documents-v5", "detail", "none"],
    queryFn: ({ signal }) => fetchDocument(workspaceId, selectedId ?? "", signal),
    enabled: Boolean(selectedId) && !demoMode,
    initialData: selectedFromList ?? undefined,
    staleTime: 10_000,
  });

  const selectedDocument: DocumentRecord | null = demoMode ? selectedFromList : documentQuery.data ?? null;

  const [inspectorTab, setInspectorTab] = useState<"preview" | "details">("preview");
  const [allowLargePreview, setAllowLargePreview] = useState(false);

  useEffect(() => {
    setInspectorTab("preview");
    setAllowLargePreview(false);
  }, [selectedId]);

  const runId = useMemo(() => {
    if (!selectedDocument) return null;
    const inlineRunId = selectedDocument.last_run?.run_id ?? null;
    return inlineRunId || null;
  }, [selectedDocument]);

  const runIdQuery = useQuery({
    queryKey: selectedId ? documentsV5Keys.runsForDocument(workspaceId, selectedId) : ["documents-v5", "runs", "none"],
    queryFn: ({ signal }) => fetchLatestRunId(workspaceId, selectedId ?? "", signal),
    enabled: Boolean(selectedId) && !demoMode && !runId,
    staleTime: 10_000,
  });

  const effectiveRunId = runId ?? (demoMode ? (selectedDocument?.last_run?.run_id ?? null) : runIdQuery.data ?? null);

  const runQuery = useQuery<RunResource>({
    queryKey: effectiveRunId ? documentsV5Keys.run(effectiveRunId) : ["documents-v5", "run", "none"],
    queryFn: ({ signal }) => fetchRun(effectiveRunId ?? "", signal),
    enabled: Boolean(effectiveRunId) && !demoMode,
    staleTime: 10_000,
    refetchInterval: (query) => (query.state.data?.status === "queued" || query.state.data?.status === "running" ? 4_000 : false),
  });

  const effectiveRun = demoMode && effectiveRunId ? createDemoRun(effectiveRunId) : runQuery.data ?? null;

  const downloadProcessedMutation = useMutation({
    mutationFn: async () => {
      if (!effectiveRunId) {
        throw new Error("No processed output is available yet.");
      }
      if (demoMode) {
        const demo = DEMO_OUTPUTS[effectiveRunId];
        if (!demo || demo.kind === "none") {
          throw new Error(demo?.note ?? "No processed output is available yet.");
        }
        const blob = new Blob([demo.text ?? ""], { type: demo.contentType ?? "text/plain" });
        triggerDownload(blob, demo.filename ?? "processed-output");
        return;
      }
      const { blob, filename } = await downloadRunOutput(effectiveRunId);
      triggerDownload(blob, filename);
    },
  });

  const previewEnabled = inspectorTab === "preview" && Boolean(effectiveRunId) && Boolean(selectedDocument) && (demoMode || Boolean(effectiveRun));
  const previewTooLarge = Boolean(effectiveRun?.output?.size_bytes && effectiveRun.output.size_bytes > 600_000);
  const previewAllowed = !previewTooLarge || allowLargePreview;

  const previewQuery = useQuery({
    queryKey: ["documents-v5", "preview", effectiveRunId ?? "none"],
    queryFn: async ({ signal }) => {
      if (!effectiveRunId) {
        return null;
      }
      if (demoMode) {
        return DEMO_OUTPUTS[effectiveRunId] ?? { kind: "none", note: "No output." };
      }
      const { blob, filename, contentType } = await downloadRunOutput(effectiveRunId, signal);
      const inferredType = contentType || effectiveRun?.output?.content_type || "";
      return {
        kind: inferPreviewKind(inferredType, filename),
        filename,
        contentType: inferredType,
        blob,
      };
    },
    enabled: previewEnabled && previewAllowed,
    staleTime: 60_000,
  });

  const previewPayload = previewQuery.data as
    | null
    | (DemoOutput & { blob?: Blob })
    | { kind: "csv" | "json" | "pdf" | "none"; filename: string; contentType: string; blob: Blob };

  const listContainerRef = useRef<HTMLDivElement | null>(null);
  const handleListScroll = useCallback(() => {
    const node = listContainerRef.current;
    if (!node || demoMode) {
      return;
    }
    if (!documentsQuery.hasNextPage || documentsQuery.isFetchingNextPage) {
      return;
    }
    const threshold = 500;
    const remaining = node.scrollHeight - node.scrollTop - node.clientHeight;
    if (remaining < threshold) {
      documentsQuery.fetchNextPage();
    }
  }, [demoMode, documentsQuery]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const uploadQueue = useUploadQueue({
    concurrency: 3,
    startUpload: (file, { onProgress }) => uploadWorkspaceDocument(workspaceId, file, { onProgress }),
  });

  const lastSuccessCountRef = useRef(0);
  useEffect(() => {
    const successCount = uploadQueue.items.filter((item) => item.status === "succeeded").length;
    if (successCount > lastSuccessCountRef.current) {
      lastSuccessCountRef.current = successCount;
      queryClient.invalidateQueries({ queryKey: documentsV5Keys.workspace(workspaceId) });
    }
  }, [queryClient, uploadQueue.items, workspaceId]);

  const enqueueFiles = useCallback(
    (files: readonly File[]) => {
      if (!files.length || demoMode) {
        return;
      }
      uploadQueue.enqueue(files);
    },
    [demoMode, uploadQueue],
  );

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files ?? []);
      enqueueFiles(files);
      event.target.value = "";
    },
    [enqueueFiles],
  );

  const onDragOver = useCallback((event: DragEvent) => {
    if (demoMode) return;
    event.preventDefault();
    event.stopPropagation();
    setDragActive(true);
  }, [demoMode]);

  const onDragLeave = useCallback((event: DragEvent) => {
    if (demoMode) return;
    event.preventDefault();
    event.stopPropagation();
    if ((event.target as HTMLElement | null)?.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDragActive(false);
  }, [demoMode]);

  const onDrop = useCallback((event: DragEvent) => {
    if (demoMode) return;
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    enqueueFiles(files);
  }, [demoMode, enqueueFiles]);

  const setStateFilter = useCallback(
    (next: DocumentsV5StateFilter) => {
      setSearchParams((prev) => {
        const nextParams = new URLSearchParams(prev);
        if (next === "all") {
          nextParams.delete("state");
        } else {
          nextParams.set("state", next);
        }
        nextParams.delete("selected");
        return nextParams;
      });
    },
    [setSearchParams],
  );

  const setTagsFilter = useCallback(
    (tags: readonly string[]) => {
      setSearchParams((prev) => {
        const nextParams = new URLSearchParams(prev);
        const csv = toTagsCsv(tags);
        if (csv) {
          nextParams.set("tags", csv);
        } else {
          nextParams.delete("tags");
        }
        nextParams.delete("selected");
        return nextParams;
      });
    },
    [setSearchParams],
  );

  const setSelected = useCallback(
    (id: string | null) => {
      setSearchParams((prev) => {
        const nextParams = new URLSearchParams(prev);
        if (id) {
          nextParams.set("selected", id);
        } else {
          nextParams.delete("selected");
        }
        return nextParams;
      });
    },
    [setSearchParams],
  );

  const showDemo = useCallback(() => {
    setSearchParams((prev) => {
      const nextParams = new URLSearchParams(prev);
      nextParams.set("demo", "1");
      nextParams.delete("selected");
      return nextParams;
    });
  }, [setSearchParams]);

  const exitDemo = useCallback(() => {
    setSearchParams((prev) => {
      const nextParams = new URLSearchParams(prev);
      nextParams.delete("demo");
      nextParams.delete("selected");
      return nextParams;
    });
  }, [setSearchParams]);

  const tagsDraftRef = useRef<HTMLInputElement | null>(null);
  const [tagsDraft, setTagsDraft] = useState("");

  const addFilterTag = useCallback(() => {
    const normalized = tagsDraft.trim();
    if (!normalized) return;
    const existing = new Set(selectedTags.map((tag) => tag.toLowerCase()));
    if (existing.has(normalized.toLowerCase())) {
      setTagsDraft("");
      return;
    }
    setTagsDraft("");
    setTagsFilter([...selectedTags, normalized]);
    tagsDraftRef.current?.focus();
  }, [selectedTags, setTagsFilter, tagsDraft]);

  const removeFilterTag = useCallback(
    (tag: string) => {
      setTagsFilter(selectedTags.filter((value) => value.toLowerCase() !== tag.toLowerCase()));
    },
    [selectedTags, setTagsFilter],
  );

  const uploadButton = (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFileInputChange}
      />
      <Button
        variant="secondary"
        size="sm"
        disabled={demoMode}
        onClick={() => fileInputRef.current?.click()}
      >
        Upload
      </Button>
    </>
  );

  const hasDocuments = documents.length > 0;
  const selectedCountLabel = demoMode ? "Demo" : `${documentsQuery.data?.pages?.[0]?.total ?? documents.length}`;

  const listBody = (() => {
    if (demoMode) {
      if (!hasDocuments) {
        return <EmptyListState onUseDemo={undefined} />;
      }
      return (
        <DocumentList
          documents={documents}
          selectedId={selectedId}
          onSelect={setSelected}
          onScroll={handleListScroll}
          containerRef={listContainerRef}
        />
      );
    }

    if (documentsQuery.isLoading) {
      return (
        <div className="flex flex-1 items-center justify-center px-6 py-10">
          <PageState title="Loading documents" variant="loading" />
        </div>
      );
    }

    if (documentsQuery.isError) {
      return (
	        <div className="flex flex-1 items-center justify-center px-6 py-10 text-center">
	          <PageState
	            title="Unable to load documents"
	            description={describeError(documentsQuery.error)}
	            variant="error"
	            action={
	              <div className="mt-4 flex flex-wrap justify-center gap-2">
	                <Button variant="secondary" size="sm" onClick={() => documentsQuery.refetch()}>
	                  Retry
	                </Button>
                <Button variant="secondary" size="sm" onClick={showDemo}>
                  Use demo
                </Button>
              </div>
            }
          />
        </div>
      );
    }

    if (!hasDocuments) {
      return <EmptyListState onUseDemo={showDemo} />;
    }

    return (
      <DocumentList
        documents={documents}
        selectedId={selectedId}
        onSelect={setSelected}
        onScroll={handleListScroll}
        containerRef={listContainerRef}
      />
    );
  })();

  return (
    <div
      className="relative flex min-h-0 flex-1 overflow-hidden bg-background"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {dragActive ? (
        <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-overlay/10 backdrop-blur-[2px]">
          <div className="rounded-3xl border border-border/80 bg-card/90 px-10 py-8 shadow-xl">
            <div className="text-sm font-semibold text-foreground">Drop files to upload</div>
            <div className="mt-1 text-xs text-muted-foreground">They’ll appear here as soon as they’re received.</div>
          </div>
        </div>
      ) : null}

      <div className="flex w-[min(30rem,42%)] min-w-[22rem] flex-col border-r border-border/70 bg-card">
        <div className="border-b border-border/70 px-5 pb-4 pt-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-base font-semibold text-foreground">Documents v5</h1>
                <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
                  {selectedCountLabel}
                </span>
                {demoMode ? (
                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                    Demo
                  </span>
                ) : null}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Upload, review, preview, download processed output.</div>
            </div>
            <div className="flex items-center gap-2">
              {demoMode ? (
                <Button variant="secondary" size="sm" onClick={exitDemo}>
                  Exit demo
                </Button>
              ) : null}
              {uploadButton}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {STATE_FILTERS.map((filter) => {
              const active = filter.id === state;
              return (
                <button
                  key={filter.id}
                  type="button"
                  onClick={() => setStateFilter(filter.id)}
                  className={clsx(
                    "focus-ring rounded-full px-3 py-1.5 text-xs font-semibold transition",
                    active ? "bg-foreground text-background" : "bg-muted text-foreground hover:bg-muted",
                  )}
                >
                  {filter.label}
                </button>
              );
            })}
          </div>

          <div className="mt-4">
            <div className="flex flex-wrap items-center gap-2">
              {selectedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeFilterTag(tag)}
                  className="focus-ring inline-flex items-center gap-2 rounded-full bg-muted px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted"
                  title="Remove tag filter"
                >
                  <span>{tag}</span>
                  <span aria-hidden="true" className="text-muted-foreground">
                    ×
                  </span>
                </button>
              ))}
              <div className="flex min-w-[12rem] flex-1 items-center gap-2">
                <label className="sr-only" htmlFor="documents-v5-tags-filter">
                  Filter by tag
                </label>
                <Input
                  id="documents-v5-tags-filter"
                  ref={tagsDraftRef}
                  value={tagsDraft}
                  onChange={(event) => setTagsDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === ",") {
                      event.preventDefault();
                      addFilterTag();
                    }
                    if (event.key === "Backspace" && !tagsDraft && selectedTags.length > 0) {
                      event.preventDefault();
                      removeFilterTag(selectedTags[selectedTags.length - 1]);
                    }
                  }}
                  placeholder="Filter tags…"
                  disabled={demoMode}
                  className="h-9 rounded-full border-border bg-background px-4 text-xs focus-visible:ring-ring"
                />
	                {selectedTags.length > 0 || state !== "all" ? (
	                  <button
	                    type="button"
	                    onClick={() => {
	                      setTagsDraft("");
	                      setSearchParams((prev) => {
	                        const nextParams = new URLSearchParams(prev);
	                        nextParams.delete("tags");
	                        nextParams.delete("state");
	                        nextParams.delete("selected");
	                        return nextParams;
	                      });
	                    }}
	                    className="focus-ring rounded-full px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-background"
	                  >
                    Clear
                  </button>
                ) : null}
              </div>
            </div>
            <div className="mt-2 text-[11px] text-muted-foreground">Search uses the top bar. Tags filter supports Enter/Backspace.</div>
          </div>
        </div>

        <div className="relative flex min-h-0 flex-1 flex-col">
          {listBody}

          {uploadQueue.summary.inFlightCount > 0 || uploadQueue.summary.failedCount > 0 ? (
            <UploadShelf
              items={uploadQueue.items}
              onCancel={uploadQueue.cancel}
              onRetry={uploadQueue.retry}
              onRemove={uploadQueue.remove}
              onClearCompleted={uploadQueue.clearCompleted}
            />
          ) : null}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <Inspector
          workspaceId={workspaceId}
          demoMode={demoMode}
          document={selectedDocument}
          run={effectiveRun}
          runError={runQuery.error}
          runLoading={runQuery.isLoading}
          tab={inspectorTab}
          onTabChange={setInspectorTab}
          onDownloadProcessed={() => downloadProcessedMutation.mutate()}
          downloading={downloadProcessedMutation.isPending}
          onAllowLargePreview={() => setAllowLargePreview(true)}
          previewTooLarge={previewTooLarge}
          previewAllowed={previewAllowed}
          previewPayload={previewPayload}
          previewError={previewQuery.error}
          previewLoading={previewQuery.isLoading}
        />
      </div>
    </div>
  );
}

function EmptyListState({ onUseDemo }: { readonly onUseDemo?: (() => void) | undefined }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-8 py-12 text-center">
      <div className="text-sm font-semibold text-foreground">No documents yet</div>
      <div className="mt-2 max-w-sm text-sm text-muted-foreground">
        Drag & drop files into this window, or use Upload. Processed outputs will always be the primary download.
      </div>
      {onUseDemo ? (
        <div className="mt-6">
          <Button variant="secondary" size="sm" onClick={onUseDemo}>
            Try demo data
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function DocumentList({
  documents,
  selectedId,
  onSelect,
  onScroll,
  containerRef,
}: {
  readonly documents: readonly DocumentRecord[];
  readonly selectedId: string | null | undefined;
  readonly onSelect: (id: string | null) => void;
  readonly onScroll: () => void;
  readonly containerRef: MutableRefObject<HTMLDivElement | null>;
}) {
  return (
    <div
      ref={containerRef}
      className="min-h-0 flex-1 overflow-y-auto px-3 py-3"
      onScroll={onScroll}
    >
      <div className="flex flex-col gap-1">
        {documents.map((doc) => (
          <DocumentRow
            key={doc.id}
            document={doc}
            selected={doc.id === selectedId}
            onClick={() => onSelect(doc.id === selectedId ? null : doc.id)}
          />
        ))}
      </div>
    </div>
  );
}

function DocumentRow({
  document,
  selected,
  onClick,
}: {
  readonly document: DocumentRecord;
  readonly selected: boolean;
  readonly onClick: () => void;
}) {
  const badge = statusBadge(document.status);
  const updatedAt = document.updated_at ? absoluteTime.format(new Date(document.updated_at)) : "";
  const tags = document.tags ?? [];

  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "focus-ring group flex w-full items-start justify-between gap-3 rounded-2xl px-4 py-3 text-left transition",
        selected ? "bg-foreground text-background" : "bg-card hover:bg-background",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className={clsx("truncate text-sm font-semibold", selected ? "text-white" : "text-foreground")}>
            {document.name}
          </div>
          <span
            className={clsx(
              "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
              selected ? "bg-card/15 text-white" : badge.classes,
            )}
          >
            {badge.label}
          </span>
        </div>
        <div className={clsx("mt-1 flex flex-wrap items-center gap-2 text-[11px]", selected ? "text-background/70" : "text-muted-foreground")}>
          <span>{formatBytes(document.byte_size)}</span>
          {updatedAt ? (
            <>
              <span aria-hidden="true">·</span>
              <span className="truncate">{updatedAt}</span>
            </>
          ) : null}
        </div>
        {tags.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className={clsx(
                  "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  selected ? "bg-card/10 text-background/85" : "bg-muted text-muted-foreground",
                )}
              >
                {tag}
              </span>
            ))}
            {tags.length > 4 ? (
              <span
                className={clsx(
                  "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  selected ? "bg-card/10 text-background/70" : "bg-muted text-muted-foreground",
                )}
              >
                +{tags.length - 4}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className={clsx("mt-0.5 text-[11px] font-semibold", selected ? "text-background/60" : "text-muted-foreground")}>
        {selected ? "Selected" : ""}
      </div>
    </button>
  );
}

function UploadShelf({
  items,
  onCancel,
  onRetry,
  onRemove,
  onClearCompleted,
}: {
  readonly items: ReturnType<typeof useUploadQueue>["items"];
  readonly onCancel: (id: string) => void;
  readonly onRetry: (id: string) => void;
  readonly onRemove: (id: string) => void;
  readonly onClearCompleted: () => void;
}) {
  const active = items.filter((item) => item.status === "uploading" || item.status === "queued");
  const completed = items.filter((item) => item.status === "succeeded" || item.status === "failed" || item.status === "cancelled");
  const visible = [...active, ...completed].slice(0, 4);

  return (
    <div className="border-t border-border/70 bg-card px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-foreground">
          Uploads
          {active.length > 0 ? <span className="ml-1 text-muted-foreground">({active.length} active)</span> : null}
        </div>
        {completed.length > 0 ? (
          <button
            type="button"
            className="focus-ring text-xs font-semibold text-muted-foreground hover:text-foreground"
            onClick={onClearCompleted}
          >
            Clear completed
          </button>
        ) : null}
      </div>
      <div className="mt-2 flex flex-col gap-2">
        {visible.map((item) => (
          <div key={item.id} className="rounded-2xl bg-background px-3 py-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold text-foreground">{item.file.name}</div>
                <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>{item.status === "queued" ? "Queued" : item.status === "uploading" ? "Uploading" : item.status === "succeeded" ? "Uploaded" : item.status === "failed" ? "Failed" : "Cancelled"}</span>
                  <span aria-hidden="true">·</span>
                  <span>{item.progress.percent}%</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {item.status === "uploading" || item.status === "queued" ? (
                  <button
                    type="button"
                    className="focus-ring rounded-full px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:bg-card"
                    onClick={() => onCancel(item.id)}
                  >
                    Cancel
                  </button>
                ) : null}
                {item.status === "failed" ? (
                  <button
                    type="button"
                    className="focus-ring rounded-full px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:bg-card"
                    onClick={() => onRetry(item.id)}
                  >
                    Retry
                  </button>
                ) : null}
                {item.status === "succeeded" || item.status === "failed" || item.status === "cancelled" ? (
                  <button
                    type="button"
                    className="focus-ring rounded-full px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:bg-card hover:text-muted-foreground"
                    onClick={() => onRemove(item.id)}
                    aria-label="Remove upload"
                  >
                    ×
                  </button>
                ) : null}
              </div>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-card">
              <div
                className={clsx(
                  "h-full rounded-full transition-all",
                  item.status === "failed" ? "bg-rose-400" : item.status === "cancelled" ? "bg-muted" : "bg-brand-500",
                )}
                style={{ width: `${Math.min(100, Math.max(0, item.progress.percent))}%` }}
              />
            </div>
            {item.error ? <div className="mt-2 text-[11px] text-rose-700">{item.error}</div> : null}
          </div>
        ))}
        {items.length > visible.length ? (
          <div className="text-[11px] text-muted-foreground">And {items.length - visible.length} more…</div>
        ) : null}
      </div>
    </div>
  );
}

function Inspector({
  workspaceId,
  demoMode,
  document,
  run,
  runLoading,
  runError,
  tab,
  onTabChange,
  onDownloadProcessed,
  downloading,
  previewTooLarge,
  previewAllowed,
  onAllowLargePreview,
  previewPayload,
  previewLoading,
  previewError,
}: {
  readonly workspaceId: string;
  readonly demoMode: boolean;
  readonly document: DocumentRecord | null;
  readonly run: RunResource | null;
  readonly runLoading: boolean;
  readonly runError: unknown;
  readonly tab: "preview" | "details";
  readonly onTabChange: (value: "preview" | "details") => void;
  readonly onDownloadProcessed: () => void;
  readonly downloading: boolean;
  readonly previewTooLarge: boolean;
  readonly previewAllowed: boolean;
  readonly onAllowLargePreview: () => void;
  readonly previewPayload: unknown;
  readonly previewLoading: boolean;
  readonly previewError: unknown;
}) {
  if (!document) {
    return (
      <div className="flex flex-1 items-center justify-center px-10 text-center">
        <div>
          <div className="text-sm font-semibold text-foreground">Select a document</div>
          <div className="mt-2 max-w-sm text-sm text-muted-foreground">
            Preview the processed output, then download it with confidence.
          </div>
        </div>
      </div>
    );
  }

  const badge = statusBadge(document.status);
  const hasInlineRun = Boolean(document.last_run?.run_id);
  const runMessage = document.last_run?.message ?? null;
  const originalUrl = resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`);

  const processedReady = Boolean(run?.output?.ready && run.output.has_output);
  const processedFilename = run?.output?.filename ?? null;
  const processedContentType = run?.output?.content_type ?? null;

  const runLogs = run ? runLogsUrl(run) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border/70 bg-card px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="truncate text-base font-semibold text-foreground">{document.name}</div>
              <span className={clsx("rounded-full px-2 py-0.5 text-[11px] font-semibold", badge.classes)}>{badge.label}</span>
              {demoMode ? (
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">Demo</span>
              ) : null}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>{formatBytes(document.byte_size)}</span>
              <span aria-hidden="true">·</span>
              <span>Uploaded {absoluteTime.format(new Date(document.created_at))}</span>
              {runMessage ? (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="truncate">{runMessage}</span>
                </>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="primary"
              size="sm"
              isLoading={downloading}
              disabled={!processedReady && document.status !== "processed"}
              onClick={onDownloadProcessed}
            >
              Download processed
            </Button>
            <a
              href={processedReady && run ? runOutputDownloadUrl(run.id) : undefined}
              className={clsx(
                "focus-ring inline-flex h-8 items-center justify-center rounded-lg border border-border bg-card px-3 text-xs font-semibold text-foreground transition hover:bg-background",
                !processedReady ? "pointer-events-none opacity-40" : "",
              )}
              target="_blank"
              rel="noreferrer"
            >
              Open in new tab
            </a>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <a
            href={originalUrl}
            className="text-xs font-semibold text-muted-foreground hover:text-foreground"
            target="_blank"
            rel="noreferrer"
          >
            Download original
          </a>
          {runLogs ? (
            <a
              href={runLogs}
              className="text-xs font-semibold text-muted-foreground hover:text-foreground"
              target="_blank"
              rel="noreferrer"
            >
              Download logs
            </a>
          ) : null}
          {hasInlineRun ? (
            <span className="text-xs text-muted-foreground">Last run linked</span>
          ) : null}
        </div>

        <div className="mt-5">
          <TabsRoot value={tab} onValueChange={(value) => onTabChange(value as "preview" | "details")}>
            <TabsList className="inline-flex rounded-xl bg-muted p-1">
              <TabsTrigger
                value="preview"
                className={clsx(
                  "focus-ring rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                  tab === "preview" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                Preview
              </TabsTrigger>
              <TabsTrigger
                value="details"
                className={clsx(
                  "focus-ring rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                  tab === "details" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                Details
              </TabsTrigger>
            </TabsList>

            <TabsContent value="preview" className="mt-5">
              <PreviewPanel
                demoMode={demoMode}
                document={document}
                run={run}
                runLoading={runLoading}
                runError={runError}
                previewTooLarge={previewTooLarge}
                previewAllowed={previewAllowed}
                onAllowLargePreview={onAllowLargePreview}
                payload={previewPayload}
                loading={previewLoading}
                error={previewError}
              />
            </TabsContent>

            <TabsContent value="details" className="mt-5">
              <DetailsPanel workspaceId={workspaceId} document={document} run={run} />
            </TabsContent>
          </TabsRoot>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto bg-background px-6 py-6">
        {tab === "preview" ? (
          <div className="text-xs text-muted-foreground">
            {processedFilename ? `Processed file: ${processedFilename}` : processedContentType ? `Type: ${processedContentType}` : ""}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function inferPreviewKind(contentType: string, filename: string) {
  const type = contentType.toLowerCase();
  if (type.includes("pdf")) return "pdf";
  if (type.includes("json")) return "json";
  if (type.includes("csv")) return "csv";
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "pdf";
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".csv")) return "csv";
  return "none";
}

function createDemoRun(runId: string): RunResource | null {
  const output = DEMO_OUTPUTS[runId];
  if (!output) return null;
  const status = runId === "demo-run-2" ? "succeeded" : runId === "demo-run-1" ? "failed" : "running";
  return {
    id: runId,
    object: "ade.run",
    workspace_id: DEMO_WORKSPACE_ID,
    configuration_id: "demo-config",
    build_id: "demo-build",
    status,
    created_at: "2025-12-23T10:00:00Z",
    started_at: "2025-12-23T10:00:10Z",
    completed_at: status === "succeeded" || status === "failed" ? "2025-12-23T10:03:00Z" : null,
    duration_seconds: status === "succeeded" ? 172 : null,
    exit_code: status === "succeeded" ? 0 : status === "failed" ? 1 : null,
    input: undefined,
    output: {
      ready: output.kind !== "none",
      has_output: output.kind !== "none",
      filename: output.filename ?? null,
      content_type: output.contentType ?? null,
      download_url: output.kind !== "none" ? `/api/v1/runs/${runId}/output/download` : null,
      output_path: null,
      processed_file: null,
      size_bytes: output.text ? output.text.length : null,
    },
    links: {
      self: `/api/v1/runs/${runId}`,
      events: `/api/v1/runs/${runId}/events`,
      events_stream: `/api/v1/runs/${runId}/events/stream`,
      events_download: `/api/v1/runs/${runId}/events/download`,
      input: `/api/v1/runs/${runId}/input`,
      input_download: `/api/v1/runs/${runId}/input/download`,
      output: `/api/v1/runs/${runId}/output`,
      output_download: `/api/v1/runs/${runId}/output/download`,
      output_metadata: `/api/v1/runs/${runId}/output/metadata`,
    },
    events_url: null,
    events_stream_url: null,
    events_download_url: null,
    engine_version: null,
    config_version: null,
    env_reason: null,
    env_reused: null,
    failure_code: null,
    failure_stage: null,
    failure_message: status === "failed" ? "Output was not produced." : null,
  };
}

function PreviewPanel({
  demoMode,
  document,
  run,
  runLoading,
  runError,
  previewTooLarge,
  previewAllowed,
  onAllowLargePreview,
  payload,
  loading,
  error,
}: {
  readonly demoMode: boolean;
  readonly document: DocumentRecord;
  readonly run: RunResource | null;
  readonly runLoading: boolean;
  readonly runError: unknown;
  readonly previewTooLarge: boolean;
  readonly previewAllowed: boolean;
  readonly onAllowLargePreview: () => void;
  readonly payload: unknown;
  readonly loading: boolean;
  readonly error: unknown;
}) {
  const lastRunStatus = document.last_run?.status ?? null;
  const outputReady = Boolean(run?.output?.ready && run.output.has_output);

  if (runLoading && !demoMode) {
    return <PageState title="Loading processed output" variant="loading" />;
  }

  if (runError && !demoMode) {
    return (
      <PageState
        title="Unable to load run"
        description={describeError(runError)}
        variant="error"
      />
    );
  }

  if (previewTooLarge && !previewAllowed) {
    return (
      <div className="rounded-3xl border border-border/70 bg-card p-6">
        <div className="text-sm font-semibold text-foreground">Large output</div>
        <div className="mt-2 text-sm text-muted-foreground">
          This output is large. Load a preview anyway?
        </div>
        <div className="mt-4">
          <Button variant="secondary" size="sm" onClick={onAllowLargePreview}>
            Load preview
          </Button>
        </div>
      </div>
    );
  }

  if (!outputReady) {
    const note =
      document.status === "failed" || lastRunStatus === "failed"
        ? "Processing failed. Review the message and logs, then try again."
        : document.status === "processing"
          ? "Processing… output will appear here automatically."
          : "No processed output yet.";
    return (
      <div className="rounded-3xl border border-border/70 bg-card p-6">
        <div className="text-sm font-semibold text-foreground">Processed output</div>
        <div className="mt-2 text-sm text-muted-foreground">{note}</div>
      </div>
    );
  }

  if (loading) {
    return <PageState title="Loading preview" variant="loading" />;
  }

  if (error) {
    return <PageState title="Preview unavailable" description={describeError(error)} variant="error" />;
  }

  if (!payload) {
    return <PageState title="Preview unavailable" description="No preview data was returned." variant="error" />;
  }

  if (demoMode && typeof payload === "object" && payload && "kind" in payload) {
    const demo = payload as DemoOutput;
    return <DemoPreview demo={demo} />;
  }

  if (typeof payload === "object" && payload && "blob" in payload && "kind" in payload) {
    const typed = payload as { kind: string; filename: string; contentType: string; blob: Blob };
    return <BlobPreview kind={typed.kind} filename={typed.filename} contentType={typed.contentType} blob={typed.blob} />;
  }

  return <PageState title="Preview unavailable" description="Preview data format is unsupported." variant="error" />;
}

function DemoPreview({ demo }: { readonly demo: DemoOutput }) {
  if (demo.kind === "none") {
    return (
      <div className="rounded-3xl border border-border/70 bg-card p-6">
        <div className="text-sm font-semibold text-foreground">Processed output</div>
        <div className="mt-2 text-sm text-muted-foreground">{demo.note ?? "No output."}</div>
      </div>
    );
  }

  if (demo.kind === "json") {
    return (
      <pre className="overflow-auto rounded-3xl border border-border/70 bg-muted px-5 py-4 text-xs text-muted-foreground">
        {demo.text ?? ""}
      </pre>
    );
  }

  if (demo.kind === "csv") {
    const rows = parseCsvPreview(demo.text ?? "");
    const header = rows[0] ?? [];
    const body = rows.slice(1);
    return <TablePreview header={header} rows={body} />;
  }

  return (
    <div className="rounded-3xl border border-border/70 bg-card p-6">
      <div className="text-sm font-semibold text-foreground">Preview unavailable</div>
      <div className="mt-2 text-sm text-muted-foreground">Demo preview for this type is not configured.</div>
    </div>
  );
}

function BlobPreview({ kind, filename, contentType, blob }: { readonly kind: string; readonly filename: string; readonly contentType: string; readonly blob: Blob }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (kind !== "pdf") {
      return;
    }
    const next = URL.createObjectURL(blob);
    setUrl(next);
    return () => {
      URL.revokeObjectURL(next);
    };
  }, [blob, kind]);

  if (kind === "pdf") {
    return url ? (
      <div className="overflow-hidden rounded-3xl border border-border/70 bg-card">
        <iframe title={filename} src={url} className="h-[70vh] w-full" />
      </div>
    ) : (
      <PageState title="Preparing PDF preview" variant="loading" />
    );
  }

  if (kind === "json" || contentType.includes("json")) {
    return <TextPreview blob={blob} tryFormat="json" />;
  }

  if (kind === "csv" || contentType.includes("csv")) {
    return <TextPreview blob={blob} tryFormat="csv" />;
  }

  return (
    <div className="rounded-3xl border border-border/70 bg-card p-6">
      <div className="text-sm font-semibold text-foreground">Preview unavailable</div>
      <div className="mt-2 text-sm text-muted-foreground">This file type can be downloaded, but isn’t previewed inline yet.</div>
    </div>
  );
}

function TextPreview({ blob, tryFormat }: { readonly blob: Blob; readonly tryFormat: "json" | "csv" }) {
  const [text, setText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    blob
      .text()
      .then((value) => {
        if (!cancelled) {
          setText(value);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to read preview.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [blob]);

  if (error) {
    return <PageState title="Preview unavailable" description={error} variant="error" />;
  }

  if (!text) {
    return <PageState title="Loading preview" variant="loading" />;
  }

  if (tryFormat === "csv") {
    const rows = parseCsvPreview(text);
    const header = rows[0] ?? [];
    const body = rows.slice(1);
    return <TablePreview header={header} rows={body} />;
  }

  if (tryFormat === "json") {
    let formatted = text;
    try {
      formatted = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      // ignore
    }
    return (
      <pre className="overflow-auto rounded-3xl border border-border/70 bg-muted px-5 py-4 text-xs text-muted-foreground">
        {formatted}
      </pre>
    );
  }

  return (
    <pre className="overflow-auto rounded-3xl border border-border/70 bg-muted px-5 py-4 text-xs text-muted-foreground">
      {text}
    </pre>
  );
}

function TablePreview({ header, rows }: { readonly header: readonly string[]; readonly rows: readonly string[][] }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-border/70 bg-card">
      <div className="overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-background">
            <tr>
              {header.map((cell, index) => (
                <th key={`${cell}-${index}`} className="whitespace-nowrap border-b border-border px-4 py-3 text-left text-xs font-semibold text-muted-foreground">
                  {cell || `Column ${index + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-card even:bg-background/60">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="whitespace-nowrap border-b border-border px-4 py-2 text-xs text-foreground">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DetailsPanel({ workspaceId, document, run }: { readonly workspaceId: string; readonly document: DocumentRecord; readonly run: RunResource | null }) {
  const tags = document.tags ?? [];
  const uploader = document.uploader?.name ?? document.uploader?.email ?? null;
  return (
    <div className="flex flex-col gap-5">
      <TagEditor workspaceId={workspaceId} document={document} />
      <div className="rounded-3xl border border-border/70 bg-card px-5 py-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Metadata</div>
        <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
          <DetailRow label="Status" value={statusBadge(document.status).label} />
          <DetailRow label="Size" value={formatBytes(document.byte_size)} />
          <DetailRow label="Uploaded" value={absoluteTime.format(new Date(document.created_at))} />
          <DetailRow label="Updated" value={absoluteTime.format(new Date(document.updated_at))} />
          <DetailRow label="Uploader" value={uploader ?? "—"} />
          <DetailRow label="Tags" value={tags.length ? `${tags.length}` : "0"} />
        </div>
      </div>

      <div className="rounded-3xl border border-border/70 bg-card px-5 py-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latest Run</div>
        <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
          <DetailRow label="Run status" value={run?.status ?? document.last_run?.status ?? "—"} />
          <DetailRow label="Output ready" value={run?.output?.ready ? "Yes" : "No"} />
          <DetailRow label="Output type" value={run?.output?.content_type ?? "—"} />
          <DetailRow label="Output size" value={run?.output?.size_bytes ? formatBytes(run.output.size_bytes) : "—"} />
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl bg-background px-4 py-3">
      <div className="text-xs font-semibold text-muted-foreground">{label}</div>
      <div className="text-right text-xs font-semibold text-foreground">{value}</div>
    </div>
  );
}

function TagEditor({ workspaceId, document }: { readonly workspaceId: string; readonly document: DocumentRecord }) {
  const queryClient = useQueryClient();
  const tags = document.tags ?? [];
  const [draft, setDraft] = useState("");
  const normalized = draft.trim();

  const catalogQuery = useQuery<TagCatalogPage>({
    queryKey: documentsV5Keys.tagCatalog(workspaceId, normalized.length >= 2 ? normalized : ""),
    queryFn: ({ signal }) =>
      fetchTagCatalog(
        workspaceId,
        {
          ...(normalized.length >= 2 ? { q: normalized } : {}),
          sort: "-count",
          page_size: 8,
        },
        signal,
      ),
    enabled: workspaceId.length > 0,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });

  const suggestions = useMemo(() => {
    const existing = new Set(tags.map((tag) => tag.toLowerCase()));
    return (catalogQuery.data?.items ?? []).filter((item) => !existing.has(item.tag.toLowerCase())).slice(0, 6);
  }, [catalogQuery.data?.items, tags]);

  const patchMutation = useMutation({
    mutationFn: (payload: { add?: readonly string[] | null; remove?: readonly string[] | null }) =>
      patchDocumentTags(workspaceId, document.id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(documentsV5Keys.detail(workspaceId, updated.id), updated);
      queryClient.invalidateQueries({ queryKey: documentsV5Keys.workspace(workspaceId) });
    },
  });

  const addTag = useCallback(
    (value: string) => {
      const next = value.trim();
      if (!next || patchMutation.isPending) {
        return;
      }
      if (tags.some((tag) => tag.toLowerCase() === next.toLowerCase())) {
        setDraft("");
        return;
      }
      patchMutation.mutate({ add: [next] });
      setDraft("");
    },
    [patchMutation, tags],
  );

  const removeTag = useCallback(
    (value: string) => {
      if (patchMutation.isPending) {
        return;
      }
      patchMutation.mutate({ remove: [value] });
    },
    [patchMutation],
  );

  return (
    <div className="rounded-3xl border border-border/70 bg-card px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tags</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {tags.length ? (
              tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="focus-ring inline-flex items-center gap-2 rounded-full bg-muted px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted"
                  title="Remove tag"
                >
                  <span>{tag}</span>
                  <span aria-hidden="true" className="text-muted-foreground">
                    ×
                  </span>
                </button>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">No tags yet.</span>
            )}
          </div>
        </div>
        <div className="shrink-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Add</div>
          <div className="mt-2 flex items-center gap-2">
            <label className="sr-only" htmlFor="documents-v5-tag-editor">
              Add a tag
            </label>
            <Input
              id="documents-v5-tag-editor"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === ",") {
                  event.preventDefault();
                  addTag(draft);
                }
              }}
              placeholder="New tag"
              className="h-9 w-44 rounded-full border-border bg-background px-4 text-xs focus-visible:ring-ring"
              disabled={patchMutation.isPending}
            />
            <Button variant="secondary" size="sm" disabled={!normalized} onClick={() => addTag(draft)}>
              Add
            </Button>
          </div>
        </div>
      </div>

      {suggestions.length > 0 ? (
        <div className="mt-4">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Suggestions</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((item) => (
              <button
                key={item.tag}
                type="button"
                onClick={() => addTag(item.tag)}
                className="focus-ring rounded-full bg-background px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-muted"
                disabled={patchMutation.isPending}
              >
                {item.tag}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {patchMutation.isError ? (
        <div className="mt-3 text-sm text-rose-700">{describeError(patchMutation.error)}</div>
      ) : null}
    </div>
  );
}
