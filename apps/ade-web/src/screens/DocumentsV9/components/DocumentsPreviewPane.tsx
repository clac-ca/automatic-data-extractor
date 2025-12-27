import clsx from "clsx";
import type { ReactNode } from "react";

import { Button } from "@ui/Button";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import type { RunResource } from "@shared/runs/api";

import { buildStatusDescription, MAX_PREVIEW_COLUMNS, MAX_PREVIEW_ROWS } from "../data";
import type { DocumentEntry, WorkbookPreview, WorkbookSheet } from "../types";
import { buildNormalizedFilename, formatRelativeTime, formatBytes, numberFormatter } from "../utils";
import { CloseIcon, DownloadIcon } from "./icons";
import { MappingBadge } from "./MappingBadge";
import { StatusPill } from "./StatusPill";

export function DocumentsPreviewPane({
  document,
  now,
  activeSheetId,
  onSheetChange,
  onDownload,
  onClose,
  activeRun,
  runLoading,
  outputUrl,
  workbook,
  workbookLoading,
  workbookError,
}: {
  document: DocumentEntry | null;
  now: number;
  activeSheetId: string | null;
  onSheetChange: (id: string) => void;
  onDownload: (doc: DocumentEntry | null) => void;
  onClose: () => void;
  activeRun: RunResource | null;
  runLoading: boolean;
  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;
}) {
  const sheets = workbook?.sheets ?? [];
  const selectedSheetId = activeSheetId ?? sheets[0]?.name ?? "";
  const activeSheet = sheets.find((sheet) => sheet.name === selectedSheetId) ?? sheets[0];
  const canDownload = Boolean(document?.record && document.status === "ready" && outputUrl);
  const outputMeta = activeRun?.output;
  const outputFilename = document ? outputMeta?.filename ?? buildNormalizedFilename(document.name) : "";
  const outputSize =
    outputMeta?.size_bytes && outputMeta.size_bytes > 0 ? formatBytes(outputMeta.size_bytes) : null;
  const outputSheetSummary = activeSheet
    ? `${numberFormatter.format(activeSheet.totalRows)} rows · ${numberFormatter.format(activeSheet.totalColumns)} cols`
    : null;
  const outputSummary = [outputSize, outputSheetSummary].filter(Boolean).join(" · ");

  return (
    <aside className="flex min-h-0 w-full flex-col border-l border-slate-200 bg-white lg:w-[42%]">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Preview</p>
          <h2 className="truncate text-lg font-semibold text-slate-900">
            {document ? document.name : "Select a document"}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {document ? (
              <>
                <StatusPill status={document.status} />
                <span>{buildStatusDescription(document.status, activeRun)}</span>
              </>
            ) : (
              <span>Choose a file to inspect the processed output.</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="ghost" className="gap-2 text-xs" onClick={onClose}>
            <CloseIcon className="h-4 w-4" />
            Close <kbd className="ml-1 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">Esc</kbd>
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {!document ? (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center text-sm text-slate-500">
            <p className="text-sm font-semibold text-slate-900">Preview is ready when you are.</p>
            <p>Select a document from the grid to inspect its output.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">Summary</h3>
                <span className="text-xs text-slate-500">Updated {formatRelativeTime(now, document.updatedAt)}</span>
              </div>
              <dl className="mt-4 grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Uploaded</dt>
                  <dd className="font-semibold text-slate-900">{formatRelativeTime(now, document.createdAt)}</dd>
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
                  <dd className="flex flex-wrap items-center justify-end gap-2 text-xs">
                    {document.tags.length === 0 ? (
                      <span className="text-slate-500">No tags</span>
                    ) : (
                      document.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold"
                        >
                          {tag}
                        </span>
                      ))
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Mapping</dt>
                  <dd className="flex justify-end">{renderMappingSummary(document.mapping)}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">Processed output</h3>
                <Button
                  type="button"
                  size="sm"
                  className="gap-2 text-xs"
                  onClick={() => onDownload(document)}
                  disabled={!canDownload}
                >
                  <DownloadIcon className="h-4 w-4" />
                  Download processed XLSX
                </Button>
              </div>

              {!canDownload && document.status !== "ready" ? (
                <p className="mt-2 text-[11px] text-slate-400">Download becomes available when status is Ready.</p>
              ) : null}

              {document.status === "ready" ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span className="font-semibold text-slate-900">{outputFilename}</span>
                  {outputSummary ? <span>{outputSummary}</span> : null}
                </div>
              ) : null}

              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50">
                {document.status === "ready" ? (
                  !outputUrl ? (
                    <PreviewMessage title="Output link unavailable">
                      <p>We could not load the processed output link yet. Try again in a moment.</p>
                    </PreviewMessage>
                  ) : workbookLoading ? (
                    <PreviewMessage title="Loading preview">
                      <p>Fetching the processed workbook for review.</p>
                    </PreviewMessage>
                  ) : workbookError ? (
                    <PreviewMessage title="Preview unavailable">
                      <p>The XLSX is ready to download, but we could not render the preview.</p>
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
                                "rounded-full px-3 py-1 font-semibold transition",
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
                      <p>The processed XLSX is ready to download, but we cannot render a preview here.</p>
                    </PreviewMessage>
                  )
                ) : document.status === "failed" ? (
                  <PreviewMessage title={document.error?.summary ?? "Processing failed"}>
                    <p>{document.error?.detail ?? "We could not complete normalization for this file."}</p>
                    {document.error?.nextStep ? (
                      <p className="mt-2 text-[11px] text-slate-400">{document.error.nextStep}</p>
                    ) : null}
                  </PreviewMessage>
                ) : document.status === "archived" ? (
                  <PreviewMessage title="Archived">
                    <p>This document is archived and read-only.</p>
                  </PreviewMessage>
                ) : (
                  <PreviewMessage title="Processing output">
                    <p>{document.stage ?? "Preparing normalized output"}</p>
                  </PreviewMessage>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <h3 className="text-xs uppercase tracking-[0.2em] text-slate-400">History</h3>
              <div className="mt-4 text-xs text-slate-500">
                {runLoading ? (
                  <p className="text-[11px] text-slate-400">Refreshing run status...</p>
                ) : activeRun ? (
                  <p>
                    Run status: <span className="font-semibold text-slate-900">{activeRun.status}</span>
                  </p>
                ) : (
                  <p>Latest run updates appear here.</p>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </aside>
  );
}

function PreviewMessage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-6">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <div className="text-sm text-slate-500">{children}</div>
    </div>
  );
}

function PreviewTable({ sheet }: { sheet: WorkbookSheet }) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 bg-slate-100 text-slate-500">
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

function renderMappingSummary(mapping: DocumentEntry["mapping"]) {
  if (mapping.pending && mapping.attention === 0 && mapping.unmapped === 0) {
    return <span className="text-xs font-semibold text-slate-500">Mapping pending</span>;
  }
  if (mapping.attention === 0 && mapping.unmapped === 0) {
    return <span className="text-xs font-semibold text-slate-500">No mapping issues</span>;
  }
  return <MappingBadge mapping={mapping} showPending />;
}
