import { describe, expect, it, vi } from "vitest";

import { fireEvent, render, screen } from "@test/test-utils";
import type { DocumentUploadResponse } from "@shared/documents";
import type { UploadManagerItem, UploadManagerSummary } from "@shared/documents/uploadManager";

import { UploadManager } from "./UploadManager";

function buildItem(id: string, file: File, status: UploadManagerItem<DocumentUploadResponse>["status"], percent: number) {
  return {
    id,
    file,
    status,
    progress: {
      loaded: Math.round((file.size || 0) * (percent / 100)),
      total: file.size || 0,
      percent,
    },
  } satisfies UploadManagerItem<DocumentUploadResponse>;
}

describe("UploadManager", () => {
  it("renders upload list and actions", () => {
    const onPause = vi.fn();
    const onResume = vi.fn();
    const onRetry = vi.fn();
    const onCancel = vi.fn();
    const onRemove = vi.fn();
    const onClearCompleted = vi.fn();

    const fileA = new File(["hello"], "alpha.csv", { type: "text/csv" });
    const fileB = new File(["world"], "beta.csv", { type: "text/csv" });

    const items: UploadManagerItem<DocumentUploadResponse>[] = [
      buildItem("upload-1", fileA, "uploading", 50),
      buildItem("upload-2", fileB, "queued", 0),
    ];

    const summary: UploadManagerSummary = {
      totalCount: 2,
      queuedCount: 1,
      uploadingCount: 1,
      pausedCount: 0,
      succeededCount: 0,
      failedCount: 0,
      cancelledCount: 0,
      completedCount: 0,
      totalBytes: fileA.size + fileB.size,
      uploadedBytes: Math.round(fileA.size / 2),
      percent: 50,
      inFlightCount: 1,
    };

    render(
      <UploadManager
        items={items}
        summary={summary}
        onPause={onPause}
        onResume={onResume}
        onRetry={onRetry}
        onCancel={onCancel}
        onRemove={onRemove}
        onClearCompleted={onClearCompleted}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /in progress/i }));

    expect(screen.getByText("Upload manager")).toBeInTheDocument();
    expect(screen.getByText("alpha.csv")).toBeInTheDocument();
    expect(screen.getByText("beta.csv")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(onPause).toHaveBeenCalledWith("upload-1");
  });
});
