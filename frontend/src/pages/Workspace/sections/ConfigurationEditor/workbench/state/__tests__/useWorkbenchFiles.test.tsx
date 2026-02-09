import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkbenchFileNode } from "../../types";
import { useWorkbenchFiles } from "../useWorkbenchFiles";

type PersistedState =
  | {
      openTabs: Array<string | { id: string; pinned?: boolean }>;
      activeTabId?: string | null;
      mru?: string[];
    }
  | null;

const tree: WorkbenchFileNode = {
  id: "root",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "manifest.toml", name: "manifest.toml", kind: "file", language: "toml" },
    { id: "src/data.py", name: "data.py", kind: "file", language: "python" },
  ],
};

function createStorageStub(initial: PersistedState) {
  let current = initial;
  const getMock = vi.fn(() => current);
  const setMock = vi.fn((value: PersistedState) => {
    current = value ?? null;
  });
  const clearMock = vi.fn(() => {
    current = null;
  });

  const persistence = {
    get: getMock as unknown as <T>() => T | null,
    set: setMock as unknown as <T>(value: T) => void,
    clear: clearMock as () => void,
  };

  return { persistence, getMock, setMock, clearMock, snapshot: () => current };
}

interface HarnessProps {
  readonly tree: WorkbenchFileNode | null;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: {
    get<T>(): T | null;
    set<T>(value: T): void;
    clear(): void;
  } | null;
}

function Harness({ tree, loadFile, persistence }: HarnessProps) {
  const files = useWorkbenchFiles({ tree, loadFile, persistence: persistence ?? undefined });

  return (
    <div>
      <div data-testid="active-tab">{files.activeTabId}</div>
      <div data-testid="open-tabs">{files.tabs.map((tab) => tab.id).join(",")}</div>
      <div data-testid="tab-statuses">{files.tabs.map((tab) => tab.status).join(",")}</div>
      <button type="button" onClick={() => files.openFile("manifest.toml")}>Open manifest</button>
      <button type="button" onClick={() => files.openFile("src/data.py")}>Open data</button>
      <button type="button" onClick={() => files.selectTab("manifest.toml")}>Select manifest</button>
      <button type="button" onClick={() => files.closeTab(files.activeTabId)} disabled={!files.activeTabId}>
        Close active
      </button>
    </div>
  );
}

describe("useWorkbenchFiles", () => {
  it("hydrates persisted tabs from storage", async () => {
    const storage = createStorageStub({ openTabs: ["manifest.toml", "src/data.py"], activeTabId: "src/data.py" });
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));

    render(<Harness tree={tree} loadFile={loadFile} persistence={storage.persistence} />);

    await waitFor(() => expect(screen.getByTestId("open-tabs").textContent).toBe("manifest.toml,src/data.py"));
    expect(screen.getByTestId("active-tab").textContent).toBe("src/data.py");
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toBe("ready,ready"));
  });

  it("persists tab mutations to storage", async () => {
    const storage = createStorageStub(null);
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));

    render(<Harness tree={tree} loadFile={loadFile} persistence={storage.persistence} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("loading"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [{ id: "manifest.toml", pinned: false }],
        activeTabId: "manifest.toml",
        mru: ["manifest.toml"],
      });
    });

    fireEvent.click(screen.getByText("Open data"));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("loading"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [
          { id: "manifest.toml", pinned: false },
          { id: "src/data.py", pinned: false },
        ],
        activeTabId: "src/data.py",
        mru: ["src/data.py", "manifest.toml"],
      });
    });

    fireEvent.click(screen.getByText("Close active"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [{ id: "manifest.toml", pinned: false }],
        activeTabId: "manifest.toml",
        mru: ["manifest.toml"],
      });
    });

    fireEvent.click(screen.getByText("Close active"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [],
        activeTabId: null,
        mru: [],
      });
    });
  });

  it("loads file content when opening a tab", async () => {
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));
    render(<Harness tree={tree} loadFile={loadFile} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledWith("manifest.toml"));
  });

  it("retries loading when a tab errors and is re-selected", async () => {
    const loadFile = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({ content: "new content", etag: null });

    render(<Harness tree={tree} loadFile={loadFile} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("error"));

    fireEvent.click(screen.getByText("Select manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(2));
  });
});
