export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function formatBytes(byteSize: number): string {
  if (!Number.isFinite(byteSize) || byteSize <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(byteSize) / Math.log(1024)), units.length - 1);
  const value = byteSize / 1024 ** exponent;
  const raw = value.toFixed(value >= 10 || exponent === 0 ? 0 : 1);
  const formatted = raw.endsWith(".0") ? raw.slice(0, -2) : raw;
  return `${formatted} ${units[exponent]}`;
}
