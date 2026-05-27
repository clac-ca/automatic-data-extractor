import type { ComponentProps } from "react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen, waitFor, within } from "@/test/test-utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentPreviewTab } from "../DocumentPreviewTab";

const createDocumentActivityThreadMock = vi.fn();
const fetchDocumentPreviewMock = vi.fn();
const listWorkspaceMembersMock = vi.fn();
const notifyToastMock = vi.fn();

vi.mock("@/api/documents", async () => {
  const actual = await vi.importActual<typeof import("@/api/documents")>("@/api/documents");
  return {
    ...actual,
    createDocumentActivityThread: (...args: unknown[]) => createDocumentActivityThreadMock(...args),
    fetchDocumentPreview: (...args: unknown[]) => fetchDocumentPreviewMock(...args),
  };
});

vi.mock("@/api/workspaces/api", async () => {
  const actual = await vi.importActual<typeof import("@/api/workspaces/api")>("@/api/workspaces/api");
  return {
    ...actual,
    listWorkspaceMembers: (...args: unknown[]) => listWorkspaceMembersMock(...args),
  };
});

vi.mock("@/providers/notifications", async () => {
  const actual = await vi.importActual<typeof import("@/providers/notifications")>("@/providers/notifications");
  return {
    ...actual,
    useNotifications: () => ({
      notifyToast: notifyToastMock,
    }),
  };
});

vi.mock("../hooks/usePreviewDisplayPreferences", () => ({
  usePreviewDisplayPreferences: () => ({
    preferences: {
      trimEmptyRows: false,
      trimEmptyColumns: false,
      showHiddenRowsAndColumns: false,
    },
    showHiddenRowsAndColumns: false,
    setShowHiddenRowsAndColumns: vi.fn(),
  }),
}));

vi.mock("../hooks/useDocumentPreviewModel", () => ({
  useDocumentPreviewModel: () => ({
    canLoadSelectedSource: true,
    normalizedState: { reason: null },
    hasSheetError: false,
    hasPreviewError: false,
    isLoading: false,
    sheets: [{ name: "Intake", index: 0, kind: "worksheet", is_active: true }],
    selectedSheet: { name: "Intake", index: 0, kind: "worksheet", is_active: true },
    previewRows: [
      ["Email Address"],
      ["final-a@example.com"],
      ["final-b@example.com"],
    ],
    rowNumbers: [1, 2, 3],
    visibleIndices: [0],
    columnLabels: ["A"],
    cellFormats: [],
    previewCountSummary: null,
  }),
}));

vi.mock("../components/DocumentPreviewGrid", () => ({
  DocumentPreviewGrid: (props: ComponentProps<"div"> & { onHeaderMenuClick?: (index: number) => void }) => (
    <button type="button" onClick={() => props.onHeaderMenuClick?.(0)}>
      Add mapping request
    </button>
  ),
}));

vi.mock("../components/DocumentPreviewHeader", () => ({
  DocumentPreviewHeader: () => <div data-testid="preview-header" />,
}));

vi.mock("../components/DocumentPreviewStatsRow", () => ({
  DocumentPreviewStatsRow: () => <div data-testid="preview-stats" />,
}));

vi.mock("../components/DocumentPreviewSheetTabs", () => ({
  DocumentPreviewSheetTabs: () => <div data-testid="preview-sheets" />,
}));

vi.mock("../components/DocumentPreviewUnavailableState", () => ({
  DocumentPreviewUnavailableState: () => <div data-testid="preview-unavailable" />,
}));

function createDocument(): DocumentRow {
  return {
    id: "doc-1",
    workspaceId: "ws-1",
    name: "example.xlsx",
    fileType: "xlsx",
    byteSize: 20,
    commentCount: 0,
    tags: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    lastRun: { id: "run-1", operation: "process", status: "succeeded", createdAt: "2026-01-01T00:00:00Z" },
    lastRunMetrics: null,
    lastRunTableColumns: [
      {
        workbook_index: 0,
        workbook_name: "example.xlsx",
        sheet_index: 0,
        sheet_name: "Intake",
        table_index: 0,
        column_index: 2,
        header_raw: "Worker Email",
        header_normalized: "worker_email",
        non_empty_cells: 2,
        valid_cells: 2,
        mapping_status: "mapped",
        mapped_field: "Email Address",
        mapping_score: 1,
        mapping_method: "classifier",
        unmapped_reason: null,
      },
    ],
    lastRunFields: null,
  } as DocumentRow;
}

function createAdminMember(id: string, displayName: string, email: string, roleSlugs: string[]) {
  return {
    user_id: id,
    role_ids: [`role-${id}`],
    role_slugs: roleSlugs,
    created_at: "2026-01-01T00:00:00Z",
    user: {
      id,
      email,
      display_name: displayName,
    },
    access_mode: "direct",
    is_directly_managed: true,
    sources: [],
  };
}

describe("DocumentPreviewTab mapping requests", () => {
  beforeEach(() => {
    createDocumentActivityThreadMock.mockReset();
    fetchDocumentPreviewMock.mockReset();
    listWorkspaceMembersMock.mockReset();
    notifyToastMock.mockReset();

    createDocumentActivityThreadMock.mockResolvedValue({});
    fetchDocumentPreviewMock.mockResolvedValue({
      name: "Intake",
      index: 0,
      rows: [
        ["A", "B", "Worker Email"],
        ["x", "y", "original-a@example.com"],
        ["x", "y", "original-b@example.com"],
      ],
      totalRows: 3,
      totalColumns: 3,
      truncatedRows: false,
      truncatedColumns: false,
    });
    listWorkspaceMembersMock.mockResolvedValue({
      items: [
        createAdminMember("admin-1", "Ada Admin", "ada@example.com", ["workspace-admin"]),
        createAdminMember("member-1", "Member User", "member@example.com", ["viewer"]),
      ],
      meta: {
        limit: 2,
        hasMore: false,
        nextCursor: null,
        totalIncluded: true,
        totalCount: 2,
        changesCursor: "0",
      },
      facets: null,
    });
  });

  it("requires admin notification and creates a formatted mapping comment with mentions", async () => {
    const user = userEvent.setup();
    render(
      <DocumentPreviewTab
        workspaceId="ws-1"
        document={createDocument()}
        source="normalized"
        sheet={null}
        onSourceChange={vi.fn()}
        onSheetChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Add mapping request" }));

    expect(await screen.findByRole("dialog", { name: "Create mapping request" })).toBeInTheDocument();
    expect(screen.getByText("Worker Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create comment" })).toBeDisabled();

    await user.type(screen.getByLabelText(/Should map to/), "employee_email");
    await user.click(screen.getByRole("combobox"));
    await waitFor(() => {
      expect(screen.getAllByText("Signatory-specific rule").length).toBeGreaterThan(0);
    });
    await user.click(screen.getAllByText("Signatory-specific rule").at(-1)!);
    expect(screen.getByRole("button", { name: "Create comment" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Select admins" }));
    const adminOption = await screen.findByText("Ada Admin");
    await user.click(adminOption);
    expect(screen.getByText("@Ada Admin")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create comment" }));

    await waitFor(() => {
      expect(createDocumentActivityThreadMock).toHaveBeenCalledTimes(1);
    });

    expect(fetchDocumentPreviewMock).toHaveBeenCalledWith(
      "ws-1",
      "doc-1",
      expect.objectContaining({
        sheetName: "Intake",
        trimEmptyRows: false,
        trimEmptyColumns: false,
      }),
    );

    const [, , payload] = createDocumentActivityThreadMock.mock.calls[0];
    expect(payload).toEqual(
      expect.objectContaining({
        anchorType: "note",
        mentions: [expect.objectContaining({ userId: "admin-1" })],
      }),
    );
    expect(payload.body).toContain("Mapping request");
    expect(payload.body).toContain("Notify: @Ada Admin");
    expect(payload.body).toContain("Requested mapping: employee_email");
    expect(payload.body).toContain("Rule scope: Signatory-specific");
    expect(payload.body).toContain("- Original header: Worker Email");
    expect(payload.body).toContain("- Current/final header: Email Address");
    expect(payload.body).toContain("Final/current column sample:");
    expect(payload.body).toContain("final-a@example.com");
    expect(payload.body).toContain("Original column sample:");
    expect(payload.body).toContain("original-a@example.com");

    const mention = payload.mentions[0];
    const mentionText = Array.from(payload.body).slice(mention.start, mention.end).join("");
    expect(mentionText).toBe("@Ada Admin");
    expect(notifyToastMock).toHaveBeenCalledWith(expect.objectContaining({ intent: "success" }));
  });

  it("blocks comment creation when no workspace admins are available", async () => {
    listWorkspaceMembersMock.mockResolvedValue({
      items: [createAdminMember("member-1", "Member User", "member@example.com", ["viewer"])],
      meta: {
        limit: 1,
        hasMore: false,
        nextCursor: null,
        totalIncluded: true,
        totalCount: 1,
        changesCursor: "0",
      },
      facets: null,
    });

    const user = userEvent.setup();
    render(
      <DocumentPreviewTab
        workspaceId="ws-1"
        document={createDocument()}
        source="normalized"
        sheet={null}
        onSourceChange={vi.fn()}
        onSheetChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Add mapping request" }));

    const dialog = await screen.findByRole("dialog", { name: "Create mapping request" });
    await waitFor(() => {
      expect(within(dialog).getByText("No workspace admins are available to notify.")).toBeInTheDocument();
    });
    expect(within(dialog).getByRole("button", { name: "Create comment" })).toBeDisabled();
  });
});
