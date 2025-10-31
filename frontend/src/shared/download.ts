export interface DownloadPayload {
  readonly blob: Blob;
  readonly filename: string;
}

export function downloadBlob({ blob, filename }: DownloadPayload) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
