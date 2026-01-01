import type {
  DocumentLastRun,
  DocumentListRow,
  DocumentRecord,
  FileType,
  RunResource,
  WorkbookPreview,
  WorkbookSheet,
} from "./types";

export const numberFormatter = new Intl.NumberFormat("en-US");
export const MAX_PREVIEW_ROWS = 200;
export const DEFAULT_BOARD_ID = "default";
export const DEFAULT_BOARD_LABEL = "Default board";
export function formatRelativeTime(nowTimestamp: number, timestamp: number | string | null | undefined) {
  const resolved =
    typeof timestamp === "number" ? timestamp : typeof timestamp === "string" ? Date.parse(timestamp) : NaN;
  const base = Number.isNaN(resolved) ? nowTimestamp : resolved;
  const diff = Math.max(0, nowTimestamp - base);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function parseTimestamp(value: string | null | undefined) {
  const parsed = value ? Date.parse(value) : NaN;
  return Number.isNaN(parsed) ? Date.now() : parsed;
}

export function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${sizes[i]}`;
}

export function normalizeBoardId(value: string) {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized.length > 0 ? normalized : null;
}

export function formatBoardLabel(value: string) {
  const normalized = normalizeBoardId(value);
  if (!normalized) return DEFAULT_BOARD_LABEL;
  return normalized
    .split(/[-_]+/g)
    .filter(Boolean)
    .map((segment) => segment[0]?.toUpperCase() + segment.slice(1))
    .join(" ");
}

export function buildNormalizedFilename(name: string) {
  const base = name.replace(/\.[^.]+$/, "");
  return `${base}_normalized.xlsx`;
}

export function extractFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) return null;
  const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
}

export function triggerDownload(blob: Blob, fileName: string) {
  if (typeof window === "undefined") return;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
}

export function normalizeCell(value: unknown) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value instanceof Date) return value.toLocaleDateString();
  return String(value);
}

export function normalizeRow(row: string[], length: number) {
  return Array.from({ length }, (_, index) => row[index] ?? "");
}

export function buildHeaders(raw: string[], totalColumns: number) {
  const trimmed = raw.map((cell) => cell.trim());
  const hasNamed = trimmed.some(Boolean);
  const headerCount = Math.max(trimmed.length, totalColumns);
  const headers = hasNamed ? trimmed : Array.from({ length: headerCount }, (_, index) => columnLabel(index));
  return normalizeRow(headers, headerCount);
}

export function columnLabel(index: number) {
  let label = "";
  let n = index + 1;
  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }
  return `Column ${label}`;
}

export function shortId(value: string, length = 8) {
  if (!value) return "";
  return value.slice(0, Math.max(4, length));
}

export async function copyToClipboard(text: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.top = "-1000px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

export function fileTypeFromName(name: string): FileType {
  const lower = name.toLowerCase();
  if (lower.endsWith(".xlsx")) return "xlsx";
  if (lower.endsWith(".xls")) return "xls";
  if (lower.endsWith(".csv")) return "csv";
  if (lower.endsWith(".pdf")) return "pdf";
  return "unknown";
}

export function fileTypeLabel(type: FileType) {
  switch (type) {
    case "xlsx":
      return "XLSX";
    case "xls":
      return "XLS";
    case "csv":
      return "CSV";
    case "pdf":
      return "PDF";
    default:
      return "File";
  }
}

export function fileExtension(name: string) {
  const match = name.toLowerCase().match(/\.([a-z0-9]+)$/);
  return match?.[1] ?? "";
}

export function inferFileType(name: string, contentType?: string | null): FileType {
  const ext = fileExtension(name);
  if (ext === "xlsx") return "xlsx";
  if (ext === "xls") return "xls";
  if (ext === "csv") return "csv";
  if (ext === "pdf") return "pdf";

  const ct = (contentType ?? "").toLowerCase();
  if (ct.includes("spreadsheetml")) return "xlsx";
  if (ct.includes("ms-excel")) return "xls";
  if (ct.includes("csv")) return "csv";
  if (ct.includes("pdf")) return "pdf";
  return "unknown";
}

export function stableId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

export function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export async function fetchWorkbookPreview(url: string, signal?: AbortSignal): Promise<WorkbookPreview> {
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) throw new Error("Unable to fetch processed workbook.");

  const buffer = await response.arrayBuffer();
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });

  const sheets = workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, blankrows: false }) as unknown[][];
    const totalRows = rows.length;
    const totalColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const truncatedRows = totalRows > MAX_PREVIEW_ROWS;

    const visibleRows = rows.slice(0, MAX_PREVIEW_ROWS).map((row) => row.map((cell) => normalizeCell(cell)));

    const columnCount = Math.max(visibleRows[0]?.length ?? 0, totalColumns, 1);
    const headers = buildHeaders(visibleRows[0] ?? [], columnCount);
    const bodyRows = visibleRows.slice(1).map((row) => normalizeRow(row as string[], headers.length));

    return {
      name,
      headers,
      rows: bodyRows as string[][],
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns: false,
    } satisfies WorkbookSheet;
  });

  return { sheets };
}

export async function downloadOriginalDocument(
  workspaceId: string,
  documentId: string,
  fallbackName: string,
): Promise<string> {
  const response = await fetch(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/download`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error("Unable to download original file.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? fallbackName;
  triggerDownload(blob, filename);
  return filename;
}

export async function downloadRunOutput(outputDownloadUrl: string, fallbackName: string): Promise<string> {
  const response = await fetch(outputDownloadUrl, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to download processed output.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? buildNormalizedFilename(fallbackName);
  triggerDownload(blob, filename);
  return filename;
}

export async function downloadRunOutputById(runId: string, fallbackName: string): Promise<string> {
  const response = await fetch(`/api/v1/runs/${runId}/output/download`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to download processed output.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? buildNormalizedFilename(fallbackName);
  triggerDownload(blob, filename);
  return filename;
}

export function runOutputDownloadUrl(run: RunResource): string | null {
  if (run.output?.download_url) return run.output.download_url;
  if (run.links?.output_download) return run.links.output_download;
  return null;
}

export function runHasDownloadableOutput(run: RunResource | null) {
  if (!run) return false;
  if (run.status !== "succeeded") return false;
  return Boolean(runOutputDownloadUrl(run));
}

export function getDocumentOutputRun(document: DocumentListRow | DocumentRecord | null | undefined): DocumentLastRun | null {
  if (!document) return null;
  if (document.last_successful_run) return document.last_successful_run;
  if (document.last_run?.status === "succeeded") return document.last_run;
  return null;
}
