import clsx from "clsx";

import type { DocumentEntry } from "../types";

type UploadItem = NonNullable<DocumentEntry["upload"]>;

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
      return "bg-danger-500";
    case "paused":
      return "bg-warning-500";
    case "cancelled":
      return "bg-muted-foreground";
    case "succeeded":
      return "bg-success-500";
    default:
      return "bg-brand-500";
  }
}
