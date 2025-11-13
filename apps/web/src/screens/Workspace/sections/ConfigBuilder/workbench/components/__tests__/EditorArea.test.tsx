import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@ui/CodeEditor", () => ({
  CodeEditor: ({ value, onChange }: { value: string; onChange?: (value: string | undefined) => void }) => (
    <textarea
      data-testid="code-editor"
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

import type { WorkbenchFileTab } from "../../types";
import { EditorArea } from "../EditorArea";

const tabs: WorkbenchFileTab[] = [
  {
    id: "manifest.json",
    name: "manifest.json",
    language: "json",
    initialContent: "{}",
    content: "{}",
    status: "ready",
    error: null,
    etag: null,
  },
  {
    id: "src/data.py",
    name: "data.py",
    language: "python",
    initialContent: "print('hello')\n",
    content: "print('hello')\n",
    status: "ready",
    error: null,
    etag: null,
  },
];

afterEach(() => {
  vi.clearAllMocks();
});

describe("EditorArea keyboard shortcuts", () => {
  it("cycles to the next tab with Ctrl+Tab", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onContentChange = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.json"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onContentChange={onContentChange}
      />,
    );

    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("src/data.py");

    unmount();
  });

  it("cycles to the previous tab with Ctrl+Shift+Tab", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onContentChange = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="src/data.py"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onContentChange={onContentChange}
      />,
    );

    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true, shiftKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("manifest.json");

    unmount();
  });

  it("closes the active tab with Ctrl+W", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onContentChange = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.json"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onContentChange={onContentChange}
      />,
    );

    fireEvent.keyDown(window, { key: "w", ctrlKey: true });
    expect(onCloseTab).toHaveBeenCalledWith("manifest.json");

    unmount();
  });
});
