import type { FileType } from "./types";

export function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${sizes[i]}`;
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

function fileExtension(name: string) {
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

export function formatTimestamp(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
