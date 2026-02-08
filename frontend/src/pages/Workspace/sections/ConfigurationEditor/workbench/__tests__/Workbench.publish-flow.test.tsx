import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunCompletionInfo } from "../state/useRunSessionModel";
import type { WorkbenchFileTab } from "../types";
import { WorkbenchConsoleStore } from "../state/consoleStore";

const invalidateQueriesMock = vi.fn();
const navigateMock = vi.fn();

let onRunCompleteCallback: ((info: RunCompletionInfo) => void) | undefined;
const startRunMock = vi.fn(async () => ({ runId: "run-123", startedAt: "2026-02-07T10:00:00.000Z" }));
let mockConfigStatus: "draft" | "active" | "archived" = "draft";
let mockEditableCapability = true;
let mockFilesFetchedAfterMount = true;
let mockConfigFetchedAfterMount = true;

const filesQueryRefetchMock = vi.fn(async () => ({
  data: {
    status: "active",
    capabilities: { editable: false },
  },
}));
const configurationsQueryRefetchMock = vi.fn(async () => ({ data: { items: [] } }));

const baseTab: WorkbenchFileTab = {
  id: "manifest.toml",
  name: "manifest.toml",
  initialContent: "name='demo'\n",
  content: "name='demo'\n",
  status: "ready",
  etag: null,
  error: null,
  saving: false,
  saveError: null,
  lastSavedAt: null,
  metadata: null,
};

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("../state/useWorkbenchUrlState", () => ({
  useWorkbenchUrlState: () => ({
    fileId: "manifest.toml",
    pane: "terminal",
    console: "closed",
    panel: "none",
    historyScope: "workspace",
    historyFilter: "all",
    versionId: undefined,
    mode: "live",
    returnToId: undefined,
    sourceVersionId: undefined,
    consoleExplicit: false,
    setFileId: vi.fn(),
    setPane: vi.fn(),
    setConsole: vi.fn(),
    setHistoryFilter: vi.fn(),
    setVersionId: vi.fn(),
    setMode: vi.fn(),
    patchState: vi.fn(),
  }),
}));

vi.mock("@/pages/Workspace/hooks/configurations", () => ({
  configurationKeys: {
    files: (workspaceId: string, configId: string) => ["workspaces", workspaceId, "configurations", configId, "files"],
    detail: (workspaceId: string, configId: string) => ["workspaces", workspaceId, "configurations", configId],
    root: (workspaceId: string) => ["workspaces", workspaceId, "configurations"],
    historyWorkspace: (workspaceId: string) => ["workspaces", workspaceId, "configurations", "history", "workspace"],
    file: (workspaceId: string, configId: string, path: string) => [
      "workspaces",
      workspaceId,
      "configurations",
      configId,
      "files",
      path,
    ],
  },
  useConfigurationFilesQuery: () => ({
    data: {
      status: mockConfigStatus,
      fileset_hash: "fileset",
      capabilities: { editable: mockEditableCapability },
      entries: [],
    },
    isLoading: false,
    isError: false,
    isSuccess: true,
    isFetchedAfterMount: mockFilesFetchedAfterMount,
    refetch: filesQueryRefetchMock,
  }),
  useConfigurationQuery: () => ({
    data: {
      id: "cfg-1",
      display_name: "Config",
      status: mockConfigStatus,
      updated_at: "2026-02-07T10:00:00.000Z",
    },
    isLoading: false,
    isError: false,
    isSuccess: true,
    isFetchedAfterMount: mockConfigFetchedAfterMount,
    refetch: vi.fn(),
  }),
  useConfigurationsQuery: () => ({
    data: {
      items: [
        { id: "active-1", display_name: "Active Config", status: "active" },
        { id: "draft-1", display_name: "Draft Config", status: "draft" },
      ],
    },
    refetch: configurationsQueryRefetchMock,
  }),
  useDuplicateConfigurationMutation: () => ({
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: false,
  }),
  useCreateConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useArchiveConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useReplaceConfigurationMutation: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useSaveConfigurationFileMutation: () => ({
    mutateAsync: vi.fn(),
  }),
  useConfigurationWorkspaceHistoryQuery: () => ({
    data: null,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRestoreConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useUpdateConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("../state/useWorkbenchFiles", () => ({
  useWorkbenchFiles: () => ({
    tabs: [baseTab],
    activeTab: baseTab,
    activeTabId: baseTab.id,
    isDirty: false,
    updateContent: vi.fn(),
    replaceTabContent: vi.fn(),
    beginSavingTab: vi.fn(),
    completeSavingTab: vi.fn(),
    failSavingTab: vi.fn(),
    openFile: vi.fn(),
    selectTab: vi.fn(),
    closeTab: vi.fn(),
    closeOtherTabs: vi.fn(),
    closeTabsToRight: vi.fn(),
    closeAllTabs: vi.fn(),
    moveTab: vi.fn(),
    reloadTab: vi.fn(),
    pinTab: vi.fn(),
    unpinTab: vi.fn(),
    selectRecentTab: vi.fn(),
  }),
}));

vi.mock("../state/useUnsavedChangesGuard", () => ({
  useUnsavedChangesGuard: vi.fn(),
}));

vi.mock("../utils/tree", () => ({
  createWorkbenchTreeFromListing: () => ({
    id: "root",
    name: "root",
    kind: "folder",
    children: [{ id: "manifest.toml", name: "manifest.toml", kind: "file" }],
  }),
  findFileNode: () => ({ id: "manifest.toml" }),
  findFirstFile: () => ({ id: "manifest.toml" }),
}));

vi.mock("../utils/workbenchHelpers", () => ({
  decodeFileContent: () => "",
  describeError: () => "error",
  formatRelative: () => "now",
  formatWorkspaceLabel: () => "workspace",
}));

vi.mock("@/providers/theme", () => ({
  useTheme: () => ({ resolvedMode: "light" }),
  isDarkMode: () => false,
}));

vi.mock("@/providers/notifications", () => ({
  useNotifications: () => ({
    notifyBanner: vi.fn(),
    dismissScope: vi.fn(),
    notifyToast: vi.fn(),
  }),
}));

vi.mock("@/api/configurations/api", () => ({
  exportConfiguration: vi.fn(),
  readConfigurationFileJson: vi.fn(),
}));

vi.mock("../components/BottomPanel", () => ({
  BottomPanel: () => <div data-testid="bottom-panel" />,
}));

vi.mock("../components/EditorArea", () => ({
  EditorArea: () => <div data-testid="editor-area" />,
}));

vi.mock("../components/RunExtractionDialog", () => ({
  RunExtractionDialog: () => <div data-testid="run-extraction-dialog" />,
}));

vi.mock("../components/WorkbenchLayoutSync", () => ({
  WorkbenchLayoutSync: () => null,
}));

vi.mock("../components/WorkbenchSidebar", () => ({
  WorkbenchSidebar: () => <div data-testid="workbench-sidebar" />,
}));

vi.mock("../components/WorkbenchSidebarResizeHandle", () => ({
  WorkbenchSidebarResizeHandle: () => <div data-testid="sidebar-resize-handle" />,
}));

vi.mock("../components/WorkbenchChrome", () => ({
  WorkbenchChrome: ({
    canPublish,
    onPublish,
    consoleToggleDisabled,
  }: {
    canPublish: boolean;
    onPublish: () => void;
    consoleToggleDisabled?: boolean;
  }) => (
    <div>
      <button data-testid="chrome-publish" onClick={onPublish} disabled={!canPublish}>
        Publish
      </button>
      <span data-testid="console-toggle-disabled">{consoleToggleDisabled ? "yes" : "no"}</span>
    </div>
  ),
}));

vi.mock("../components/WorkbenchGuidedTour", () => ({
  WorkbenchGuidedTour: () => null,
}));

vi.mock("../components/PublishConfigurationDialog", () => ({
  PublishConfigurationDialog: ({
    open,
    phase,
    errorMessage,
    onStartPublish,
    onRetryPublish,
    onDone,
  }: {
    open: boolean;
    phase: string;
    errorMessage?: string | null;
    onStartPublish: () => void;
    onRetryPublish: () => void;
    onDone: () => void;
  }) =>
    open ? (
      <div data-testid="publish-dialog" data-phase={phase}>
        {errorMessage ? <p>{errorMessage}</p> : null}
        <button onClick={onStartPublish}>Start publish</button>
        <button onClick={onRetryPublish}>Retry publish</button>
        <button onClick={onDone}>Done</button>
      </div>
    ) : null,
}));

vi.mock("@/components/ui/context-menu-simple", () => ({
  ContextMenu: () => null,
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
  ConfirmDialog: () => null,
}));

vi.mock("@/components/layout", () => ({
  PageState: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../state/useRunSessionModel", () => ({
  useRunSessionModel: (options: { onRunComplete?: (info: RunCompletionInfo) => void }) => {
    onRunCompleteCallback = options.onRunComplete;
    return {
      runStatus: "idle",
      runConnectionState: "connecting",
      runMode: undefined,
      runInProgress: false,
      validation: { status: "idle", messages: [], lastRunAt: undefined, error: null, digest: null },
      console: new WorkbenchConsoleStore(128),
      latestRun: null,
      clearConsole: vi.fn(),
      startRun: startRunMock,
    };
  },
}));

import { Workbench } from "../Workbench";

describe("Workbench publish flow", () => {
  beforeEach(() => {
    onRunCompleteCallback = undefined;
    startRunMock.mockClear();
    invalidateQueriesMock.mockClear();
    filesQueryRefetchMock.mockClear();
    configurationsQueryRefetchMock.mockClear();
    mockConfigStatus = "draft";
    mockEditableCapability = true;
    mockFilesFetchedAfterMount = true;
    mockConfigFetchedAfterMount = true;
  });

  it("opens publish dialog, starts publish, and flips to read-only on success", async () => {
    render(
      <Workbench
        workspaceId="ws-1"
        configId="cfg-1"
        configDisplayName="Draft"
        onCloseWorkbench={vi.fn()}
      />,
    );

    expect(screen.getByTestId("chrome-publish")).toBeEnabled();
    fireEvent.click(screen.getByTestId("chrome-publish"));
    expect(screen.getByTestId("publish-dialog")).toHaveAttribute("data-phase", "confirm");

    fireEvent.click(screen.getByText("Start publish"));
    await waitFor(() => {
      expect(startRunMock).toHaveBeenCalledWith({ operation: "publish" }, { mode: "publish" });
    });

    await act(async () => {
      onRunCompleteCallback?.({
        runId: "run-123",
        status: "succeeded",
        mode: "publish",
        payload: { status: "succeeded" },
      });
    });

    expect(screen.getByTestId("publish-dialog")).toHaveAttribute("data-phase", "succeeded");
    expect(screen.getByText("Read-only configuration")).toBeInTheDocument();
    expect(screen.getByTestId("chrome-publish")).toBeDisabled();
    expect(screen.getByTestId("console-toggle-disabled").textContent).toBe("yes");
  });

  it("shows failure and keeps draft editable with retry support", async () => {
    render(
      <Workbench
        workspaceId="ws-1"
        configId="cfg-1"
        configDisplayName="Draft"
        onCloseWorkbench={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("chrome-publish"));
    fireEvent.click(screen.getByText("Start publish"));

    await act(async () => {
      onRunCompleteCallback?.({
        runId: "run-123",
        status: "failed",
        mode: "publish",
        payload: { error_message: "stale snapshot" },
      });
    });

    expect(screen.getByTestId("publish-dialog")).toHaveAttribute("data-phase", "failed");
    expect(screen.getByText("Publish failed: stale snapshot")).toBeInTheDocument();
    expect(screen.getByTestId("chrome-publish")).toBeEnabled();

    fireEvent.click(screen.getByText("Retry publish"));
    await waitFor(() => {
      expect(startRunMock).toHaveBeenCalledTimes(2);
    });
  });

  it("treats active configs as read-only even if editable capability drifts true", () => {
    mockConfigStatus = "active";
    mockEditableCapability = true;

    render(
      <Workbench
        workspaceId="ws-1"
        configId="cfg-1"
        configDisplayName="Active"
        onCloseWorkbench={vi.fn()}
      />,
    );

    expect(screen.getByText("Read-only configuration")).toBeInTheDocument();
    expect(screen.getByTestId("chrome-publish")).toBeDisabled();
  });

  it("waits for a fresh file status snapshot before showing editor actions", () => {
    mockFilesFetchedAfterMount = false;

    render(
      <Workbench
        workspaceId="ws-1"
        configId="cfg-1"
        configDisplayName="Draft"
        onCloseWorkbench={vi.fn()}
      />,
    );

    expect(screen.getByText("Refreshing configuration")).toBeInTheDocument();
  });

  it("waits for a fresh configuration status snapshot before showing editor actions", () => {
    mockConfigFetchedAfterMount = false;

    render(
      <Workbench
        workspaceId="ws-1"
        configId="cfg-1"
        configDisplayName="Draft"
        onCloseWorkbench={vi.fn()}
      />,
    );

    expect(screen.getByText("Refreshing configuration")).toBeInTheDocument();
  });
});
