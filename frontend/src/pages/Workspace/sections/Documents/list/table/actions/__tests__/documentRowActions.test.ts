import { describe, expect, it, vi } from "vitest";

import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { buildDocumentRowActions } from "../documentRowActions";

function makeDocument(): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "source.csv",
    fileType: "csv",
    byteSize: 16,
    commentCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    tags: [],
    assignee: {
      id: "user_other",
      name: "Other",
      email: "other@example.com",
    },
    lastRun: {
      id: "run_1",
      status: "failed",
      createdAt: "2026-01-01T00:00:00Z",
      startedAt: "2026-01-01T00:01:00Z",
      completedAt: "2026-01-01T00:02:00Z",
      errorMessage: "engine failed",
    },
  } as DocumentRow;
}

describe("buildDocumentRowActions", () => {
  it("keeps core action parity between overflow and context menus", () => {
    const document = makeDocument();
    const handlers = {
      onOpen: vi.fn(),
      onOpenPreview: vi.fn(),
      onDownloadLatest: vi.fn(),
      onDownloadOriginal: vi.fn(),
      onDownloadEventsLog: vi.fn(),
      onAssignToMe: vi.fn(),
      onRename: vi.fn(),
      onDeleteRequest: vi.fn(),
    };

    const overflow = buildDocumentRowActions({
      document,
      lifecycle: "active",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: true,
      surface: "overflow",
      onDownloadLatest: handlers.onDownloadLatest,
      onDownloadOriginal: handlers.onDownloadOriginal,
      onDownloadEventsLog: handlers.onDownloadEventsLog,
      onAssignToMe: handlers.onAssignToMe,
      onRename: handlers.onRename,
      onDeleteRequest: handlers.onDeleteRequest,
    });

    const context = buildDocumentRowActions({
      document,
      lifecycle: "active",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: true,
      surface: "context",
      onOpen: handlers.onOpen,
      onOpenPreview: handlers.onOpenPreview,
      onDownloadLatest: handlers.onDownloadLatest,
      onDownloadOriginal: handlers.onDownloadOriginal,
      onAssignToMe: handlers.onAssignToMe,
      onRename: handlers.onRename,
      onDeleteRequest: handlers.onDeleteRequest,
    });

    expect(context.map((item) => item.id).slice(0, 2)).toEqual(["open", "open-preview"]);
    expect(context.find((item) => item.id === "download-events-log")).toBeUndefined();
    expect(context.filter((item) => !["open", "open-preview"].includes(item.id)).map((item) => item.id)).toEqual(
      overflow.filter((item) => item.id !== "download-events-log").map((item) => item.id),
    );
  });

  it("keeps archive-only actions hidden for archived documents", () => {
    const document = makeDocument();
    const actions = buildDocumentRowActions({
      document,
      lifecycle: "archived",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: false,
      surface: "overflow",
      onDownloadLatest: vi.fn(),
      onDownloadOriginal: vi.fn(),
      onDownloadEventsLog: vi.fn(),
      onAssignToMe: vi.fn(),
      onRename: vi.fn(),
      onDeleteRequest: vi.fn(),
    });

    expect(actions.map((item) => item.id)).toEqual([
      "download",
      "download-original",
      "download-events-log",
      "assign-to-me",
    ]);
  });

  it("shows restore instead of archive for archived documents", () => {
    const document = makeDocument();
    const actions = buildDocumentRowActions({
      document,
      lifecycle: "archived",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: true,
      surface: "overflow",
      onDownloadLatest: vi.fn(),
      onDownloadOriginal: vi.fn(),
      onDownloadEventsLog: vi.fn(),
      onAssignToMe: vi.fn(),
      onRename: vi.fn(),
      onDeleteRequest: vi.fn(),
      onRestoreRequest: vi.fn(),
    });

    expect(actions.find((item) => item.id === "delete")).toBeUndefined();
    expect(actions.find((item) => item.id === "restore")?.label).toBe("Restore");
  });

  it("hides assign-to-me when already assigned to current user", () => {
    const document = makeDocument();
    const actions = buildDocumentRowActions({
      document,
      lifecycle: "active",
      isBusy: false,
      isSelfAssigned: true,
      canRenameInline: true,
      surface: "overflow",
      onAssignToMe: vi.fn(),
    });

    expect(actions.find((item) => item.id === "assign-to-me")).toBeUndefined();
  });

  it("hides the overflow events log action when the document has no last run", () => {
    const document = {
      ...makeDocument(),
      lastRun: null,
    } as DocumentRow;

    const actions = buildDocumentRowActions({
      document,
      lifecycle: "active",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: true,
      surface: "overflow",
      onDownloadLatest: vi.fn(),
      onDownloadOriginal: vi.fn(),
      onDownloadEventsLog: vi.fn(),
      onAssignToMe: vi.fn(),
      onRename: vi.fn(),
      onDeleteRequest: vi.fn(),
    });

    expect(actions.find((item) => item.id === "download-events-log")).toBeUndefined();
  });
});
