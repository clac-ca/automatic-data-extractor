const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return dateTimeFormatter.format(date);
}

const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

export function formatByteSize(byteSize: number | null | undefined): string {
  if (byteSize === null || byteSize === undefined || Number.isNaN(byteSize)) {
    return "—";
  }
  if (byteSize <= 0) {
    return "0 B";
  }
  const base = Math.log(byteSize) / Math.log(1024);
  const index = Math.min(Math.floor(base), SIZE_UNITS.length - 1);
  const size = byteSize / 1024 ** index;
  return `${size.toFixed(index === 0 ? 0 : 1)} ${SIZE_UNITS[index]}`;
}

export function formatDocumentStatus(status: string): string {
  if (status === "deleted") {
    return "Deleted";
  }
  return "Active";
}
