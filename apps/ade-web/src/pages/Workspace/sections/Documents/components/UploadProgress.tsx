import clsx from "clsx";

import type { DocumentUploadResponse } from "@api/documents";
import type { UploadManagerItem } from "@hooks/documents/uploadManager";

type UploadItem = UploadManagerItem<DocumentUploadResponse>;

export function UploadProgress({ upload }: { upload: UploadItem }) {
  const percent = Math.max(0, Math.min(100, upload.progress.percent ?? 0));
  const label = uploadStatusLabel(upload.status, percent);

  return (
    <div className="flex flex-col gap-1 text-[10px] text-muted-foreground">
      <div className="flex items-center justify-between">
        <span>{label}</span>
        {upload.status === "uploading" ? <span className="tabular-nums">{percent}%</span> : null}
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted">
        <div
          className={clsx("h-1.5 rounded-full", uploadProgressClass(upload.status))}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function uploadStatusLabel(status: UploadItem["status"], percent: number) {
  switch (status) {
    case "uploading":
      return `Uploading (${percent}%)`;
    case "succeeded":
      return "Complete";
    case "paused":
      return "Upload paused";
    case "failed":
      return "Upload failed";
    case "cancelled":
      return "Upload cancelled";
    case "queued":
      return "Queued";
    default:
      return "Uploading";
  }
}

function uploadProgressClass(status: UploadItem["status"]) {
  switch (status) {
    case "failed":
      return "bg-destructive";
    case "paused":
      return "bg-accent-foreground/60";
    case "cancelled":
      return "bg-muted-foreground/60";
    case "succeeded":
      return "bg-primary";
    default:
      return "bg-muted-foreground";
  }
}
