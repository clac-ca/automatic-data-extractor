import clsx from "clsx";
import { useMemo, useState } from "react";

import { Button } from "@ui/Button";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import type { RunResource } from "@schema";

import { MAX_PREVIEW_COLUMNS, MAX_PREVIEW_ROWS } from "../data";
import type { DocumentComment, DocumentEntry, WorkspacePerson, WorkbookPreview, WorkbookSheet } from "../types";
import { buildNormalizedFilename, formatBytes, formatRelativeTime, numberFormatter, shortId } from "../utils";
import { ChatIcon, CloseIcon, DownloadIcon, LinkIcon, RefreshIcon, UserIcon } from "./icons";
import { CommentsPanel } from "./CommentsPanel";
import { MappingBadge } from "./MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "./PeoplePicker";
import { StatusPill } from "./StatusPill";
import { TagPicker } from "./TagPicker";

export function DocumentsPreviewPane({
  workspaceId,
  document,
  now,
  activeSheetId,
  onSheetChange,

  runs,
  runsLoading,
  selectedRunId,
  onSelectRun,
  activeRun,
  runLoading,

  outputUrl,
  onDownloadOutput,
  onDownloadOriginal,
  onReprocess,

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

  outputUrl: string | null;
  onDownloadOutput: (doc: DocumentEntry | null) => void;
  onDownloadOriginal: (doc: DocumentEntry | null) => void;
  onReprocess: (doc: DocumentEntry | null) => void;

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
}) {
  const [tab, setTab] = useState<"output" | "notes" | "details">("output");

  const sheets = workbook?.sheets ?? [];
  const selectedSheetId = activeSheetId ?? sheets[0]?.name ?? "";
  const activeSheet = sheets.find((sheet) => sheet.name === selectedSheetId) ?? sheets[0];

  const canDownloadOutput = Boolean(document?.record && outputUrl);
  const canDownloadOriginal = Boolean(document?.record);
  const canReprocess = Boolean(document?.record && activeRun?.configuration_id);

  const outputMeta = activeRun?.output;
  const outputFilename = document ? outputMeta?.filename ?? buildNormalizedFilename(document.name) : "";
  const outputSize = outputMeta?.size_bytes && outputMeta.size_bytes > 0 ? formatBytes(outputMeta.size_bytes) : null;
  const outputSheetSummary = activeSheet
    ? `${numberFormatter.format(activeSheet.totalRows)} rows - ${numberFormatter.format(activeSheet.totalColumns)} cols`
    : null;
  const outputSummary = [outputSize, outputSheetSummary].filter(Boolean).join(" - ");

  const runOptions = useMemo(() => {
    return runs.slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  }, [runs]);

  const hasOutput = activeRun?.status === "succeeded" && Boolean(outputUrl);

  return (
    <aside className="flex min-h-0 min-w-0 w-full flex-col border-l border-border bg-card lg:w-[44%]">
      <div className="shrink-0 border-b border-border px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Preview</p>
            <h2 className="truncate text-lg font-semibold text-foreground">
              {document ? document.name : "Select a document"}
            </h2>
          </div>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 w-8 shrink-0 px-0"
            onClick={onClose}
            aria-label="Close preview"
            title="Close preview"
          >
            <CloseIcon className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {document ? (
            <>
              <StatusPill status={document.status} />
              <MappingBadge mapping={document.mapping} />
              {document.commentCount > 0 ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-1 text-[11px] font-semibold text-muted-foreground">
                  <ChatIcon className="h-3.5 w-3.5" />
                  {document.commentCount} notes
                </span>
              ) : null}
            </>
          ) : (
            <span>Choose a file to inspect output, assign ownership, and leave notes.</span>
          )}
        </div>

        {document ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="gap-2 text-xs"
              onClick={() => onCopyLink(document)}
              disabled={!document?.record}
            >
              <LinkIcon className="h-4 w-4" />
              Copy link
            </Button>

            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="gap-2 text-xs"
              onClick={() => onDownloadOriginal(document)}
              disabled={!canDownloadOriginal}
            >
              <DownloadIcon className="h-4 w-4" />
              Original
            </Button>

            <Button
              type="button"
              size="sm"
              className="gap-2 text-xs"
              onClick={() => onDownloadOutput(document)}
              disabled={!canDownloadOutput}
            >
              <DownloadIcon className="h-4 w-4" />
              Output
            </Button>

            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="gap-2 text-xs"
              onClick={() => onReprocess(document)}
              disabled={!canReprocess}
            >
              <RefreshIcon className="h-4 w-4" />
              Reprocess
            </Button>
          </div>
        ) : null}

        {document ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-background px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card">
                <UserIcon className="h-4 w-4 text-muted-foreground" />
              </span>
              <div>
                <p className="text-xs text-muted-foreground">Assignee</p>
                <p className="text-sm font-semibold text-foreground">{document.assigneeLabel ?? "Unassigned"}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {!document.assigneeKey ? (
                <Button type="button" size="sm" onClick={() => onPickUp(document.id)} className="text-xs">
                  Pick up
                </Button>
              ) : document.assigneeKey !== currentUserKey ? (
                <Button type="button" size="sm" variant="secondary" onClick={() => onPickUp(document.id)} className="text-xs">
                  Assign to me
                </Button>
              ) : null}

              <PeoplePicker
                people={people}
                value={[document.assigneeKey ?? unassignedKey()]}
                onChange={(keys) => onAssign(document.id, normalizeSingleAssignee(keys))}
                placeholder="Assign..."
                includeUnassigned
                buttonClassName="min-w-0 max-w-[14rem] text-xs"
              />
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
        {!document ? (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-background px-6 text-center text-sm text-muted-foreground">
            <p className="text-sm font-semibold text-foreground">Preview is ready when you are.</p>
            <p>Select a document from the grid to inspect its output and collaborate.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <TabsRoot value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
              <TabsList className="flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-background px-3 py-2 text-xs">
                <TabsTrigger
                  value="output"
                  className={clsx(
                    "rounded-full px-3 py-1 font-semibold transition",
                    tab === "output" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Output
                </TabsTrigger>
                <TabsTrigger
                  value="notes"
                  className={clsx(
                    "rounded-full px-3 py-1 font-semibold transition",
                    tab === "notes" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Notes {document.commentCount > 0 ? `(${document.commentCount})` : ""}
                </TabsTrigger>
                <TabsTrigger
                  value="details"
                  className={clsx(
                    "rounded-full px-3 py-1 font-semibold transition",
                    tab === "details" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Details
                </TabsTrigger>
              </TabsList>

              <TabsContent value="output" className="mt-5">
                <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Run history</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {runsLoading ? "Loading runs..." : `${runs.length} run${runs.length === 1 ? "" : "s"} found`}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-muted-foreground">Selected run:</span>
                      <div className="rounded-full border border-border bg-background px-2 py-1 text-xs font-semibold text-foreground">
                        {selectedRunId ? shortId(selectedRunId) : "Latest"}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 max-h-44 overflow-auto rounded-2xl border border-border bg-background">
                    {runsLoading ? (
                      <div className="px-4 py-4 text-sm text-muted-foreground">Loading runs...</div>
                    ) : runOptions.length === 0 ? (
                      <div className="px-4 py-4 text-sm text-muted-foreground">No runs yet.</div>
                    ) : (
                      <div className="divide-y divide-border">
                        {runOptions.slice(0, 10).map((run) => {
                          const active = run.id === (selectedRunId ?? runOptions[0]?.id);
                          return (
                            <button
                              key={run.id}
                              type="button"
                              onClick={() => onSelectRun(run.id)}
                              className={clsx(
                                "flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm transition",
                                active ? "bg-card" : "hover:bg-muted",
                              )}
                            >
                              <div className="min-w-0">
                                <p className="truncate font-semibold text-foreground">
                                  {shortId(run.id)} - {run.status.toUpperCase()}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  Created {formatRelativeTime(now, Date.parse(run.created_at))}
                                </p>
                              </div>
                              <span className="text-xs font-semibold text-muted-foreground">
                                {run.output?.has_output ? "Output ready" : "No output"}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </section>

                <section className="mt-5 rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Processed output</h3>
                    <Button
                      type="button"
                      size="sm"
                      className="gap-2 text-xs"
                      onClick={() => onDownloadOutput(document)}
                      disabled={!canDownloadOutput}
                    >
                      <DownloadIcon className="h-4 w-4" />
                      Download output XLSX
                    </Button>
                  </div>

                  {hasOutput ? (
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">{outputFilename}</span>
                      {outputSummary ? <span>{outputSummary}</span> : null}
                    </div>
                  ) : null}

                  <div className="mt-4 rounded-2xl border border-border bg-background">
                    {hasOutput ? (
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
                            <TabsList className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-xs">
                              {sheets.map((sheet) => (
                                <TabsTrigger
                                  key={sheet.name}
                                  value={sheet.name}
                                  className={clsx(
                                    "rounded-full px-3 py-1 font-semibold transition",
                                    selectedSheetId === sheet.name
                                      ? "bg-card text-foreground shadow-sm"
                                      : "text-muted-foreground hover:text-foreground",
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
                            <div className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
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
                    ) : runLoading ? (
                      <PreviewMessage title="Loading run output">Fetching the latest run status.</PreviewMessage>
                    ) : (
                      <PreviewMessage title="Processing output">
                        {document.stage ?? "Preparing normalized output"}
                      </PreviewMessage>
                    )}
                  </div>
                </section>
              </TabsContent>

              <TabsContent value="notes" className="mt-5">
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
              </TabsContent>

              <TabsContent value="details" className="mt-5">
                <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Summary</h3>
                    <span className="text-xs text-muted-foreground">Updated {formatRelativeTime(now, document.updatedAt)}</span>
                  </div>

                  <dl className="mt-4 grid gap-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Uploader</dt>
                      <dd className="font-semibold text-foreground">{document.uploader ?? "Unassigned"}</dd>
                    </div>

                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Tags</dt>
                      <dd className="flex justify-end" title="Tags are shared and saved to the document">
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
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Mapping</dt>
                      <dd className="flex justify-end">
                        <MappingBadge mapping={document.mapping} />
                      </dd>
                    </div>
                  </dl>
                </section>

                <section className="mt-5 rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
                  <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Link</h3>
                  <p className="mt-3 text-xs text-muted-foreground">Copy a share link so teammates land directly on this document.</p>
                  <div className="mt-3">
                    <Button type="button" size="sm" variant="secondary" className="gap-2 text-xs" onClick={() => onCopyLink(document)}>
                      <LinkIcon className="h-4 w-4" />
                      Copy link
                    </Button>
                  </div>
                </section>
              </TabsContent>
            </TabsRoot>
          </div>
        )}
      </div>
    </aside>
  );
}

function PreviewMessage({ title, children }: { title: string; children: string }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
      <p className="font-semibold text-foreground">{title}</p>
      <p>{children}</p>
    </div>
  );
}

function PreviewTable({ sheet }: { sheet: WorkbookSheet }) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 bg-muted text-muted-foreground">
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
          <tr key={`${sheet.name}-${rowIndex}`} className="border-t border-border">
            {row.map((cell, cellIndex) => (
              <td key={`${sheet.name}-${rowIndex}-${cellIndex}`} className="px-3 py-2 text-foreground">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
