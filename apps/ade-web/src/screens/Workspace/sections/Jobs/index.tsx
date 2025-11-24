import { useMemo, useState } from "react";
import clsx from "clsx";

import { useInfiniteQuery } from "@tanstack/react-query";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { fetchWorkspaceJobs, workspaceJobsKeys, type JobRecord, type JobStatus } from "@shared/jobs";

import { Button } from "@ui/Button";
import { Select } from "@ui/Select";
import { PageState } from "@ui/PageState";

const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  succeeded: "Succeeded",
  failed: "Failed",
  running: "Running",
  queued: "Queued",
  cancelled: "Cancelled",
};

const JOB_STATUS_CLASSES: Record<JobStatus, string> = {
  succeeded: "bg-success-100 text-success-700",
  failed: "bg-rose-100 text-rose-700",
  running: "bg-brand-50 text-brand-700",
  queued: "bg-slate-100 text-slate-700",
  cancelled: "bg-slate-200 text-slate-700",
};

const TIME_RANGE_OPTIONS = [
  { value: "24h", label: "Last 24 hours", durationMs: 24 * 60 * 60 * 1000 },
  { value: "7d", label: "Last 7 days", durationMs: 7 * 24 * 60 * 60 * 1000 },
  { value: "30d", label: "Last 30 days", durationMs: 30 * 24 * 60 * 60 * 1000 },
  { value: "all", label: "All time", durationMs: null },
  { value: "custom", label: "Custom range", durationMs: null },
] as const;

const SORT_OPTIONS = [
  { value: "recent", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "duration_desc", label: "Longest duration" },
] as const;

const JOBS_PAGE_SIZE = 100;

export default function WorkspaceJobsRoute() {
  const { workspace } = useWorkspaceContext();
  const [selectedStatuses, setSelectedStatuses] = useState<Set<JobStatus>>(new Set());
  const [timeRange, setTimeRange] = useState<(typeof TIME_RANGE_OPTIONS)[number]["value"]>("7d");
  const [sortOrder, setSortOrder] = useState<(typeof SORT_OPTIONS)[number]["value"]>("recent");
  const [searchTerm, setSearchTerm] = useState("");
  const [customRange, setCustomRange] = useState<{ start: string; end: string }>({ start: "", end: "" });

  const singleStatusForQuery = selectedStatuses.size === 1 ? Array.from(selectedStatuses)[0] : null;

  const jobsQuery = useInfiniteQuery<JobRecord[]>({
    queryKey: workspaceJobsKeys.list(workspace.id, { status: singleStatusForQuery ?? "all" }),
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceJobs(
        workspace.id,
        {
          status: singleStatusForQuery,
          limit: JOBS_PAGE_SIZE,
          offset: pageParam,
        },
        signal,
      ),
    getNextPageParam: (lastPage, pages) =>
      lastPage.length === JOBS_PAGE_SIZE ? pages.length * JOBS_PAGE_SIZE : undefined,
    enabled: Boolean(workspace.id),
    staleTime: 30_000,
  });

  const jobs = useMemo(() => {
    const pages = jobsQuery.data?.pages ?? [];
    return pages.flat();
  }, [jobsQuery.data?.pages]);

  const filteredJobs = useMemo(() => {
    const now = Date.now();
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const timeConfig = TIME_RANGE_OPTIONS.find((option) => option.value === timeRange);
    const horizon = timeConfig?.value === "custom" ? null : timeConfig?.durationMs ?? null;
    let customStartMs = customRange.start ? new Date(customRange.start).getTime() : null;
    let customEndMs = customRange.end ? new Date(customRange.end).getTime() : null;
    if (customStartMs && customEndMs && customStartMs > customEndMs) {
      [customStartMs, customEndMs] = [customEndMs, customStartMs];
    }

    return jobs
      .filter((job) => {
        if (selectedStatuses.size > 0 && !selectedStatuses.has(job.status as JobStatus)) {
          return false;
        }
        if (timeRange === "custom") {
          const startedAt = getJobStartTimestamp(job);
          if (customStartMs && startedAt < customStartMs) return false;
          if (customEndMs && startedAt > customEndMs) return false;
        } else if (horizon) {
          const startedAt = getJobStartTimestamp(job);
          if (now - startedAt > horizon) return false;
        }
        if (normalizedSearch) {
          if (!jobSearchHaystack(job).includes(normalizedSearch)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        switch (sortOrder) {
          case "oldest":
            return getJobStartTimestamp(a) - getJobStartTimestamp(b);
          case "duration_desc":
            return durationMs(b) - durationMs(a);
          case "recent":
          default:
            return getJobStartTimestamp(b) - getJobStartTimestamp(a);
        }
      });
  }, [jobs, selectedStatuses, timeRange, sortOrder, searchTerm, customRange]);

  const toggleStatus = (status: JobStatus) => {
    setSelectedStatuses((current) => {
      const next = new Set(current);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedStatuses(new Set());
    setTimeRange("7d");
    setSortOrder("recent");
    setSearchTerm("");
    setCustomRange({ start: "", end: "" });
  };

  const handleExport = () => {
    if (filteredJobs.length === 0) return;
    const rows = filteredJobs.map((job) => [
      job.id,
      deriveDocumentName(job) ?? "—",
      deriveConfigLabel(job),
      deriveTriggeredBy(job) ?? "—",
      job.status,
      formatTimestamp(getJobStartTimestamp(job)),
      formatTimestamp(getJobEndTimestamp(job)),
      (durationMs(job) / 1000).toFixed(1),
      (job as { error_message?: string }).error_message ?? "",
    ]);
    const header = [
      "Job ID",
      "Document",
      "Config",
      "Triggered by",
      "Status",
      "Started",
      "Finished",
      "Duration (s)",
      "Error message",
    ];
    const csv = [header, ...rows]
      .map((cols) => cols.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `jobs-${new Date().toISOString()}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white/95 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Jobs</p>
            <h1 className="text-lg font-semibold text-slate-900 sm:text-xl">{workspace.name ?? "Workspace"} jobs</h1>
            <p className="text-xs text-slate-500">Review previous runs, filter by status, and export job history.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={handleExport} disabled={filteredJobs.length === 0}>
              Export CSV
            </Button>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Reset filters
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <StatusPillBar selected={selectedStatuses} onToggle={toggleStatus} />
          <Select value={timeRange} onChange={(event) => setTimeRange(event.target.value as typeof timeRange)} className="w-48">
            {TIME_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          {timeRange === "custom" ? (
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              <label className="flex flex-col gap-1">
                Start
                <input
                  type="datetime-local"
                  value={customRange.start}
                  onChange={(event) => setCustomRange((prev) => ({ ...prev, start: event.target.value }))}
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                />
              </label>
              <label className="flex flex-col gap-1">
                End
                <input
                  type="datetime-local"
                  value={customRange.end}
                  onChange={(event) => setCustomRange((prev) => ({ ...prev, end: event.target.value }))}
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                />
              </label>
            </div>
          ) : null}
          <Select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as typeof sortOrder)} className="w-48">
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <div className="flex-1 min-w-[220px]">
            <input
              type="search"
              placeholder="Search jobs by ID, document, or config"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        {jobsQuery.isError ? (
          <div className="py-16">
            <PageState
              variant="error"
              title="Unable to load jobs"
              description="We couldn’t fetch job history right now. Try reloading the page."
            />
          </div>
        ) : jobsQuery.isLoading ? (
          <div className="py-16 text-center text-sm text-slate-500">Loading jobs…</div>
        ) : filteredJobs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm text-slate-500">No jobs match the current filters.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full table-fixed border-separate border-spacing-0 text-sm text-slate-700">
                <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">Job ID</th>
                    <th className="px-3 py-2 text-left">Document</th>
                    <th className="px-3 py-2 text-left">Config</th>
                    <th className="px-3 py-2 text-left">Triggered by</th>
                    <th className="px-3 py-2 text-left">Started</th>
                    <th className="px-3 py-2 text-left">Duration</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => {
                    const documentName = deriveDocumentName(job);
                    const configLabel = deriveConfigLabel(job);
                    const triggeredBy = deriveTriggeredBy(job);
                    const status = job.status as JobStatus;
                    return (
                      <tr key={job.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">{job.id}</td>
                        <td className="px-3 py-2">
                          <p className="truncate font-semibold text-slate-900">{documentName ?? "—"}</p>
                          <p className="text-xs text-slate-500">
                            {Array.isArray((job as { input_documents?: unknown[] }).input_documents)
                              ? `${(job as { input_documents?: unknown[] }).input_documents?.length ?? 0} document(s)`
                              : "—"}
                          </p>
                        </td>
                        <td className="px-3 py-2">
                          <p className="truncate text-slate-800">{configLabel}</p>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{triggeredBy ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-600">
                          <time dateTime={new Date(getJobStartTimestamp(job)).toISOString()}>
                            {formatTimestamp(getJobStartTimestamp(job))}
                          </time>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{formatDuration(durationMs(job))}</td>
                        <td className="px-3 py-2">
                          <span
                            className={clsx(
                              "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                              JOB_STATUS_CLASSES[status] ?? "bg-slate-200 text-slate-700",
                            )}
                          >
                            {JOB_STATUS_LABELS[status] ?? status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {jobsQuery.hasNextPage ? (
              <div className="border-t border-slate-200 bg-slate-50/60 px-3 py-2 text-center">
                <Button
                  variant="ghost"
                  onClick={() => jobsQuery.fetchNextPage()}
                  disabled={jobsQuery.isFetchingNextPage}
                  isLoading={jobsQuery.isFetchingNextPage}
                >
                  Load more jobs
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

function StatusPillBar({
  selected,
  onToggle,
}: {
  selected: ReadonlySet<JobStatus>;
  onToggle: (status: JobStatus) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(JOB_STATUS_LABELS) as JobStatus[]).map((status) => {
        const active = selected.has(status);
        return (
          <button
            key={status}
            type="button"
            onClick={() => onToggle(status)}
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-medium",
              active
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900",
            )}
          >
            {JOB_STATUS_LABELS[status]}
          </button>
        );
      })}
    </div>
  );
}

function deriveDocumentName(job: JobRecord) {
  const documents = (job as { input_documents?: unknown[] }).input_documents;
  if (!Array.isArray(documents) || documents.length === 0) return null;
  const primary = documents[0] as Record<string, string> | undefined;
  if (!primary) return null;
  return primary.display_name ?? primary.name ?? primary.original_filename ?? primary.id ?? null;
}

function deriveConfigLabel(job: JobRecord) {
  const configVersion = (job as { config_version?: Record<string, string> }).config_version;
  if (configVersion) {
    return configVersion.title ?? configVersion.semver ?? configVersion.config_version_id ?? "—";
  }
  return (job as { config_title?: string }).config_title ?? (job as { config_id?: string }).config_id ?? "—";
}

function deriveTriggeredBy(job: JobRecord) {
  const submitted = (job as { submitted_by_user?: { display_name?: string; email?: string } }).submitted_by_user;
  if (submitted) return submitted.display_name ?? submitted.email ?? null;
  return (job as { submitted_by?: string }).submitted_by ?? null;
}

function jobSearchHaystack(job: JobRecord) {
  return [
    job.id,
    deriveDocumentName(job),
    deriveConfigLabel(job),
    deriveTriggeredBy(job),
    job.status,
    (job as { error_message?: string }).error_message,
    (job as { summary?: string }).summary,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getJobStartTimestamp(job: JobRecord) {
  const ms =
    (job as { started_at?: string }).started_at ??
    (job as { queued_at?: string }).queued_at ??
    (job as { created_at?: string }).created_at ??
    ((job as { created?: number }).created ? (job as { created?: number }).created * 1000 : null);
  return typeof ms === "string" ? new Date(ms).getTime() : typeof ms === "number" ? ms : Date.now();
}

function getJobEndTimestamp(job: JobRecord) {
  const ms =
    (job as { completed_at?: string }).completed_at ??
    (job as { cancelled_at?: string }).cancelled_at ??
    (job as { updated_at?: string }).updated_at;
  return typeof ms === "string" ? new Date(ms).getTime() : typeof ms === "number" ? ms : Date.now();
}

function durationMs(job: JobRecord) {
  const start = getJobStartTimestamp(job);
  const end = getJobEndTimestamp(job);
  if (!start || !end) return 0;
  return Math.max(0, end - start);
}

function formatDuration(ms: number) {
  if (ms <= 0) return "—";
  const seconds = Math.round(ms / 100) / 10;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${remaining}s`;
}

function formatTimestamp(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toLocaleString();
}
