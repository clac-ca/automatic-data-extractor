import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckIcon, ChevronsUpDownIcon, Loader2, Save } from "lucide-react";
import { createDocumentActivityThread, fetchDocumentPreview } from "@/api/documents";
import { fetchRunFields, saveRunOutputEdits } from "@/api/runs/api";
import { listWorkspaceMembers } from "@/api/workspaces/api";
import { useNotifications } from "@/providers/notifications";
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { WorkspaceMember } from "@/types/workspaces";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { DocumentPreviewGrid } from "./components/DocumentPreviewGrid";
import { DocumentPreviewSheetTabs } from "./components/DocumentPreviewSheetTabs";
import { DocumentPreviewStatsRow } from "./components/DocumentPreviewStatsRow";
import { DocumentPreviewUnavailableState } from "./components/DocumentPreviewUnavailableState";
import { useDocumentPreviewModel } from "./hooks/useDocumentPreviewModel";
import { usePreviewDisplayPreferences } from "./hooks/usePreviewDisplayPreferences";
import { codePointIndexFromCodeUnitIndex } from "../comments/utils/mentions";

// Feature flag to control normalized preview editing.
// Set to true to re-enable editing normalized previews and saving changes back to the database.
const ENABLE_PREVIEW_EDITING = false;
const COLUMN_SAMPLE_LIMIT = 8;

type RuleScope = "signatory" | "universal";
type RunColumnMapping = NonNullable<DocumentRow["lastRunTableColumns"]>[number];
type AdminOption = {
  id: string;
  name: string | null;
  email: string;
  roleSlugs: string[];
};
type MappingRequestContext = {
  columnLabel: string;
  physicalIndex: number;
  gridColumnIndex: number;
  sheetName: string | null;
  source: DocumentPreviewSource;
  currentHeader: string | null;
  originalHeader: string | null;
  mappedField: string | null;
  mapping: RunColumnMapping | null;
  currentSample: string[];
};
type MappingRequestMention = {
  userId: string;
  start: number;
  end: number;
};

export function DocumentPreviewTab({
  workspaceId,
  document,
  source,
  sheet,
  onSourceChange,
  onSheetChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  source: DocumentPreviewSource;
  sheet: string | null;
  onSourceChange: (source: DocumentPreviewSource) => void;
  onSheetChange: (sheet: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();

  const {
    preferences,
    showHiddenRowsAndColumns,
    setShowHiddenRowsAndColumns,
  } = usePreviewDisplayPreferences(workspaceId);

  const model = useDocumentPreviewModel({
    workspaceId,
    document,
    source,
    sheet,
    onSheetChange,
    displayPreferences: preferences,
  });

  const [editedRows, setEditedRows] = useState<string[][] | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [mappingRequestContext, setMappingRequestContext] = useState<MappingRequestContext | null>(null);
  const [requestedMapping, setRequestedMapping] = useState("");
  const [ruleScope, setRuleScope] = useState<RuleScope | "">("");
  const [selectedAdminIds, setSelectedAdminIds] = useState<string[]>([]);
  const [adminPickerOpen, setAdminPickerOpen] = useState(false);
  const [isCreatingMappingRequest, setIsCreatingMappingRequest] = useState(false);
  const [mappingRequestError, setMappingRequestError] = useState<string | null>(null);
  const [comments, setComments] = useState("");
  const [fieldPickerOpen, setFieldPickerOpen] = useState(false);

  const lastRunId = document.lastRun?.id;
  const fieldsQuery = useQuery({
    queryKey: ["run-fields", workspaceId, lastRunId],
    queryFn: async ({ signal }) => {
      if (!lastRunId) return [];
      const fields = await fetchRunFields(workspaceId, lastRunId, signal);
      return fields ?? [];
    },
    enabled: Boolean(workspaceId && lastRunId && mappingRequestContext),
    staleTime: 60_000,
  });

  const nonPlaceholderFields = useMemo(() => {
    const fields = fieldsQuery.data ?? [];
    return fields.filter(
      (f) =>
        !f.field.toLowerCase().includes("placeholder") &&
        !f.label?.toLowerCase().includes("placeholder")
    );
  }, [fieldsQuery.data]);

  const adminsQuery = useQuery({
    queryKey: ["workspace-admin-members", workspaceId],
    queryFn: async ({ signal }) => {
      const page = await listWorkspaceMembers(workspaceId, { signal });
      return page.items.map(toAdminOption).filter(isAdminOption);
    },
    enabled: Boolean(workspaceId && mappingRequestContext),
    staleTime: 60_000,
  });

  const adminOptions = adminsQuery.data ?? [];
  const selectedAdmins = useMemo(() => {
    const byId = new Map(adminOptions.map((admin) => [admin.id, admin]));
    return selectedAdminIds.flatMap((id) => {
      const admin = byId.get(id);
      return admin ? [admin] : [];
    });
  }, [adminOptions, selectedAdminIds]);

  const handleHeaderMenuClick = useCallback((gridColumnIndex: number) => {
    // Map grid visible column index to sheet physical column index
    const physicalIndex = model.visibleIndices?.[gridColumnIndex];
    if (physicalIndex === undefined) return;

    // Search in document's column mapping telemetry
    const activeSheetName = sheet || (model.selectedSheet?.name ?? null);
    const lastRunTableColumns = document.lastRunTableColumns;

    let mapping: RunColumnMapping | null = null;
    const columnName = toPreviewString(model.previewRows?.[0]?.[gridColumnIndex]);

    if (source === "normalized") {
      // In normalized mode, the columns shown are the output schema columns.
      // Get the column name from row 0 of the visible columns.
      if (columnName) {
        const normName = columnName.toLowerCase();
        // Try matching by name and active sheet
        mapping = lastRunTableColumns?.find((col) => 
          (col.header_raw?.toLowerCase() === normName ||
           col.header_normalized?.toLowerCase() === normName ||
           col.mapped_field?.toLowerCase() === normName) && 
          col.sheet_name === activeSheetName
        ) ?? null;
        // Fallback to matching by name only (across any sheet)
        if (!mapping) {
          mapping = lastRunTableColumns?.find((col) => 
            col.header_raw?.toLowerCase() === normName ||
            col.header_normalized?.toLowerCase() === normName ||
            col.mapped_field?.toLowerCase() === normName
          ) ?? null;
        }
      }
    } else {
      // In original mode, column indexes map directly to the original sheet's columns
      mapping = lastRunTableColumns?.find((col) => 
        col.sheet_name === activeSheetName && col.column_index === physicalIndex
      ) ?? null;
      // Fallback: If index lookup failed but we have a columnName from row 0, match by name
      if (!mapping && columnName) {
        const normName = columnName.toLowerCase();
        mapping = lastRunTableColumns?.find((col) => 
          (col.header_raw?.toLowerCase() === normName ||
           col.header_normalized?.toLowerCase() === normName ||
           col.mapped_field?.toLowerCase() === normName) &&
          col.sheet_name === activeSheetName
        ) ?? null;
      }
    }

    const columnLabel = model.columnLabels[gridColumnIndex] || spreadsheetColumnLabel(physicalIndex);
    const currentSample = sampleColumnValues(model.previewRows, gridColumnIndex);

    setMappingRequestContext({
      columnLabel,
      physicalIndex,
      gridColumnIndex,
      sheetName: activeSheetName,
      source,
      currentHeader: columnName || null,
      originalHeader: mapping?.header_raw ?? null,
      mappedField: mapping?.mapped_field ?? null,
      mapping,
      currentSample,
    });
    setRequestedMapping("");
    setRuleScope("");
    setSelectedAdminIds([]);
    setComments("");
    setFieldPickerOpen(false);
    setMappingRequestError(null);
  }, [model.visibleIndices, model.columnLabels, model.previewRows, model.selectedSheet?.name, document.lastRunTableColumns, sheet, source]);

  // Reset editedRows when switching sheet, source, or when preview rows change
  useEffect(() => {
    setEditedRows(null);
  }, [source, sheet, model.previewRows]);

  const handleRowsChange = useCallback((nextRows: string[][]) => {
    setEditedRows(nextRows);
  }, []);

  const handleSave = useCallback(async () => {
    if (!editedRows) return;

    const runId = document.lastRun?.id;
    if (!runId) {
      notifyToast({
        title: "No run output available to save edits to.",
        intent: "danger",
        duration: 5000,
      });
      return;
    }

    setIsSaving(true);
    try {
      await saveRunOutputEdits(workspaceId, runId, {
        sheetName: sheet,
        sheetIndex: model.selectedSheet?.index ?? null,
        rows: editedRows,
      });

      notifyToast({
        title: "Spreadsheet changes saved successfully.",
        intent: "success",
        duration: 3500,
      });

      // Invalidate preview queries to fetch the newly written file
      await queryClient.invalidateQueries({
        queryKey: ["document-detail-preview-grid", workspaceId, document.id],
      });
      await queryClient.invalidateQueries({
        queryKey: ["document-detail-preview-sheets", workspaceId, document.id],
      });
      // Also invalidate run and document cache so updates propagate
      await queryClient.invalidateQueries({
        queryKey: ["runs"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["documents"],
      });

      setEditedRows(null);
    } catch (error: unknown) {
      console.error("Failed to save output edits:", error);
      notifyToast({
        title: error instanceof Error ? error.message : "Failed to save changes back to the database.",
        intent: "danger",
        duration: 5000,
      });
    } finally {
      setIsSaving(false);
    }
  }, [editedRows, workspaceId, document.id, document.lastRun?.id, sheet, model.selectedSheet?.index, notifyToast, queryClient]);

  const toggleSelectedAdmin = useCallback((adminId: string) => {
    setSelectedAdminIds((current) =>
      current.includes(adminId)
        ? current.filter((id) => id !== adminId)
        : [...current, adminId],
    );
  }, []);

  const handleCreateMappingRequest = useCallback(async () => {
    if (!mappingRequestContext) return;
    const trimmedMapping = requestedMapping.trim();
    if (!trimmedMapping) {
      setMappingRequestError("Enter what this column should map to.");
      return;
    }
    if (!ruleScope) {
      setMappingRequestError("Choose whether this should be signatory-specific or universal.");
      return;
    }
    if (adminsQuery.isLoading) {
      setMappingRequestError("Admin list is still loading.");
      return;
    }
    if (selectedAdmins.length === 0) {
      setMappingRequestError("Select at least one admin to notify.");
      return;
    }

    setIsCreatingMappingRequest(true);
    setMappingRequestError(null);
    try {
      const originalSample = await resolveOriginalColumnSample({
        workspaceId,
        documentId: document.id,
        context: mappingRequestContext,
      });
      const comment = buildMappingRequestComment({
        context: mappingRequestContext,
        requestedMapping: trimmedMapping,
        ruleScope,
        admins: selectedAdmins,
        originalSample,
        comments: comments.trim(),
      });

      await createDocumentActivityThread(workspaceId, document.id, {
        anchorType: "note",
        body: comment.body,
        mentions: comment.mentions,
      });

      notifyToast({
        title: "Mapping request comment created.",
        intent: "success",
        duration: 3500,
      });

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["document-activity", workspaceId, document.id] }),
        queryClient.invalidateQueries({ queryKey: ["documents-detail", workspaceId, document.id] }),
        queryClient.invalidateQueries({ queryKey: ["documents", workspaceId] }),
      ]);

      setMappingRequestContext(null);
      setRequestedMapping("");
      setRuleScope("");
      setSelectedAdminIds([]);
      setAdminPickerOpen(false);
      setFieldPickerOpen(false);
      setComments("");
    } catch (error) {
      setMappingRequestError(error instanceof Error ? error.message : "Unable to create mapping request comment.");
    } finally {
      setIsCreatingMappingRequest(false);
    }
  }, [
    adminsQuery.isLoading,
    comments,
    document.id,
    mappingRequestContext,
    notifyToast,
    queryClient,
    requestedMapping,
    ruleScope,
    selectedAdmins,
    workspaceId,
  ]);

  const isDirty = ENABLE_PREVIEW_EDITING && editedRows !== null;
  const canSubmitMappingRequest =
    Boolean(requestedMapping.trim())
    && Boolean(ruleScope)
    && selectedAdmins.length > 0
    && !adminsQuery.isLoading
    && !isCreatingMappingRequest;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-muted/10">
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90">
        {isDirty ? (
          <div className="flex justify-end border-b border-border bg-background px-4 py-2">
            <Button
              size="sm"
              variant="default"
              onClick={handleSave}
              disabled={isSaving}
              className="h-8 gap-1.5 px-3 text-xs font-medium shadow-sm transition-all bg-emerald-600 hover:bg-emerald-500 text-white"
            >
              {isSaving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        ) : null}
        {model.canLoadSelectedSource ? (
          <DocumentPreviewStatsRow
            source={source}
            onSourceChange={onSourceChange}
            showHiddenRowsAndColumns={showHiddenRowsAndColumns}
            onShowHiddenRowsAndColumnsChange={setShowHiddenRowsAndColumns}
            metrics={document.lastRunMetrics}
          />
        ) : null}
      </div>

      {!model.canLoadSelectedSource ? (
        <DocumentPreviewUnavailableState
          reason={model.normalizedState.reason ?? "Normalized output is unavailable for this document."}
          onSwitchToOriginal={() => onSourceChange("original")}
        />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 px-4 pt-0 pb-1">
            <DocumentPreviewGrid
              hasSheetError={model.hasSheetError}
              hasPreviewError={model.hasPreviewError}
              isLoading={model.isLoading}
              hasSheets={model.sheets.length > 0}
              hasData={Boolean(model.selectedSheet)}
              rows={model.previewRows}
              rowNumbers={model.rowNumbers}
              columnLabels={model.columnLabels}
              cellFormats={model.cellFormats}
              isReadOnly={!ENABLE_PREVIEW_EDITING || source === "original"}
              onRowsChange={handleRowsChange}
              onHeaderMenuClick={handleHeaderMenuClick}
              className="h-full"
            />
          </div>

          <DocumentPreviewSheetTabs
            sheets={model.sheets}
            selectedSheetName={model.selectedSheet?.name ?? null}
            isLoading={model.isLoading}
            onSheetSelect={onSheetChange}
          />
        </div>
      )}

      <Dialog
        open={mappingRequestContext !== null}
        onOpenChange={(open) => {
          if (open) return;
          setMappingRequestContext(null);
          setMappingRequestError(null);
          setAdminPickerOpen(false);
          setFieldPickerOpen(false);
          setComments("");
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create mapping request</DialogTitle>
            <DialogDescription>
              Request a custom field mapping for a column.
            </DialogDescription>
          </DialogHeader>

          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateMappingRequest();
            }}
          >
            <div className="text-xs text-muted-foreground bg-muted/20 px-3 py-2 rounded-md border border-border/50">
              Original header: <strong className="text-foreground">{mappingRequestContext?.originalHeader || "No original column found"}</strong>
            </div>

            <FormField
              label="Should map to"
              required
              error={mappingRequestError && !requestedMapping.trim() ? mappingRequestError : null}
            >
              {fieldsQuery.isLoading ? (
                <div className="text-sm text-muted-foreground animate-pulse">Loading fields...</div>
              ) : nonPlaceholderFields.length > 0 ? (
                <Popover open={fieldPickerOpen} onOpenChange={setFieldPickerOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full justify-between font-normal"
                      disabled={isCreatingMappingRequest}
                    >
                      {requestedMapping
                        ? (() => {
                            const found = nonPlaceholderFields.find((f) => f.field === requestedMapping);
                            return found ? `${found.label || found.field} (${found.field})` : requestedMapping;
                          })()
                        : "Select target field"}
                      <ChevronsUpDownIcon data-icon="inline-end" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[min(32rem,calc(100vw-2rem))] p-0" align="start">
                    <Command>
                      <CommandInput placeholder="Search fields..." />
                      <CommandList>
                        <CommandEmpty>No fields found.</CommandEmpty>
                        <CommandGroup heading="Available fields">
                          {nonPlaceholderFields.map((field) => {
                            const isSelected = requestedMapping === field.field;
                            return (
                              <CommandItem
                                key={field.field}
                                value={`${field.label || field.field} ${field.field}`}
                                onSelect={() => {
                                  setRequestedMapping(field.field);
                                  setFieldPickerOpen(false);
                                }}
                              >
                                <span className="min-w-0 flex-1">
                                  <span className="font-medium text-foreground">{field.label || field.field}</span>
                                  <span className="text-xs text-muted-foreground ml-2">({field.field})</span>
                                </span>
                                {isSelected ? <CheckIcon data-icon="inline-end" /> : null}
                              </CommandItem>
                            );
                          })}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              ) : (
                <Input
                  value={requestedMapping}
                  onChange={(event) => setRequestedMapping(event.target.value)}
                  placeholder="Enter the correct field or target column"
                  disabled={isCreatingMappingRequest}
                />
              )}
            </FormField>

            <FormField
              label="Rule scope"
              required
              error={mappingRequestError && !ruleScope ? mappingRequestError : null}
            >
              <Select
                value={ruleScope}
                onValueChange={(value) => setRuleScope(value as RuleScope)}
                disabled={isCreatingMappingRequest}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose rule scope" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="signatory">Signatory-specific rule</SelectItem>
                    <SelectItem value="universal">Universal rule</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>

            <FormField
              label="Comments"
            >
              <textarea
                value={comments}
                onChange={(event) => setComments(event.target.value)}
                placeholder="Add any additional details or notes here..."
                disabled={isCreatingMappingRequest}
                rows={3}
                className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </FormField>

            <FormField
              label="Notify admins"
              required
              error={
                mappingRequestError && selectedAdmins.length === 0
                  ? mappingRequestError
                  : adminsQuery.isError
                    ? "Unable to load workspace admins."
                    : !adminsQuery.isLoading && adminOptions.length === 0
                      ? "No workspace admins are available to notify."
                      : null
              }
            >
              <Popover open={adminPickerOpen} onOpenChange={setAdminPickerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-between"
                    disabled={isCreatingMappingRequest || adminsQuery.isLoading || adminOptions.length === 0}
                  >
                    {adminsQuery.isLoading
                      ? "Loading admins..."
                      : selectedAdmins.length > 0
                        ? `${selectedAdmins.length} admin${selectedAdmins.length === 1 ? "" : "s"} selected`
                        : "Select admins"}
                    <ChevronsUpDownIcon data-icon="inline-end" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[min(32rem,calc(100vw-2rem))] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search admins..." />
                    <CommandList>
                      <CommandEmpty>No admins found.</CommandEmpty>
                      <CommandGroup heading="Workspace admins">
                        {adminOptions.map((admin) => {
                          const isSelected = selectedAdminIds.includes(admin.id);
                          return (
                            <CommandItem
                              key={admin.id}
                              value={`${getAdminLabel(admin)} ${admin.email}`}
                              onSelect={() => toggleSelectedAdmin(admin.id)}
                              className="items-start"
                            >
                              <Checkbox checked={isSelected} aria-hidden="true" tabIndex={-1} />
                              <span className="min-w-0 flex-1">
                                <span className="block truncate font-medium">{getAdminLabel(admin)}</span>
                                <span className="block truncate text-xs text-muted-foreground">{admin.email}</span>
                              </span>
                              {isSelected ? <CheckIcon data-icon="inline-end" /> : null}
                            </CommandItem>
                          );
                        })}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </FormField>

            {selectedAdmins.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedAdmins.map((admin) => (
                  <Badge key={admin.id} variant="secondary">
                    @{getAdminLabel(admin)}
                  </Badge>
                ))}
              </div>
            ) : null}

            {mappingRequestError ? (
              <div className="text-sm font-medium text-destructive">{mappingRequestError}</div>
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setMappingRequestContext(null)}
                disabled={isCreatingMappingRequest}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!canSubmitMappingRequest || adminOptions.length === 0}
              >
                {isCreatingMappingRequest ? "Creating..." : "Create comment"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function toAdminOption(member: WorkspaceMember): AdminOption {
  return {
    id: member.user.id,
    name: member.user.display_name ?? null,
    email: member.user.email,
    roleSlugs: member.role_slugs ?? [],
  };
}

function isAdminOption(admin: AdminOption) {
  return admin.roleSlugs.some((slug) => /admin|owner|manage/i.test(slug));
}

function getAdminLabel(admin: AdminOption) {
  return admin.name?.trim() || admin.email;
}

function toPreviewString(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (
    typeof value === "number"
    || typeof value === "boolean"
    || typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function sampleColumnValues(rows: unknown[][], columnIndex: number) {
  const values = rows
    .slice(1)
    .map((row) => toPreviewString(row?.[columnIndex]).trim())
    .filter((value) => value.length > 0);

  return values.slice(0, COLUMN_SAMPLE_LIMIT);
}

async function resolveOriginalColumnSample({
  workspaceId,
  documentId,
  context,
}: {
  workspaceId: string;
  documentId: string;
  context: MappingRequestContext;
}): Promise<string[] | null> {
  if (context.source === "original") {
    return context.currentSample;
  }

  const originalColumnIndex = context.mapping?.column_index;
  if (typeof originalColumnIndex !== "number") {
    return null;
  }

  const sheetName = context.mapping?.sheet_name ?? context.sheetName;
  const sheetIndex = context.mapping?.sheet_index ?? null;
  const preview = await fetchDocumentPreview(workspaceId, documentId, {
    maxRows: 50,
    maxColumns: Math.max(originalColumnIndex + 1, 50),
    trimEmptyRows: false,
    trimEmptyColumns: false,
    ...(sheetName ? { sheetName } : typeof sheetIndex === "number" ? { sheetIndex } : {}),
  });

  return sampleColumnValues(preview.rows ?? [], originalColumnIndex);
}

function buildMappingRequestComment({
  context,
  requestedMapping,
  ruleScope,
  admins,
  originalSample,
  comments,
}: {
  context: MappingRequestContext;
  requestedMapping: string;
  ruleScope: RuleScope;
  admins: AdminOption[];
  originalSample: string[] | null;
  comments?: string;
}): {
  body: string;
  mentions: MappingRequestMention[];
} {
  const mentionParts: string[] = [];
  const mentionRanges: Array<MappingRequestMention & { codeUnitStart: number; codeUnitEnd: number }> = [];
  let mentionCursor = 0;

  admins.forEach((admin, index) => {
    if (index > 0) {
      mentionParts.push(", ");
      mentionCursor += 2;
    }
    const mentionText = `@${getAdminLabel(admin)}`;
    mentionParts.push(mentionText);
    mentionRanges.push({
      userId: admin.id,
      start: 0,
      end: 0,
      codeUnitStart: mentionCursor,
      codeUnitEnd: mentionCursor + mentionText.length,
    });
    mentionCursor += mentionText.length;
  });

  const notifyLine = `Notify: ${mentionParts.join("")}`;
  const bodyLines = [
    "Mapping request",
    "",
    notifyLine,
    `Requested mapping: ${requestedMapping}`,
    `Rule scope: ${ruleScope === "signatory" ? "Signatory-specific" : "Universal"}`,
  ];

  if (comments) {
    bodyLines.push(`Comments: ${comments}`);
  }

  bodyLines.push(
    "",
    "Column context:",
    `- Sheet: ${context.sheetName || "Unknown"}`,
    `- Preview column: ${context.columnLabel} (${context.physicalIndex + 1})`,
    `- Original header: ${context.originalHeader || "No original column found"}`,
    `- Current/final header: ${context.currentHeader || context.mappedField || "Unknown"}`,
  );

  const finalSample = context.currentSample.length > 0
    ? formatSampleValues(context.currentSample)
    : "- No sample values available";
  bodyLines.push("", "Final/current column sample:", finalSample);

  if (originalSample && originalSample.length > 0) {
    bodyLines.push("", "Original column sample:", formatSampleValues(originalSample));
  } else if (context.source === "normalized") {
    bodyLines.push("", "Original column sample:", "- Original column data unavailable");
  }

  const body = bodyLines.join("\n").slice(0, 4000);
  const notifyLineStart = body.indexOf(notifyLine);
  const mentions = mentionRanges.map((mention) => {
    const start = notifyLineStart + "Notify: ".length + mention.codeUnitStart;
    const end = notifyLineStart + "Notify: ".length + mention.codeUnitEnd;
    return {
      userId: mention.userId,
      start: codePointIndexFromCodeUnitIndex(body, start),
      end: codePointIndexFromCodeUnitIndex(body, end),
    };
  });

  return { body, mentions };
}

function formatSampleValues(values: string[]) {
  return values
    .slice(0, COLUMN_SAMPLE_LIMIT)
    .map((value, index) => `- Row ${index + 1}: ${value}`)
    .join("\n");
}

function spreadsheetColumnLabel(index: number) {
  let label = "";
  let n = index + 1;

  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }

  return label;
}
