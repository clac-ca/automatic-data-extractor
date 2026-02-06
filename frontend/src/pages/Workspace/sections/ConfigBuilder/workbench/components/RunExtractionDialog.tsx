import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchDocumentSheets, type DocumentSheet } from "@/api/documents";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatDocumentTimestamp, fetchRecentDocuments, type WorkbenchDocumentRow } from "../utils/runDocuments";

export type RunLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

const RUN_LOG_LEVEL_OPTIONS: Array<{ value: RunLogLevel; label: string }> = [
  { value: "DEBUG", label: "Debug" },
  { value: "INFO", label: "Info" },
  { value: "WARNING", label: "Warning" },
  { value: "ERROR", label: "Error" },
];

export type RunExtractionSelection = {
  documentId: string;
  documentName: string;
  sheetNames?: readonly string[];
  logLevel: RunLogLevel;
};

interface RunExtractionDialogProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly onClose: () => void;
  readonly onRun: (selection: RunExtractionSelection) => void;
}

export function RunExtractionDialog({
  open,
  workspaceId,
  onClose,
  onRun,
}: RunExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const documentsQuery = useQuery<WorkbenchDocumentRow[]>({
    queryKey: ["builder-documents", workspaceId],
    queryFn: ({ signal }) => fetchRecentDocuments(workspaceId, signal),
    staleTime: 60_000,
    enabled: open,
  });
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  );
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  useEffect(() => {
    if (!open) {
      return;
    }
    if (!documents.length) {
      setSelectedDocumentId("");
      return;
    }
    setSelectedDocumentId((current) => {
      if (current && documents.some((doc) => doc.id === current)) {
        return current;
      }
      return documents[0]?.id ?? "";
    });
  }, [documents, open]);

  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["builder-document-sheets", workspaceId, selectedDocumentId],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, selectedDocumentId, signal),
    enabled: open && Boolean(selectedDocumentId),
    staleTime: 60_000,
  });
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [logLevel, setLogLevel] = useState<RunLogLevel>("INFO");
  useEffect(() => {
    if (!open) {
      return;
    }
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    setSelectedSheets((current) =>
      current.filter((name) => sheetOptions.some((sheet) => sheet.name === name)),
    );
  }, [open, sheetOptions]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  if (!open) {
    return null;
  }

  const runDisabled = !selectedDocument || documentsQuery.isLoading || documentsQuery.isError;
  const sheetsAvailable = sheetOptions.length > 0;

  const content = (
    <div className="fixed inset-0 z-[var(--app-z-modal)] flex items-center justify-center bg-overlay-strong px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Select a document</h2>
            <p className="text-sm text-muted-foreground">
              Choose a workspace document and optional worksheet before running a test.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        {documentsQuery.isError ? (
          <Alert tone="danger">Unable to load documents. Try again later.</Alert>
        ) : documentsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">Upload a document in the workspace to run the extractor.</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="builder-run-document-select">
                Document
              </label>
              <Select
                value={selectedDocumentId || undefined}
                onValueChange={(value) => setSelectedDocumentId(value)}
              >
                <SelectTrigger id="builder-run-document-select" className="w-full">
                  <SelectValue placeholder="Select a document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((document) => (
                    <SelectItem key={document.id} value={document.id}>
                      {document.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-muted-foreground">
                  Uploaded {formatDocumentTimestamp(selectedDocument.createdAt)} ·{" "}
                  {(selectedDocument.byteSize ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="builder-run-log-level-select">
                Log level
              </label>
              <Select value={logLevel} onValueChange={(value) => setLogLevel(value as RunLogLevel)}>
                <SelectTrigger id="builder-run-log-level-select" className="w-full">
                  <SelectValue placeholder="Select a log level" />
                </SelectTrigger>
                <SelectContent>
                  {RUN_LOG_LEVEL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Controls the engine runtime verbosity for this run.</p>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Worksheet</p>
              {sheetQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading worksheets…</p>
              ) : sheetQuery.isError ? (
                <Alert tone="warning">
                  <div className="space-y-2">
                    <p className="text-sm text-foreground">
                      Worksheet metadata is temporarily unavailable. The run will process the entire file unless you retry and
                      pick specific sheets.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => sheetQuery.refetch()}
                        disabled={sheetQuery.isFetching}
                      >
                        Retry loading
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                        Use all worksheets
                      </Button>
                    </div>
                  </div>
                </Alert>
              ) : sheetsAvailable ? (
                <div className="space-y-3 rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">Worksheets</p>
                      <p className="text-xs text-muted-foreground">
                        {normalizedSheetSelection.length === 0
                          ? "All worksheets will be processed by default. Select specific sheets to narrow the run."
                          : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                              normalizedSheetSelection.length === 1 ? "" : "s"
                            } selected.`}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                      Use all worksheets
                    </Button>
                  </div>

                  <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-border p-2">
                    {sheetOptions.map((sheet) => {
                      const checked = normalizedSheetSelection.includes(sheet.name);
                      return (
                        <label
                          key={`${sheet.index}-${sheet.name}`}
                          className="flex items-center gap-2 rounded px-2 py-1 text-sm text-foreground hover:bg-muted"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                            checked={checked}
                            onChange={() => toggleWorksheet(sheet.name)}
                          />
                          <span className="flex-1 truncate">
                            {sheet.name}
                            {sheet.is_active ? " (active)" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">This file will be ingested directly.</p>
              )}
            </div>
          </div>
        )}

        <footer className="mt-6 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (!selectedDocument) {
                return;
              }
              onRun({
                documentId: selectedDocument.id,
                documentName: selectedDocument.name,
                sheetNames: normalizedSheetSelection.length > 0 ? normalizedSheetSelection : undefined,
                logLevel,
              });
            }}
            disabled={runDisabled}
          >
            Start test run
          </Button>
        </footer>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(content, document.body);
}
