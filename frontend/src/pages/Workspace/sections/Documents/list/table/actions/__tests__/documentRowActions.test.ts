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
    lastRun: null,
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
    expect(context.filter((item) => !["open", "open-preview"].includes(item.id)).map((item) => item.id)).toEqual(
      overflow.map((item) => item.id),
    );
  });

  it("gates lifecycle-only actions for deleted documents", () => {
    const document = makeDocument();
    const actions = buildDocumentRowActions({
      document,
      lifecycle: "deleted",
      isBusy: false,
      isSelfAssigned: false,
      canRenameInline: false,
      surface: "overflow",
      onDownloadLatest: vi.fn(),
      onDownloadOriginal: vi.fn(),
      onAssignToMe: vi.fn(),
      onRename: vi.fn(),
      onDeleteRequest: vi.fn(),
    });

    expect(actions.map((item) => item.id)).toEqual(["download", "download-original"]);
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
});
