import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type CSSProperties,
  type ReactNode,
} from "react";

import clsx from "clsx";

import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { Link } from "@app/nav/Link";
import { useNavigate } from "@app/nav/history";
import { useSearchParams } from "@app/nav/urlState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { client } from "@shared/api/client";
import { ApiError } from "@shared/api/errors";
import { useConfigurationsQuery } from "@shared/configurations";
import { useNotifications } from "@shared/notifications";
import { createRun, fetchRun, runQueryKeys, type RunResource, type RunStatus } from "@shared/runs/api";
import { createScopedStorage } from "@shared/storage";
import type { components, paths } from "@schema";
import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type DocumentPage = components["schemas"]["DocumentPage"];
type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];

type ListDocumentsQueryBase =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

type DocumentFilters = Partial<{
  q: string;
  status_in: string;
  last_run_from: string;
}>;

type DocumentsV4Query = ListDocumentsQueryBase & DocumentFilters;

type QueueFilter = "processing" | "completed" | "failed" | "waiting";

const RECENT_WINDOW_MINUTES = 60;
const STREAM_PAGE_SIZE = 25;
const STREAM_POLL_INTERVAL_MS = 5_000;
const SUMMARY_POLL_INTERVAL_MS = 10_000;
const OUTPUT_PREVIEW_MAX_BYTES = 200_000;
const OUTPUT_PREVIEW_MAX_CHARS = 8_000;
const EMPTY_DOCUMENTS: DocumentRecord[] = [];

const V4_THEME_STYLE = {
  "--v4-bg": "#eef2f7",
  "--v4-surface": "#f9fbfd",
  "--v4-surface-strong": "#ffffff",
  "--v4-surface-muted": "#eaf0f6",
  "--v4-ink": "#1b2a34",
  "--v4-muted": "#5b6b75",
  "--v4-line": "#d7e0e7",
  "--v4-accent": "#1c4f91",
  "--v4-accent-strong": "#163f73",
  "--v4-accent-soft": "#d8e5f4",
  "--v4-warning": "#c4752a",
  "--v4-success": "#1f7a54",
  "--v4-danger": "#b42318",
  "--v4-shadow": "0 30px 70px -55px rgba(15, 23, 42, 0.65)",
  background: "radial-gradient(120% 120% at 5% 0%, #fef6e7 0%, #eef2f7 45%, #e8edf3 100%)",
} as CSSProperties;

const QUEUE_FILTERS: Array<{ id: QueueFilter | null; label: string }> = [
  { id: null, label: "All" },
  { id: "failed", label: "Failed" },
  { id: "processing", label: "Processing" },
  { id: "completed", label: "Completed" },
  { id: "waiting", label: "Waiting" },
];

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const absoluteTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const documentsV4Keys = {
  root: (workspaceId: string) => ["documents-v4", workspaceId] as const,
  summary: (workspaceId: string) => [...documentsV4Keys.root(workspaceId), "summary"] as const,
  stream: (workspaceId: string, bucket: string, q: string) =>
    [...documentsV4Keys.root(workspaceId), "stream", bucket, { q }] as const,
  document: (workspaceId: string, documentId: string) =>
    [...documentsV4Keys.root(workspaceId), "document", documentId] as const,
  outputPreview: (workspaceId: string, runId: string) =>
    [...documentsV4Keys.root(workspaceId), "output-preview", runId] as const,
};

type DocumentsSummary = {
  readonly total: number;
  readonly processing: number;
  readonly completedRecently: number;
  readonly failed: number;
  readonly waiting: number;
  readonly refreshedAt: string;
};

export default function WorkspaceDocumentsV4Route() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();
  const [searchParams, setSearchParams] = useSearchParams();

  const q = searchParams.get("q")?.trim() ?? "";
  const queue = parseQueueFilter(searchParams.get("queue"));
  const selectedDocumentId = searchParams.get("doc") ?? "";

  const [isLive, setIsLive] = useState(true);
  const [searchValue, setSearchValue] = useState(q);

  useEffect(() => {
    setSearchValue(q);
  }, [q]);

  useEffect(() => {
    const normalized = searchValue.trim();
    if (normalized === q) {
      return;
    }

    const handle = window.setTimeout(() => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (normalized) {
          next.set("q", normalized);
        } else {
          next.delete("q");
        }
        return next;
      });
    }, 300);

    return () => window.clearTimeout(handle);
  }, [q, searchValue, setSearchParams]);

  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const activeConfigs = useMemo(
    () =>
      (configurationsQuery.data?.items ?? []).filter(
        (config): config is ConfigurationRecord => config.status === "active",
      ),
    [configurationsQuery.data?.items],
  );

  const runConfigStorage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspace.id}.documents_v4.run_config_id`),
    [workspace.id],
  );
  const [runConfigId, setRunConfigId] = useState<string | null>(() => runConfigStorage.get<string>() ?? null);

  useEffect(() => {
    runConfigStorage.set(runConfigId);
  }, [runConfigId, runConfigStorage]);

  useEffect(() => {
    if (activeConfigs.length === 0) {
      if (runConfigId !== null) {
        setRunConfigId(null);
      }
      return;
    }

    if (runConfigId && activeConfigs.some((config) => config.id === runConfigId)) {
      return;
    }

    setRunConfigId(activeConfigs[0]!.id);
  }, [activeConfigs, runConfigId]);

  const runConfig = useMemo(
    () => activeConfigs.find((config) => config.id === runConfigId) ?? null,
    [activeConfigs, runConfigId],
  );

  const summaryQuery = useQuery({
    queryKey: documentsV4Keys.summary(workspace.id),
    queryFn: ({ signal }) => fetchDocumentsSummary(workspace.id, { signal }),
    staleTime: 5_000,
    refetchInterval: isLive ? SUMMARY_POLL_INTERVAL_MS : false,
  });

  const wantsAllBuckets = queue === null;
  const wantsFailed = wantsAllBuckets || queue === "failed";
  const wantsProcessing = wantsAllBuckets || queue === "processing";
  const wantsCompleted = wantsAllBuckets || queue === "completed";
  const wantsWaiting = wantsAllBuckets || queue === "waiting";

  const failedDocsQuery = useQuery({
    queryKey: documentsV4Keys.stream(workspace.id, "failed", q),
    queryFn: ({ signal }) =>
      fetchDocuments(workspace.id, {
        sort: "-last_run_at",
        status_in: "failed",
        page_size: STREAM_PAGE_SIZE,
        q,
        signal,
      }),
    enabled: wantsFailed,
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
    staleTime: 3_000,
    placeholderData: (previous) => previous,
  });

  const processingDocsQuery = useQuery({
    queryKey: documentsV4Keys.stream(workspace.id, "processing", q),
    queryFn: ({ signal }) =>
      fetchDocuments(workspace.id, {
        sort: "-created_at",
        status_in: "processing",
        page_size: STREAM_PAGE_SIZE,
        q,
        signal,
      }),
    enabled: wantsProcessing,
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
    staleTime: 3_000,
    placeholderData: (previous) => previous,
  });

  const completedDocsQuery = useQuery({
    queryKey: documentsV4Keys.stream(workspace.id, "completed", q),
    queryFn: ({ signal }) =>
      fetchDocuments(workspace.id, {
        sort: "-last_run_at",
        status_in: "processed",
        last_run_from: new Date(Date.now() - RECENT_WINDOW_MINUTES * 60_000).toISOString(),
        page_size: STREAM_PAGE_SIZE,
        q,
        signal,
      }),
    enabled: wantsCompleted,
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
    staleTime: 3_000,
    placeholderData: (previous) => previous,
  });

  const waitingDocsQuery = useQuery({
    queryKey: documentsV4Keys.stream(workspace.id, "waiting", q),
    queryFn: ({ signal }) =>
      fetchDocuments(workspace.id, {
        sort: "-created_at",
        status_in: "uploaded",
        page_size: STREAM_PAGE_SIZE,
        q,
        signal,
      }),
    enabled: wantsWaiting,
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
    staleTime: 3_000,
    placeholderData: (previous) => previous,
  });

  const failedDocs = failedDocsQuery.data ?? EMPTY_DOCUMENTS;
  const processingDocs = processingDocsQuery.data ?? EMPTY_DOCUMENTS;
  const completedDocs = completedDocsQuery.data ?? EMPTY_DOCUMENTS;
  const waitingDocs = waitingDocsQuery.data ?? EMPTY_DOCUMENTS;

  const streamDocuments = useMemo(
    () => [...failedDocs, ...processingDocs, ...completedDocs, ...waitingDocs],
    [completedDocs, failedDocs, processingDocs, waitingDocs],
  );
  const pulseIds = usePulseIds(streamDocuments);

  const openQueue = useCallback(
    (nextQueue: QueueFilter | null) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (nextQueue) {
          next.set("queue", nextQueue);
        } else {
          next.delete("queue");
        }
        return next;
      });
    },
    [setSearchParams],
  );

  const openDocument = useCallback(
    (documentId: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("doc", documentId);
        return next;
      });
    },
    [setSearchParams],
  );

  const closeDocument = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("doc");
      return next;
    });
  }, [setSearchParams]);

  const showDetailPanel = Boolean(selectedDocumentId);

  useEffect(() => {
    if (!showDetailPanel) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeDocument();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeDocument, showDetailPanel]);

  const refreshNow = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: documentsV4Keys.root(workspace.id) });
    queryClient.invalidateQueries({ queryKey: ["run"] });
  }, [queryClient, workspace.id]);

  const runDocumentMutation = useMutation({
    mutationFn: async (payload: { documentId: string; configurationId: string }) =>
      createRun(workspace.id, {
        input_document_id: payload.documentId,
        configuration_id: payload.configurationId,
      }),
    onSuccess: (run, variables) => {
      notifyToast({
        title: "Run started",
        description: `Run ${run.id} is now queued.`,
        intent: "success",
        duration: 4_000,
        scope: "documents-v4",
      });
      openDocument(variables.documentId);
      queryClient.invalidateQueries({ queryKey: documentsV4Keys.root(workspace.id) });
    },
    onError: (error: unknown) => {
      notifyToast({
        title: "Unable to start run",
        description: describeError(error),
        intent: "danger",
        duration: 6_000,
        scope: "documents-v4",
      });
    },
  });

  const retryLastRunMutation = useMutation({
    mutationFn: async (payload: { documentId: string; lastRunId: string }) => {
      const run = await fetchRun(payload.lastRunId);
      return createRun(workspace.id, {
        input_document_id: payload.documentId,
        configuration_id: run.configuration_id,
      });
    },
    onSuccess: (run, variables) => {
      notifyToast({
        title: "Retry started",
        description: `Run ${run.id} is now queued.`,
        intent: "success",
        duration: 4_000,
        scope: "documents-v4",
      });
      openDocument(variables.documentId);
      queryClient.invalidateQueries({ queryKey: documentsV4Keys.root(workspace.id) });
    },
    onError: (error: unknown) => {
      notifyToast({
        title: "Unable to retry run",
        description: describeError(error),
        intent: "danger",
        duration: 6_000,
        scope: "documents-v4",
      });
    },
  });

  const downloadOutputMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data, response } = await client.GET("/api/v1/runs/{run_id}/output/download", {
        params: { path: { run_id: runId } },
        parseAs: "blob",
      });
      if (!data) {
        throw new Error("Output download unavailable.");
      }
      const filename = extractFilename(response.headers.get("content-disposition")) ?? `run-${runId}-output`;
      triggerBrowserDownload(data, filename);
    },
    onError: (error: unknown) => {
      notifyToast({
        title: "Unable to download output",
        description: describeError(error),
        intent: "danger",
        duration: 6_000,
        scope: "documents-v4",
      });
    },
  });

  const downloadOriginalMutation = useMutation({
    mutationFn: async (payload: { workspaceId: string; documentId: string }) => {
      const { data, response } = await client.GET(
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download",
        {
          params: { path: { workspace_id: payload.workspaceId, document_id: payload.documentId } },
          parseAs: "blob",
        },
      );
      if (!data) {
        throw new Error("Document download unavailable.");
      }
      const filename =
        extractFilename(response.headers.get("content-disposition")) ?? `document-${payload.documentId}`;
      triggerBrowserDownload(data, filename);
    },
    onError: (error: unknown) => {
      notifyToast({
        title: "Unable to download original",
        description: describeError(error),
        intent: "danger",
        duration: 6_000,
        scope: "documents-v4",
      });
    },
  });

  const downloadLogsMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data, response } = await client.GET("/api/v1/runs/{run_id}/events/download", {
        params: { path: { run_id: runId } },
        parseAs: "blob",
      });
      if (!data) {
        throw new Error("Run logs unavailable.");
      }
      const filename =
        extractFilename(response.headers.get("content-disposition")) ?? `run-${runId}-events.ndjson`;
      triggerBrowserDownload(data, filename);
    },
    onError: (error: unknown) => {
      notifyToast({
        title: "Unable to download logs",
        description: describeError(error),
        intent: "danger",
        duration: 6_000,
        scope: "documents-v4",
      });
    },
  });

  const metrics = useMemo(() => {
    const data = summaryQuery.data;
    return [
      {
        id: null as QueueFilter | null,
        label: "Total",
        value: data?.total ?? null,
        helper: "All documents in this workspace",
        tone: "neutral" as const,
      },
      {
        id: "processing" as const,
        label: "Processing",
        value: data?.processing ?? null,
        helper: "Actively running now",
        tone: "brand" as const,
      },
      {
        id: "completed" as const,
        label: "Completed",
        value: data?.completedRecently ?? null,
        helper: `Last ${RECENT_WINDOW_MINUTES} minutes`,
        tone: "success" as const,
      },
      {
        id: "failed" as const,
        label: "Failed",
        value: data?.failed ?? null,
        helper: "Needs your intervention",
        tone: "danger" as const,
      },
      {
        id: "waiting" as const,
        label: "Waiting",
        value: data?.waiting ?? null,
        helper: "Uploaded, not yet run",
        tone: "warning" as const,
      },
    ];
  }, [summaryQuery.data]);

  const queueCounts = useMemo(
    () => ({
      all: summaryQuery.data?.total ?? null,
      processing: summaryQuery.data?.processing ?? null,
      completed: summaryQuery.data?.completedRecently ?? null,
      failed: summaryQuery.data?.failed ?? null,
      waiting: summaryQuery.data?.waiting ?? null,
    }),
    [summaryQuery.data],
  );

  const healthTone = useMemo(() => {
    const failed = summaryQuery.data?.failed ?? 0;
    const processing = summaryQuery.data?.processing ?? 0;
    const waiting = summaryQuery.data?.waiting ?? 0;

    if (failed > 0) {
      return "attention" as const;
    }

    if (processing > 0 || waiting > 0) {
      return "working" as const;
    }

    return "ok" as const;
  }, [summaryQuery.data?.failed, summaryQuery.data?.processing, summaryQuery.data?.waiting]);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col text-[color:var(--v4-ink)]" style={V4_THEME_STYLE}>
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 right-[-10%] h-80 w-80 rounded-full bg-[color:var(--v4-accent-soft)] blur-3xl opacity-70" />
        <div className="absolute left-[-15%] top-24 h-72 w-72 rounded-full bg-[#f7e8d0] blur-3xl opacity-70" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(255,255,255,0.75),transparent_60%)]" />
      </div>

      <div className="relative flex min-h-0 flex-1 flex-col">
        <div className="docs-v4-animate border-b border-[color:var(--v4-line)] bg-[color:var(--v4-surface)]/85 backdrop-blur">
          <div className="px-6 py-6">
            <div className="flex flex-col gap-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-[color:var(--v4-muted)]">
                    <span className="inline-flex items-center gap-2 rounded-full border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-3 py-1 shadow-sm">
                      <span
                        className={clsx(
                          "h-2 w-2 rounded-full",
                          isLive ? "bg-emerald-500" : "bg-[color:var(--v4-line)]",
                        )}
                        aria-hidden
                      />
                      Command Center
                    </span>
                    <span>{isLive ? "Live stream" : "Paused"}</span>
                  </div>
                  <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--v4-ink)] sm:text-4xl">
                    Documents
                  </h1>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-[color:var(--v4-muted)]">
                    <HealthBadge tone={healthTone} />
                    {summaryQuery.data?.refreshedAt ? (
                      <span>Updated {formatRelativeTime(summaryQuery.data.refreshedAt)}</span>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <V4LinkButton to={`/workspaces/${workspace.id}/documents`} variant="secondary" size="sm">
                    Open documents
                  </V4LinkButton>
                  <V4LinkButton to={`/workspaces/${workspace.id}/documents`} variant="primary" size="sm">
                    Upload
                  </V4LinkButton>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-full border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-2 shadow-sm">
                  <SearchIcon className="h-4 w-4 text-[color:var(--v4-muted)]" />
                  <input
                    type="text"
                    value={searchValue}
                    onChange={(event) => setSearchValue(event.target.value)}
                    placeholder="Search the live stream"
                    className="w-full bg-transparent text-sm text-[color:var(--v4-ink)] placeholder:text-[color:var(--v4-muted)] focus:outline-none"
                    aria-label="Search documents"
                  />
                  {searchValue ? (
                    <button
                      type="button"
                      onClick={() => setSearchValue("")}
                      className="rounded-full px-2 py-1 text-xs font-semibold text-[color:var(--v4-muted)] transition hover:bg-[color:var(--v4-surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)]"
                    >
                      Clear
                    </button>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {QUEUE_FILTERS.map((filter) => {
                    const count = filter.id === null ? queueCounts.all : queueCounts[filter.id];
                    return (
                      <QueueChip
                        key={filter.label}
                        label={filter.label}
                        count={count}
                        active={queue === filter.id}
                        onClick={() => openQueue(queue === filter.id ? null : filter.id)}
                      />
                    );
                  })}
                </div>

                <div className="ml-auto flex flex-wrap items-center gap-2">
                  {activeConfigs.length > 0 ? (
                    <div className="flex items-center gap-2 rounded-full border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-3 py-1.5">
                      <span className="hidden text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)] sm:inline">
                        Run with
                      </span>
                      <Select
                        className="h-8 w-[min(16rem,55vw)] border-transparent bg-transparent text-sm font-semibold text-[color:var(--v4-ink)] shadow-none focus-visible:ring-[color:var(--v4-accent)]"
                        value={runConfigId ?? ""}
                        onChange={(event) => setRunConfigId(event.target.value)}
                        aria-label="Run configuration"
                      >
                        <option value="" disabled>
                          Choose configuration…
                        </option>
                        {activeConfigs.map((config) => (
                          <option key={config.id} value={config.id}>
                            {config.display_name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  ) : (
                    <V4LinkButton to={`/workspaces/${workspace.id}/config-builder`} variant="secondary" size="sm">
                      Activate a config
                    </V4LinkButton>
                  )}

                  <LiveToggle isLive={isLive} onToggle={() => setIsLive((prev) => !prev)} />
                  <V4Button variant="secondary" size="sm" isLoading={summaryQuery.isFetching} onClick={refreshNow}>
                    Refresh
                  </V4Button>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {metrics.map((metric) => (
                  <MetricCard
                    key={metric.label}
                    label={metric.label}
                    helper={metric.helper}
                    value={metric.value}
                    tone={metric.tone}
                    selected={metric.id === queue}
                    onClick={() => openQueue(metric.id === queue ? null : metric.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="relative flex min-h-0 flex-1 min-w-0">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              <WorkStream
                workspaceId={workspace.id}
                queue={queue}
                isRunMutating={runDocumentMutation.isPending || retryLastRunMutation.isPending}
                failed={failedDocsQuery}
                processing={processingDocsQuery}
                completed={completedDocsQuery}
                waiting={waitingDocsQuery}
                selectedDocumentId={selectedDocumentId}
                pulseIds={pulseIds}
                onSelectDocument={openDocument}
                onRetryLastRun={(documentId, runId) =>
                  retryLastRunMutation.mutate({ documentId, lastRunId: runId })
                }
                onRunDocument={(documentId) => {
                  if (!runConfigId) {
                    openDocument(documentId);
                    notifyToast({
                      title: "Choose a configuration",
                      description: activeConfigs.length
                        ? "Select an active configuration to run this document."
                        : "Activate a configuration to run uploaded documents.",
                      intent: "warning",
                      duration: 8_000,
                      scope: "documents-v4",
                      actions:
                        activeConfigs.length === 0
                          ? [
                              {
                                label: "Open Config Builder",
                                onSelect: () => navigate(`/workspaces/${workspace.id}/config-builder`),
                                variant: "secondary",
                              },
                            ]
                          : undefined,
                    });
                    return;
                  }
                  runDocumentMutation.mutate({ documentId, configurationId: runConfigId });
                }}
                onDownloadOutput={(runId) => downloadOutputMutation.mutate(runId)}
              />
            </div>
          </div>

          <aside className="hidden w-[min(26rem,34vw)] min-w-[22rem] flex-col border-l border-[color:var(--v4-line)] bg-[color:var(--v4-surface)]/70 backdrop-blur lg:flex">
            {showDetailPanel ? (
              <DocumentDetailPanel
                workspaceId={workspace.id}
                documentId={selectedDocumentId}
                isLive={isLive}
                runConfig={runConfig}
                onClose={closeDocument}
                onRun={(configurationId, documentId) =>
                  runDocumentMutation.mutate({ configurationId, documentId })
                }
                onRetry={(documentId, runId) =>
                  retryLastRunMutation.mutate({ documentId, lastRunId: runId })
                }
                onDownloadOutput={(runId) => downloadOutputMutation.mutate(runId)}
                onDownloadLogs={(runId) => downloadLogsMutation.mutate(runId)}
                onDownloadOriginal={(documentId) =>
                  downloadOriginalMutation.mutate({ workspaceId: workspace.id, documentId })
                }
                isMutating={
                  runDocumentMutation.isPending ||
                  retryLastRunMutation.isPending ||
                  downloadOutputMutation.isPending ||
                  downloadLogsMutation.isPending ||
                  downloadOriginalMutation.isPending
                }
              />
            ) : (
              <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center">
                <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] p-6 shadow-sm">
                  <p className="text-sm font-semibold text-[color:var(--v4-ink)]">Select a document</p>
                  <p className="mt-1 text-sm text-[color:var(--v4-muted)]">
                    Details stay inline so you can keep monitoring the stream.
                  </p>
                </div>
              </div>
            )}
          </aside>

          {showDetailPanel ? (
            <MobileDetailOverlay onClose={closeDocument}>
              <DocumentDetailPanel
                workspaceId={workspace.id}
                documentId={selectedDocumentId}
                isLive={isLive}
                runConfig={runConfig}
                onClose={closeDocument}
                onRun={(configurationId, documentId) => runDocumentMutation.mutate({ configurationId, documentId })}
                onRetry={(documentId, runId) => retryLastRunMutation.mutate({ documentId, lastRunId: runId })}
                onDownloadOutput={(runId) => downloadOutputMutation.mutate(runId)}
                onDownloadLogs={(runId) => downloadLogsMutation.mutate(runId)}
                onDownloadOriginal={(documentId) =>
                  downloadOriginalMutation.mutate({ workspaceId: workspace.id, documentId })
                }
                isMutating={
                  runDocumentMutation.isPending ||
                  retryLastRunMutation.isPending ||
                  downloadOutputMutation.isPending ||
                  downloadLogsMutation.isPending ||
                  downloadOriginalMutation.isPending
                }
              />
            </MobileDetailOverlay>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function WorkStream({
  workspaceId,
  queue,
  isRunMutating,
  failed,
  processing,
  completed,
  waiting,
  selectedDocumentId,
  pulseIds,
  onSelectDocument,
  onRetryLastRun,
  onRunDocument,
  onDownloadOutput,
}: {
  readonly workspaceId: string;
  readonly queue: QueueFilter | null;
  readonly isRunMutating: boolean;
  readonly failed: UseQueryResult<DocumentRecord[], unknown>;
  readonly processing: UseQueryResult<DocumentRecord[], unknown>;
  readonly completed: UseQueryResult<DocumentRecord[], unknown>;
  readonly waiting: UseQueryResult<DocumentRecord[], unknown>;
  readonly selectedDocumentId: string;
  readonly pulseIds: ReadonlySet<string>;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onRetryLastRun: (documentId: string, runId: string) => void;
  readonly onRunDocument: (documentId: string) => void;
  readonly onDownloadOutput: (runId: string) => void;
}) {
  const showAllBuckets = queue === null;

  const hasAny =
    (failed.data?.length ?? 0) +
      (processing.data?.length ?? 0) +
      (completed.data?.length ?? 0) +
      (waiting.data?.length ?? 0) >
    0;

  const hasLoading = Boolean(failed.isLoading || processing.isLoading || completed.isLoading || waiting.isLoading);
  const hasError = Boolean(failed.isError || processing.isError || completed.isError || waiting.isError);

  if (!hasAny && hasLoading) {
    return (
      <div className="flex min-h-[24rem] items-center justify-center">
        <PageState title="Loading live stream" variant="loading" />
      </div>
    );
  }

  if (!hasAny && hasError) {
    return (
      <div className="flex min-h-[24rem] items-center justify-center">
        <PageState title="Unable to load documents" description="Refresh to try again." variant="error" />
      </div>
    );
  }

  if (!hasAny) {
    return (
      <div className="flex min-h-[24rem] items-center justify-center">
        <PageState title="No documents yet" description="Upload a file to see activity appear here." variant="empty" />
      </div>
    );
  }

  return (
    <div className="docs-v4-animate flex flex-col gap-6">
      {showAllBuckets || queue === "failed" ? (
        <StreamSection
          title="Needs attention"
          description="Failures that need a decision."
          tone="danger"
          items={failed.data ?? []}
          emptyMessage="No failures right now."
          workspaceId={workspaceId}
          isRunMutating={isRunMutating}
          selectedDocumentId={selectedDocumentId}
          pulseIds={pulseIds}
          onSelectDocument={onSelectDocument}
          onPrimaryAction={(doc) => {
            if (doc.last_run?.run_id) {
              onRetryLastRun(doc.id, doc.last_run.run_id);
              return;
            }
            onSelectDocument(doc.id);
          }}
        />
      ) : null}

      {showAllBuckets || queue === "processing" ? (
        <StreamSection
          title="In progress"
          description="Documents actively processing."
          tone="brand"
          items={processing.data ?? []}
          emptyMessage="Nothing processing right now."
          workspaceId={workspaceId}
          isRunMutating={isRunMutating}
          selectedDocumentId={selectedDocumentId}
          pulseIds={pulseIds}
          onSelectDocument={onSelectDocument}
          onPrimaryAction={(doc) => onSelectDocument(doc.id)}
        />
      ) : null}

      {showAllBuckets || queue === "completed" ? (
        <StreamSection
          title={`Completed (last ${RECENT_WINDOW_MINUTES} min)`}
          description="Just finished outputs."
          tone="success"
          items={completed.data ?? []}
          emptyMessage="No recent completions."
          workspaceId={workspaceId}
          isRunMutating={isRunMutating}
          selectedDocumentId={selectedDocumentId}
          pulseIds={pulseIds}
          onSelectDocument={onSelectDocument}
          onPrimaryAction={(doc) => {
            if (doc.last_run?.run_id) {
              onDownloadOutput(doc.last_run.run_id);
              return;
            }
            onSelectDocument(doc.id);
          }}
        />
      ) : null}

      {showAllBuckets || queue === "waiting" ? (
        <StreamSection
          title="Waiting on you"
          description="Uploaded documents that haven't been run."
          tone="warning"
          items={waiting.data ?? []}
          emptyMessage="Nothing waiting right now."
          workspaceId={workspaceId}
          isRunMutating={isRunMutating}
          selectedDocumentId={selectedDocumentId}
          pulseIds={pulseIds}
          onSelectDocument={onSelectDocument}
          onPrimaryAction={(doc) => onRunDocument(doc.id)}
        />
      ) : null}
    </div>
  );
}

function StreamSection({
  title,
  description,
  tone,
  items,
  emptyMessage,
  workspaceId,
  isRunMutating,
  selectedDocumentId,
  pulseIds,
  onSelectDocument,
  onPrimaryAction,
}: {
  readonly title: string;
  readonly description: string;
  readonly tone: "brand" | "success" | "danger" | "warning";
  readonly items: readonly DocumentRecord[];
  readonly emptyMessage: string;
  readonly workspaceId: string;
  readonly isRunMutating: boolean;
  readonly selectedDocumentId: string;
  readonly pulseIds: ReadonlySet<string>;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onPrimaryAction: (document: DocumentRecord) => void;
}) {
  const visibleItems = items.slice(0, 10);
  const hiddenCount = Math.max(0, items.length - visibleItems.length);

  return (
    <section className="docs-v4-animate flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx("inline-flex h-2.5 w-2.5 rounded-full", toneDotClass(tone))} aria-hidden />
            <h2 className="text-sm font-semibold text-[color:var(--v4-ink)]">{title}</h2>
            <span className="text-xs font-medium text-[color:var(--v4-muted)]">{items.length}</span>
          </div>
          <p className="mt-1 text-sm text-[color:var(--v4-muted)]">{description}</p>
        </div>
        <V4LinkButton to={`/workspaces/${workspaceId}/documents`} variant="ghost" size="sm">
          History
        </V4LinkButton>
      </div>

      {visibleItems.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-6 text-sm text-[color:var(--v4-muted)]">
          {emptyMessage}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleItems.map((document, index) => (
            <StreamItem
              key={document.id}
              document={document}
              tone={tone}
              index={index}
              selected={document.id === selectedDocumentId}
              pulsing={pulseIds.has(document.id)}
              isRunMutating={isRunMutating}
              onSelect={() => onSelectDocument(document.id)}
              onPrimaryAction={() => onPrimaryAction(document)}
            />
          ))}
          {hiddenCount > 0 ? (
            <div className="text-sm text-[color:var(--v4-muted)]">
              And {hiddenCount} more.{" "}
              <V4LinkButton to={`/workspaces/${workspaceId}/documents`} variant="ghost" size="sm" className="ml-1">
                Open history
              </V4LinkButton>
              .
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function StreamItem({
  document,
  tone,
  index,
  selected,
  pulsing,
  isRunMutating,
  onSelect,
  onPrimaryAction,
}: {
  readonly document: DocumentRecord;
  readonly tone: "brand" | "success" | "danger" | "warning";
  readonly index: number;
  readonly selected: boolean;
  readonly pulsing: boolean;
  readonly isRunMutating: boolean;
  readonly onSelect: () => void;
  readonly onPrimaryAction: () => void;
}) {
  const statusDetail = describeDocument(document);
  const timestamp = pickDocumentTimestamp(document);
  const uploaderName = document.uploader?.name ?? document.uploader?.email ?? null;

  const primaryActionLabel = useMemo(() => {
    switch (tone) {
      case "danger":
        return document.last_run?.run_id ? "Retry" : "Details";
      case "success":
        return document.last_run?.run_id ? "Download" : "Details";
      case "warning":
        return "Run";
      default:
        return "Details";
    }
  }, [document.last_run?.run_id, tone]);

  const actionVariant: V4ButtonVariant = tone === "danger" ? "danger" : tone === "success" ? "primary" : "secondary";
  const disablePrimaryAction =
    isRunMutating && (tone === "warning" || (tone === "danger" && Boolean(document.last_run?.run_id)));

  return (
    <div
      style={{ "--delay": `${140 + index * 60}ms` } as CSSProperties}
      className={clsx(
        "docs-v4-animate group relative flex flex-wrap items-start justify-between gap-4 rounded-2xl border bg-[color:var(--v4-surface-strong)] px-4 py-3 shadow-sm transition",
        selected
          ? "border-[color:var(--v4-accent)]/60 ring-2 ring-[color:var(--v4-accent-soft)]"
          : "border-[color:var(--v4-line)] hover:border-[color:var(--v4-accent)]/40",
      )}
    >
      <span className={clsx("absolute left-0 top-0 h-full w-1.5 rounded-r-full", toneStripeClass(tone))} aria-hidden />
      <button
        type="button"
        className="flex min-w-0 flex-1 items-start gap-3 pl-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v4-bg)]"
        onClick={onSelect}
        aria-pressed={selected}
      >
        <StatusIcon status={document.status} tone={tone} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="truncate text-sm font-semibold text-[color:var(--v4-ink)]">{document.name}</div>
                <StatusPill status={document.status} />
                {pulsing ? (
                  <span className="rounded-full bg-[color:var(--v4-accent-soft)] px-2 py-0.5 text-[0.6rem] font-semibold text-[color:var(--v4-accent)]">
                    Updated
                  </span>
                ) : null}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[color:var(--v4-muted)]">
                <span>{formatRelativeTime(timestamp)}</span>
                {uploaderName ? (
                  <>
                    <span aria-hidden="true">•</span>
                    <span>{uploaderName}</span>
                  </>
                ) : null}
              </div>
            </div>
          </div>
          {statusDetail ? <div className="mt-2 line-clamp-2 text-sm text-[color:var(--v4-muted)]">{statusDetail}</div> : null}
        </div>
      </button>

      <div className="flex shrink-0 items-start">
        <V4Button
          variant={actionVariant}
          size="sm"
          className="whitespace-nowrap"
          disabled={disablePrimaryAction}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onPrimaryAction();
          }}
        >
          {primaryActionLabel}
        </V4Button>
      </div>
    </div>
  );
}

function DocumentDetailPanel({
  workspaceId,
  documentId,
  isLive,
  runConfig,
  onClose,
  onRun,
  onRetry,
  onDownloadOutput,
  onDownloadLogs,
  onDownloadOriginal,
  isMutating,
}: {
  readonly workspaceId: string;
  readonly documentId: string;
  readonly isLive: boolean;
  readonly runConfig: ConfigurationRecord | null;
  readonly onClose: () => void;
  readonly onRun: (configurationId: string, documentId: string) => void;
  readonly onRetry: (documentId: string, runId: string) => void;
  readonly onDownloadOutput: (runId: string) => void;
  readonly onDownloadLogs: (runId: string) => void;
  readonly onDownloadOriginal: (documentId: string) => void;
  readonly isMutating: boolean;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const docQuery = useQuery({
    queryKey: documentsV4Keys.document(workspaceId, documentId),
    queryFn: ({ signal }) => fetchDocument(workspaceId, documentId, signal),
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
    staleTime: 2_000,
  });

  const document = docQuery.data ?? null;
  const runId = document?.last_run?.run_id ?? null;

  const runQuery = useQuery({
    queryKey: runId ? runQueryKeys.detail(runId) : ["run", "none"],
    queryFn: ({ signal }) => (runId ? fetchRun(runId, signal) : Promise.resolve(null)),
    enabled: Boolean(runId),
    staleTime: 2_000,
    refetchInterval: isLive ? STREAM_POLL_INTERVAL_MS : false,
  });

  const run = (runQuery.data ?? null) as RunResource | null;
  const output = run?.output ?? null;
  const outputReady = Boolean(output?.ready && output?.has_output);
  const previewableOutput = Boolean(
    outputReady &&
      typeof output?.size_bytes === "number" &&
      output.size_bytes > 0 &&
      output.size_bytes <= OUTPUT_PREVIEW_MAX_BYTES &&
      isPreviewableOutputContentType(output.content_type),
  );

  const outputPreviewQuery = useQuery({
    queryKey: runId
      ? documentsV4Keys.outputPreview(workspaceId, runId)
      : ["documents-v4", workspaceId, "output-preview", "none"],
    queryFn: ({ signal }) => (runId ? fetchRunOutputPreview(runId, output?.content_type ?? null, signal) : Promise.resolve("")),
    enabled: Boolean(runId && previewableOutput),
    staleTime: 60_000,
  });

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, [documentId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-[color:var(--v4-line)] px-6 py-4">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">Document</div>
          <div className="mt-1 truncate text-base font-semibold text-[color:var(--v4-ink)]">
            {document?.name ?? "Loading…"}
          </div>
        </div>
        <button
          ref={closeButtonRef}
          type="button"
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] text-[color:var(--v4-muted)] transition hover:bg-[color:var(--v4-surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)]"
          onClick={onClose}
          aria-label="Close detail panel"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {docQuery.isLoading ? (
          <PageState title="Loading details" variant="loading" />
        ) : docQuery.isError ? (
          <PageState title="Unable to load document" description="This document may have been removed." variant="error" />
        ) : !document ? null : (
          <div className="flex flex-col gap-6">
            <DetailSection title="What happened">
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill status={document.status} />
                  <span className="text-sm text-[color:var(--v4-muted)]">Updated {formatRelativeTime(document.updated_at)}</span>
                </div>
                <div className="grid gap-2 rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-3 text-sm text-[color:var(--v4-muted)]">
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="text-[color:var(--v4-muted)]">Uploaded</span>
                    <span className="font-medium text-[color:var(--v4-ink)]">
                      {absoluteTimeFormatter.format(new Date(document.created_at))}
                    </span>
                  </div>
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="text-[color:var(--v4-muted)]">Last run</span>
                    <span className="font-medium text-[color:var(--v4-ink)]">
                      {document.last_run_at ? absoluteTimeFormatter.format(new Date(document.last_run_at)) : "No runs yet"}
                    </span>
                  </div>
                  {document.uploader?.name || document.uploader?.email ? (
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="text-[color:var(--v4-muted)]">Uploaded by</span>
                      <span className="font-medium text-[color:var(--v4-ink)]">
                        {document.uploader.name ?? document.uploader.email}
                      </span>
                    </div>
                  ) : null}
                </div>
                {document.last_run?.message ? (
                  <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-3 text-sm text-[color:var(--v4-muted)]">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">Latest message</div>
                    <div className="mt-1">{document.last_run.message}</div>
                  </div>
                ) : null}
                {runId ? (
                  <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">Latest run</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <RunStatusPill status={run?.status ?? document.last_run?.status ?? "queued"} />
                          <span className="text-sm text-[color:var(--v4-muted)]">
                            {formatRelativeTime(
                              document.last_run?.run_at ?? run?.completed_at ?? run?.started_at ?? run?.created_at,
                            )}
                          </span>
                        </div>
                        {run?.status === "failed" ? (
                          <div className="mt-3 rounded-xl border border-rose-100 bg-rose-50/60 px-3 py-2 text-sm text-rose-800">
                            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-700">Failure</div>
                            <div className="mt-1">{describeRunFailure(run)}</div>
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col gap-2">
                        <V4Button variant="secondary" size="sm" disabled={!runId || isMutating} onClick={() => onDownloadLogs(runId)}>
                          Download logs
                        </V4Button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </DetailSection>

            <DetailSection title="What ADE produced">
              <div className="flex flex-col gap-3">
                {runId ? (
                  <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">Latest run</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <RunStatusPill status={document.last_run?.status ?? run?.status ?? "queued"} />
                          <span className="text-sm text-[color:var(--v4-muted)]">
                            {document.last_run?.run_at ? formatRelativeTime(document.last_run.run_at) : null}
                          </span>
                        </div>
                        {output?.filename ? (
                          <div className="mt-3">
                            <div className="text-sm font-semibold text-[color:var(--v4-ink)]">{output.filename}</div>
                            <div className="mt-1 text-sm text-[color:var(--v4-muted)]">
                              {output.size_bytes ? formatBytes(output.size_bytes) : "Output details available"}
                            </div>
                          </div>
                        ) : (
                          <div className="mt-3 text-sm text-[color:var(--v4-muted)]">
                            {outputReady ? "Output is ready." : "Output metadata will appear once the run starts producing files."}
                          </div>
                        )}

                        {outputReady ? (
                          <div className="mt-4 rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-muted)] px-4 py-3">
                            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">Preview</div>
                            {previewableOutput ? (
                              outputPreviewQuery.isLoading ? (
                                <div className="mt-2 text-sm text-[color:var(--v4-muted)]">Loading preview…</div>
                              ) : outputPreviewQuery.isError ? (
                                <div className="mt-2 text-sm text-[color:var(--v4-muted)]">
                                  Preview unavailable. Download the output to inspect it.
                                </div>
                              ) : (
                                <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-xl bg-[color:var(--v4-surface-strong)] px-3 py-2 text-xs text-[color:var(--v4-ink)] shadow-sm">
                                  {outputPreviewQuery.data}
                                </pre>
                              )
                            ) : (
                              <div className="mt-2 text-sm text-[color:var(--v4-muted)]">
                                Preview is available for small text outputs (≤ {formatBytes(OUTPUT_PREVIEW_MAX_BYTES)}).
                              </div>
                            )}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col gap-2">
                        <V4Button
                          variant="primary"
                          size="sm"
                          disabled={!runId || !outputReady || isMutating}
                          onClick={() => onDownloadOutput(runId)}
                        >
                          {outputReady ? "Download output" : "Output pending"}
                        </V4Button>
                        <V4Button
                          variant="secondary"
                          size="sm"
                          disabled={isMutating}
                          onClick={() => onDownloadOriginal(document.id)}
                        >
                          Download original
                        </V4Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-6 text-sm text-[color:var(--v4-muted)]">
                    No run output yet.
                  </div>
                )}
              </div>
            </DetailSection>

            <DetailSection title="What you can do next">
              <div className="flex flex-col gap-3">
                {document.status === "failed" && document.last_run?.run_id ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <V4Button
                      variant="danger"
                      size="md"
                      disabled={isMutating}
                      onClick={() => onRetry(document.id, document.last_run!.run_id!)}
                    >
                      Retry last run
                    </V4Button>
                    <V4Button
                      variant="secondary"
                      size="md"
                      disabled={isMutating}
                      onClick={() => onDownloadLogs(document.last_run!.run_id!)}
                    >
                      Download logs
                    </V4Button>
                  </div>
                ) : null}

                {document.status === "uploaded" ? (
                  runConfig ? (
                    <V4Button
                      variant="primary"
                      size="md"
                      disabled={isMutating}
                      onClick={() => onRun(runConfig.id, document.id)}
                    >
                      Run with {runConfig.display_name}
                    </V4Button>
                  ) : (
                    <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-3 text-sm text-[color:var(--v4-muted)]">
                      <div className="font-semibold text-[color:var(--v4-ink)]">Choose a configuration</div>
                      <div className="mt-1">Activate a configuration to run uploaded documents from this screen.</div>
                      <div className="mt-3">
                        <V4LinkButton to={`/workspaces/${workspaceId}/config-builder`} variant="ghost" size="sm">
                          Open Config Builder
                        </V4LinkButton>
                      </div>
                    </div>
                  )
                ) : null}

                <div className="rounded-2xl border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-4 py-3 text-sm text-[color:var(--v4-muted)]">
                  <div className="font-semibold text-[color:var(--v4-ink)]">Open full document manager</div>
                  <div className="mt-1">Tag, archive, and run batches in the classic documents page.</div>
                  <div className="mt-3">
                    <V4LinkButton to={`/workspaces/${workspaceId}/documents`} variant="ghost" size="sm">
                      Open Documents
                    </V4LinkButton>
                  </div>
                </div>
              </div>
            </DetailSection>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailSection({ title, children }: { readonly title: string; readonly children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-[color:var(--v4-ink)]">{title}</h3>
      {children}
    </section>
  );
}

function MobileDetailOverlay({ children, onClose }: { readonly children: ReactNode; readonly onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex lg:hidden" role="dialog" aria-modal="true">
      <button type="button" className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} aria-label="Close detail panel" />
      <div className="relative ml-auto flex h-full w-[min(26rem,100%)] max-w-md flex-col border-l border-[color:var(--v4-line)] bg-[color:var(--v4-surface)] shadow-[0_45px_90px_-50px_rgba(15,23,42,0.85)]">
        {children}
      </div>
    </div>
  );
}

type V4ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type V4ButtonProps = ComponentProps<typeof Button> & { readonly variant?: V4ButtonVariant };

function V4Button({ variant = "secondary", className, ...props }: V4ButtonProps) {
  const baseVariant = variant === "primary" ? "secondary" : variant;
  return (
    <Button
      {...props}
      variant={baseVariant}
      className={clsx(
        "rounded-full shadow-sm focus-visible:ring-offset-[color:var(--v4-bg)]",
        variant === "primary" &&
          "border-transparent bg-[color:var(--v4-accent)] text-white hover:bg-[color:var(--v4-accent-strong)] focus-visible:ring-[color:var(--v4-accent)]",
        variant === "secondary" &&
          "border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] text-[color:var(--v4-ink)] hover:bg-[color:var(--v4-surface-muted)] focus-visible:ring-[color:var(--v4-accent)]",
        variant === "ghost" &&
          "text-[color:var(--v4-ink)] hover:bg-[color:var(--v4-surface-muted)] focus-visible:ring-[color:var(--v4-accent)]",
        variant === "danger" && "focus-visible:ring-rose-400",
        className,
      )}
    />
  );
}

interface V4LinkButtonProps {
  readonly to: string;
  readonly variant?: V4ButtonVariant;
  readonly size?: "sm" | "md";
  readonly className?: string;
  readonly children: ReactNode;
}

function V4LinkButton({ to, variant = "secondary", size = "md", className, children }: V4LinkButtonProps) {
  const sizeClass = size === "sm" ? "h-9 px-3 text-xs" : "h-10 px-4 text-sm";
  return (
    <Link
      to={to}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v4-bg)]",
        sizeClass,
        variant === "primary" && "bg-[color:var(--v4-accent)] text-white hover:bg-[color:var(--v4-accent-strong)]",
        variant === "secondary" &&
          "border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] text-[color:var(--v4-ink)] hover:bg-[color:var(--v4-surface-muted)]",
        variant === "ghost" && "text-[color:var(--v4-ink)] hover:bg-[color:var(--v4-surface-muted)]",
        variant === "danger" && "bg-rose-600 text-white hover:bg-rose-700",
        className,
      )}
    >
      {children}
    </Link>
  );
}

function QueueChip({
  label,
  count,
  active,
  onClick,
}: {
  readonly label: string;
  readonly count: number | null;
  readonly active: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v4-bg)]",
        active
          ? "border-transparent bg-[color:var(--v4-accent-soft)] text-[color:var(--v4-ink)] shadow-sm"
          : "border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] text-[color:var(--v4-muted)] hover:bg-[color:var(--v4-surface-muted)]",
      )}
    >
      {label}
      {count != null ? (
        <span className="rounded-full bg-[color:var(--v4-surface)] px-2 py-0.5 text-[0.6rem] font-semibold text-[color:var(--v4-muted)]">
          {formatCount(count)}
        </span>
      ) : null}
    </button>
  );
}

function LiveToggle({ isLive, onToggle }: { readonly isLive: boolean; readonly onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={isLive}
      className={clsx(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v4-bg)]",
        isLive
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] text-[color:var(--v4-muted)]",
      )}
    >
      <span className={clsx("h-2 w-2 rounded-full", isLive ? "bg-emerald-500 animate-pulse" : "bg-[color:var(--v4-line)]")} aria-hidden />
      {isLive ? "Live" : "Paused"}
    </button>
  );
}

function HealthBadge({ tone }: { readonly tone: "ok" | "attention" | "working" }) {
  const label = tone === "ok" ? "All clear" : tone === "attention" ? "Needs attention" : "Working";
  const dot = tone === "ok" ? "bg-emerald-500" : tone === "attention" ? "bg-rose-500" : "bg-sky-500";

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] px-2 py-0.5 text-xs font-medium text-[color:var(--v4-muted)]">
      <span className={clsx("h-2 w-2 rounded-full", dot)} aria-hidden />
      {label}
    </span>
  );
}

function MetricCard({
  label,
  helper,
  value,
  tone,
  selected,
  onClick,
}: {
  readonly label: string;
  readonly helper: string;
  readonly value: number | null;
  readonly tone: "neutral" | "brand" | "success" | "danger" | "warning";
  readonly selected: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={clsx(
        "flex w-full flex-col rounded-2xl border px-4 py-3 text-left shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--v4-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--v4-bg)]",
        selected
          ? "border-[color:var(--v4-accent)]/50 bg-[color:var(--v4-accent-soft)]/60"
          : "border-[color:var(--v4-line)] bg-[color:var(--v4-surface-strong)] hover:border-[color:var(--v4-accent)]/30 hover:bg-[color:var(--v4-surface-muted)]",
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--v4-muted)]">{label}</div>
          <div className="mt-1 text-2xl font-semibold text-[color:var(--v4-ink)] tabular-nums">
            {value == null ? "—" : formatCount(value)}
          </div>
        </div>
        <span className={clsx("mt-1 inline-flex h-2.5 w-2.5 rounded-full", toneDotClass(tone))} aria-hidden />
      </div>
      <div className="mt-2 text-sm text-[color:var(--v4-muted)]">{helper}</div>
    </button>
  );
}

function StatusPill({ status }: { readonly status: DocumentStatus }) {
  const label = formatDocumentStatus(status);
  return <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", statusPillClass(status))}>{label}</span>;
}

function RunStatusPill({ status }: { readonly status: RunStatus }) {
  return <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", runStatusPillClass(status))}>{formatRunStatus(status)}</span>;
}

function StatusIcon({ status, tone }: { readonly status: DocumentStatus; readonly tone: string }) {
  const ring = toneIconRingClass(tone);
  const glyph = statusIconGlyph(status);
  return <span className={clsx("mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-2xl border bg-[color:var(--v4-surface-strong)]", ring)}>{glyph}</span>;
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
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

function statusIconGlyph(status: DocumentStatus) {
  switch (status) {
    case "processed":
      return <CheckIcon className="h-4 w-4 text-emerald-700" />;
    case "failed":
      return <AlertIcon className="h-4 w-4 text-rose-700" />;
    case "processing":
      return <SpinnerIcon className="h-4 w-4 text-sky-700" />;
    case "uploaded":
      return <ClockIcon className="h-4 w-4 text-amber-700" />;
    default:
      return <DotIcon className="h-4 w-4 text-[color:var(--v4-muted)]" />;
  }
}

function SpinnerIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={clsx("animate-spin", className)} viewBox="0 0 20 20" fill="none">
      <circle className="opacity-30" cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2.2" />
      <path d="M17 10a7 7 0 0 0-7-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M5 10.5 8.5 14 15 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AlertIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M10 6v5" strokeLinecap="round" />
      <path d="M10 14.5h.01" strokeLinecap="round" />
      <path d="M10 2 2 18h16L10 2Z" strokeLinejoin="round" />
    </svg>
  );
}

function ClockIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M10 6v4l2.5 2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z" />
    </svg>
  );
}

function DotIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <circle cx="10" cy="10" r="3" />
    </svg>
  );
}

function parseQueueFilter(value: string | null): QueueFilter | null {
  switch (value) {
    case "processing":
    case "completed":
    case "failed":
    case "waiting":
      return value;
    default:
      return null;
  }
}

function toneDotClass(tone: "neutral" | "brand" | "success" | "danger" | "warning") {
  switch (tone) {
    case "brand":
      return "bg-sky-500";
    case "success":
      return "bg-emerald-500";
    case "danger":
      return "bg-rose-500";
    case "warning":
      return "bg-amber-500";
    default:
      return "bg-[color:var(--v4-line)]";
  }
}

function toneStripeClass(tone: "brand" | "success" | "danger" | "warning") {
  switch (tone) {
    case "brand":
      return "bg-sky-500/70";
    case "success":
      return "bg-emerald-500/70";
    case "danger":
      return "bg-rose-500/70";
    case "warning":
      return "bg-amber-500/70";
    default:
      return "bg-[color:var(--v4-line)]/70";
  }
}

function toneIconRingClass(tone: string) {
  switch (tone) {
    case "brand":
      return "border-sky-200 bg-sky-50/40";
    case "success":
      return "border-emerald-200 bg-emerald-50/40";
    case "danger":
      return "border-rose-200 bg-rose-50/40";
    case "warning":
      return "border-amber-200 bg-amber-50/40";
    default:
      return "border-[color:var(--v4-line)] bg-[color:var(--v4-surface-muted)]";
  }
}

function statusPillClass(status: DocumentStatus) {
  switch (status) {
    case "processed":
      return "bg-emerald-100 text-emerald-700";
    case "failed":
      return "bg-rose-100 text-rose-700";
    case "processing":
      return "bg-sky-100 text-sky-700";
    case "uploaded":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-slate-200 text-slate-700";
  }
}

function runStatusPillClass(status: RunStatus) {
  switch (status) {
    case "succeeded":
      return "bg-emerald-100 text-emerald-700";
    case "failed":
      return "bg-rose-100 text-rose-700";
    case "running":
      return "bg-sky-100 text-sky-700";
    case "queued":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-slate-200 text-slate-700";
  }
}

function formatDocumentStatus(status: DocumentStatus) {
  switch (status) {
    case "uploaded":
      return "Uploaded";
    case "processing":
      return "Processing";
    case "processed":
      return "Processed";
    case "failed":
      return "Failed";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

function formatRunStatus(status: RunStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function pickDocumentTimestamp(document: DocumentRecord) {
  const candidates = [
    document.last_run?.run_at,
    document.last_run_at,
    document.updated_at,
    document.created_at,
  ].filter((value): value is string => typeof value === "string" && value.length > 0);

  return candidates[0] ?? document.created_at;
}

function describeDocument(document: DocumentRecord) {
  const message = document.last_run?.message?.trim();
  if (message) {
    return message;
  }
  switch (document.status) {
    case "uploaded":
      return "Ready to run.";
    case "processing":
      return "Processing…";
    case "processed":
      return "Output is ready.";
    case "failed":
      return "Run failed. Review logs or retry.";
    default:
      return null;
  }
}

function describeRunFailure(run: RunResource) {
  const message = run.failure_message?.trim();
  if (message) {
    return message;
  }
  if (run.failure_stage && run.failure_code) {
    return `${run.failure_stage}: ${run.failure_code}`;
  }
  if (run.failure_stage) {
    return run.failure_stage;
  }
  if (run.failure_code) {
    return run.failure_code;
  }
  return "Run failed. Download logs for details.";
}

function formatRelativeTime(timestamp: string | null | undefined) {
  if (!timestamp) {
    return "Unknown time";
  }

  const now = Date.now();
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) {
    return "Unknown time";
  }

  const diffSeconds = Math.round((then - now) / 1_000);
  const abs = Math.abs(diffSeconds);

  if (abs < 45) {
    return relativeTimeFormatter.format(diffSeconds, "second");
  }
  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 45) {
    return relativeTimeFormatter.format(diffMinutes, "minute");
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 36) {
    return relativeTimeFormatter.format(diffHours, "hour");
  }
  const diffDays = Math.round(diffHours / 24);
  return relativeTimeFormatter.format(diffDays, "day");
}

function formatCount(value: number) {
  return value.toLocaleString();
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"] as const;
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const rounded = index === 0 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${units[index]}`;
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

async function fetchDocuments(
  workspaceId: string,
  options: {
    readonly sort?: string;
    readonly page_size?: number;
    readonly include_total?: boolean;
    readonly q?: string;
    readonly status_in?: string;
    readonly last_run_from?: string;
    readonly signal?: AbortSignal;
  },
) {
  const query: DocumentsV4Query = {
    sort: options.sort,
    page: 1,
    page_size: options.page_size ?? STREAM_PAGE_SIZE,
    include_total: options.include_total ?? false,
    q: options.q,
    status_in: options.status_in,
    last_run_from: options.last_run_from,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal: options.signal,
  });

  if (!data) {
    return EMPTY_DOCUMENTS;
  }

  const page = data as DocumentPage;
  return page.items ?? EMPTY_DOCUMENTS;
}

async function fetchDocument(workspaceId: string, documentId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    signal,
  });

  if (!data) {
    throw new Error("Document not found.");
  }

  return data as DocumentRecord;
}

async function fetchDocumentsSummary(workspaceId: string, options?: { readonly signal?: AbortSignal }): Promise<DocumentsSummary> {
  const now = new Date();
  const lastRunFrom = new Date(now.getTime() - RECENT_WINDOW_MINUTES * 60_000).toISOString();

  const [all, processing, completed, failed, waiting] = await Promise.all([
    fetchDocumentsCount(workspaceId, {}, options?.signal),
    fetchDocumentsCount(workspaceId, { status_in: "processing" }, options?.signal),
    fetchDocumentsCount(workspaceId, { status_in: "processed", last_run_from: lastRunFrom }, options?.signal),
    fetchDocumentsCount(workspaceId, { status_in: "failed" }, options?.signal),
    fetchDocumentsCount(workspaceId, { status_in: "uploaded" }, options?.signal),
  ]);

  return {
    total: all,
    processing,
    completedRecently: completed,
    failed,
    waiting,
    refreshedAt: now.toISOString(),
  };
}

async function fetchDocumentsCount(
  workspaceId: string,
  options: { readonly status_in?: string; readonly last_run_from?: string },
  signal?: AbortSignal,
) {
  const query: DocumentsV4Query = {
    page: 1,
    page_size: 1,
    include_total: true,
    status_in: options.status_in,
    last_run_from: options.last_run_from,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    return 0;
  }

  const page = data as DocumentPage;
  return page.total ?? 0;
}

function isPreviewableOutputContentType(contentType: string | null | undefined) {
  if (!contentType) {
    return false;
  }
  return (
    contentType.startsWith("text/") ||
    contentType.includes("json") ||
    contentType.includes("xml") ||
    contentType.includes("yaml")
  );
}

async function fetchRunOutputPreview(runId: string, contentType: string | null, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/runs/{run_id}/output/download", {
    params: { path: { run_id: runId } },
    parseAs: "blob",
    signal,
  });

  if (!data) {
    throw new Error("Preview unavailable.");
  }

  const text = await data.text();
  const trimmed = text.length > OUTPUT_PREVIEW_MAX_CHARS ? `${text.slice(0, OUTPUT_PREVIEW_MAX_CHARS)}…` : text;

  if (contentType && contentType.includes("json")) {
    try {
      const parsed = JSON.parse(trimmed);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return trimmed;
    }
  }

  return trimmed;
}

function describeError(error: unknown) {
  if (error instanceof ApiError) {
    const maybeNested = (error.problem as unknown as { error?: { message?: string } } | undefined)?.error?.message;
    return maybeNested ?? error.problem?.detail ?? error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong.";
}

function usePulseIds(documents: readonly DocumentRecord[]) {
  const [pulseIds, setPulseIds] = useState<ReadonlySet<string>>(() => new Set());
  const previousMap = useRef<Map<string, string>>(new Map());
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    const nextMap = new Map<string, string>();
    const nextPulse = new Set<string>();

    for (const doc of documents) {
      nextMap.set(doc.id, doc.updated_at);
      const previous = previousMap.current.get(doc.id);
      if (previous && previous !== doc.updated_at) {
        nextPulse.add(doc.id);
      }
    }

    previousMap.current = nextMap;
    if (nextPulse.size === 0) {
      return;
    }

    setPulseIds(nextPulse);
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => setPulseIds(new Set()), 2_500);

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, [documents]);

  return pulseIds;
}
