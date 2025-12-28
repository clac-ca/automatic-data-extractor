import clsx from "clsx";

import { Button } from "@ui/Button";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import {
  buildStatusDescription,
  getDocumentOutputRun,
  MAX_PREVIEW_COLUMNS,
  MAX_PREVIEW_ROWS,
} from "../data";
import type { DocumentEntry, RunResource, WorkbookPreview, WorkbookSheet } from "../types";
import {
  buildNormalizedFilename,
  formatRelativeTime,
  formatBytes,
  numberFormatter,
  parseTimestamp,
} from "../utils";
import { CloseIcon, DownloadIcon, RefreshIcon } from "./icons";
import { MappingBadge } from "./MappingBadge";
import { StatusPill } from "./StatusPill";

export function DocumentsPreviewPane({
  document,
  now,
  activeSheetId,
  onSheetChange,
  onClose,
  // Runs
  runs,
  runsLoading,
  activeRunId,
  onRunSelect,
  activeRun,
  // Output preview
  outputUrl,
  workbook,
  workbookLoading,
  workbookError,
  // Actions
  onDownloadOutput,
  onDownloadOriginal,
  onReprocess,
}: {
  document: DocumentEntry | null;
  now: number;
  activeSheetId: string | null;
  onSheetChange: (id: string) => void;
  onClose: () => void;

  runs: RunResource[];
  runsLoading: boolean;
  activeRunId: string | null;
  onRunSelect: (id: string) => void;
  activeRun: RunResource | null;

  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  onDownloadOutput: (doc: DocumentEntry, run: RunResource | null) => void;
  onDownloadOriginal: (doc: DocumentEntry) => void;
  onReprocess: (doc: DocumentEntry) => void;
}) {
  const sheets = workbook?.sheets ?? [];
  const selectedSheetId = activeSheetId ?? sheets[0]?.name ?? "";
  const activeSheet = sheets.find((sheet) => sheet.name === selectedSheetId) ?? sheets[0];

  const fallbackRunId = getDocumentOutputRun(document?.record)?.run_id ?? null;
  const canDownloadOutput = Boolean(
    document?.record && (activeRun?.status === "succeeded" ? outputUrl : fallbackRunId),
  );
  const outputMeta = activeRun?.output;
  const outputFilename = document ? outputMeta?.filename ?? buildNormalizedFilename(document.name) : "";
  const outputSize = outputMeta?.size_bytes && outputMeta.size_bytes > 0 ? formatBytes(outputMeta.size_bytes) : null;

  const outputSheetSummary = activeSheet
    ? `${numberFormatter.format(activeSheet.totalRows)} rows · ${numberFormatter.format(activeSheet.totalColumns)} cols`
    : null;

  const outputSummary = [outputSize, outputSheetSummary].filter(Boolean).join(" · ");

  return (
    <aside className="flex min-h-0 w-full flex-col border-t border-slate-200 bg-white lg:w-[42%] lg:border-l lg:border-t-0">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Document</p>
          <h2 className="truncate text-lg font-semibold text-slate-900">
            {document ? document.name : "Select a document"}
          </h2>

          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {document ? (
              <>
                <StatusPill status={document.status} />
                <MappingBadge mapping={document.mapping} />
                <span>{buildStatusDescription(document.status, activeRun)}</span>
              </>
            ) : (
              <span>Choose a file to inspect runs and output.</span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <Button type="button" size="sm" variant="ghost" className="gap-2" onClick={onClose}>
            <CloseIcon className="h-4 w-4" />
            Close
          </Button>

          {document?.record ? (
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                size="sm"
                className="gap-2"
                onClick={() => onDownloadOutput(document, activeRun)}
                disabled={!canDownloadOutput}
              >
                <DownloadIcon className="h-4 w-4" />
                Download output
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="gap-2"
                onClick={() => onDownloadOriginal(document)}
              >
                <DownloadIcon className="h-4 w-4" />
                Download original
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="gap-2"
                onClick={() => onReprocess(document)}
              >
                <RefreshIcon className="h-4 w-4" />
                Reprocess
              </Button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {!document ? (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center text-sm text-slate-500">
            <p className="text-sm font-semibold text-slate-900">Preview is ready when you are.</p>
            <p>Select a document from the list to inspect runs and output.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {/* Summary */}
            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">Summary</h3>
                <span className="text-xs text-slate-500">Updated {formatRelativeTime(now, document.updatedAt)}</span>
              </div>
              <dl className="mt-4 grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Type</dt>
                  <dd className="font-semibold text-slate-900">{document.fileType.toUpperCase()}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Size</dt>
                  <dd className="font-semibold text-slate-900">{document.size}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Uploader</dt>
                  <dd className="font-semibold text-slate-900">{document.uploader ?? "Unassigned"}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Tags</dt>
                  <dd className="text-xs text-slate-700">
                    {document.tags.length === 0 ? "No tags" : document.tags.join(", ")}
                  </dd>
                </div>
              </dl>
            </section>

            {/* Runs + selector */}
            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">Runs</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Active run</span>
                  <select
                    value={activeRunId ?? ""}
                    onChange={(e) => onRunSelect(e.target.value)}
                    aria-label="Select run"
                    className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
                    disabled={runsLoading || runs.length === 0}
                  >
                    {runs.length === 0 ? <option value="">No runs</option> : null}
                    {runs.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.status.toUpperCase()} · {formatRelativeTime(now, parseTimestamp(r.created_at))}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50">
                {runsLoading ? (
                  <PreviewMessage title="Loading runs">Fetching run history…</PreviewMessage>
                ) : runs.length === 0 ? (
                  <PreviewMessage title="No runs yet">
                    Processing starts automatically after upload. If this document is new, give it a moment.
                  </PreviewMessage>
                ) : (
                  <div className="divide-y divide-slate-200">
                    {runs.slice(0, 6).map((r) => {
                      const isActive = r.id === activeRunId;
                      const failure = r.failure_message ?? r.failure_stage ?? r.failure_code ?? null;
                      return (
                        <button
                          key={r.id}
                          type="button"
                          onClick={() => onRunSelect(r.id)}
                          className={clsx(
                            "flex w-full items-start justify-between gap-3 px-4 py-3 text-left text-xs transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                            isActive ? "bg-white" : "hover:bg-white/70",
                          )}
                        >
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-900">
                              {r.status.toUpperCase()}{" "}
                              <span className="ml-2 font-normal text-slate-500">
                                {formatRelativeTime(now, parseTimestamp(r.created_at))}
                              </span>
                            </div>
                            {failure ? (
                              <div className="mt-1 truncate text-[11px] text-rose-700">{failure}</div>
                            ) : (
                              <div className="mt-1 text-[11px] text-slate-500">
                                {r.duration_seconds ? `${Math.round(r.duration_seconds)}s` : "—"}
                              </div>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-500">
                            {r.output?.has_output ? "Output" : "—"}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>

            {/* Output */}
            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">Processed output</h3>
                <Button
                  type="button"
                  size="sm"
                  className="gap-2"
                  onClick={() => onDownloadOutput(document, activeRun)}
                  disabled={!canDownloadOutput}
                >
                  <DownloadIcon className="h-4 w-4" />
                  Download XLSX
                </Button>
              </div>

              {activeRun?.status === "succeeded" ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span className="font-semibold text-slate-900">{outputFilename}</span>
                  {outputSummary ? <span>{outputSummary}</span> : null}
                </div>
              ) : null}

              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50">
                {activeRun?.status === "succeeded" ? (
                  !outputUrl ? (
                    <PreviewMessage title="Output link unavailable">
                      We could not load the processed output link yet. Try again in a moment.
                    </PreviewMessage>
                  ) : workbookLoading ? (
                    <PreviewMessage title="Loading preview">Fetching the processed workbook for review.</PreviewMessage>
                  ) : workbookError ? (
                    <PreviewMessage title="Preview unavailable">
                      The XLSX is ready to download, but we could not render the preview.
                    </PreviewMessage>
                  ) : activeSheet ? (
                    <div>
                      <TabsRoot value={selectedSheetId} onValueChange={onSheetChange}>
                        <TabsList className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs">
                          {sheets.map((sheet) => (
                            <TabsTrigger
                              key={sheet.name}
                              value={sheet.name}
                              className={clsx(
                                "rounded-full px-3 py-1 font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                                selectedSheetId === sheet.name
                                  ? "bg-white text-slate-900 shadow-sm"
                                  : "text-slate-500 hover:text-slate-800",
                              )}
                            >
                              {sheet.name}
                            </TabsTrigger>
                          ))}
                        </TabsList>
                        {sheets.map((sheet) => (
                          <TabsContent key={sheet.name} value={sheet.name} className="max-h-[28rem] overflow-auto">
                            <PreviewTable sheet={sheet} />
                          </TabsContent>
                        ))}
                      </TabsRoot>
                      {(activeSheet.truncatedRows || activeSheet.truncatedColumns) && (
                        <div className="border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500">
                          Showing first {Math.min(activeSheet.totalRows, MAX_PREVIEW_ROWS)} rows and{" "}
                          {Math.min(activeSheet.totalColumns, MAX_PREVIEW_COLUMNS)} columns.
                        </div>
                      )}
                    </div>
                  ) : (
                    <PreviewMessage title="Preview unavailable">
                      The processed XLSX is ready to download, but we cannot render a preview here.
                    </PreviewMessage>
                  )
                ) : activeRun?.status === "failed" ? (
                  <PreviewMessage title={activeRun.failure_message ?? "Run failed"}>
                    {activeRun.failure_stage ?? "We could not complete normalization for this file."}
                  </PreviewMessage>
                ) : (
                  <PreviewMessage title="Processing output">
                    {document.stage ?? "Preparing normalized output"}
                  </PreviewMessage>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </aside>
  );
}

function PreviewMessage({ title, children }: { title: string; children: string }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-slate-500">
      <p className="font-semibold text-slate-900">{title}</p>
      <p>{children}</p>
    </div>
  );
}

function PreviewTable({ sheet }: { sheet: WorkbookSheet }) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 z-10 bg-slate-100 text-slate-500">
        <tr>
          {sheet.headers.map((column, index) => (
            <th key={`${column}-${index}`} className="px-3 py-2 font-semibold uppercase tracking-wide">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.map((row, rowIndex) => (
          <tr key={`${sheet.name}-${rowIndex}`} className="border-t border-slate-200">
            {row.map((cell, cellIndex) => (
              <td key={`${sheet.name}-${rowIndex}-${cellIndex}`} className="px-3 py-2 text-slate-900">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
