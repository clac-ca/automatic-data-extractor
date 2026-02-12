import type { DocumentUploadRunOptions } from "@/api/documents/uploads";

import type { FileType } from "../../shared/types";

export type UploadSheetScope = "active" | "all" | "selected";

const SHEET_SELECTABLE_FILE_TYPES = new Set<FileType>(["xlsx", "xls"]);

export function supportsWorkbookSheetSelection(fileType: FileType): boolean {
  return SHEET_SELECTABLE_FILE_TYPES.has(fileType);
}

export function normalizeSheetNames(sheetNames: readonly string[]): string[] {
  const unique = new Set<string>();
  for (const value of sheetNames) {
    const normalized = value.trim();
    if (normalized.length === 0) {
      continue;
    }
    unique.add(normalized);
  }
  return Array.from(unique);
}

export function buildUploadRunOptions(
  scope: UploadSheetScope,
  selectedSheetNames: readonly string[],
): DocumentUploadRunOptions {
  const normalizedSheetNames = normalizeSheetNames(selectedSheetNames);
  if (scope === "all") {
    return { active_sheet_only: false };
  }
  if (scope === "selected" && normalizedSheetNames.length > 0) {
    return {
      active_sheet_only: false,
      input_sheet_names: normalizedSheetNames,
    };
  }
  return { active_sheet_only: true };
}
