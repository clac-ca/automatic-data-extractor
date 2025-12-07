import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@ui/CodeEditor", () => ({
  CodeEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange?: (value: string | undefined) => void;
    theme?: string;
  }) => (
    <textarea
      data-testid="code-editor"
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

import type { WorkbenchFileTab } from "../../types";
import { EditorArea } from "../EditorArea";

const focusEditor = (container: HTMLElement) => {
  const editor = container.querySelector<HTMLTextAreaElement>('[data-testid="code-editor"]');
  editor?.focus();
};

const tabs: WorkbenchFileTab[] = [
  {
    id: "manifest.toml",
    name: "manifest.toml",
    language: "toml",
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
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount, container } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.toml"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    focusEditor(container);
    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true });
    expect(onSelectRecentTab).toHaveBeenCalledWith("forward");

    unmount();
  });

  it("cycles to the previous tab with Ctrl+Shift+Tab", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount, container } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="src/data.py"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    focusEditor(container);
    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true, shiftKey: true });
    expect(onSelectRecentTab).toHaveBeenCalledWith("backward");

    unmount();
  });

  it("cycles visually with Ctrl+PageDown", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount, container } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.toml"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    focusEditor(container);
    fireEvent.keyDown(window, { key: "PageDown", ctrlKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("src/data.py");

    unmount();
  });

  it("cycles visually backwards with Ctrl+PageUp", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount, container } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="src/data.py"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    focusEditor(container);
    fireEvent.keyDown(window, { key: "PageUp", ctrlKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("manifest.toml");

    unmount();
  });

  it("closes the active tab with Ctrl+W", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount, container } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.toml"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    focusEditor(container);
    fireEvent.keyDown(window, { key: "w", ctrlKey: true });
    expect(onCloseTab).toHaveBeenCalledWith("manifest.toml");

    unmount();
  });
});
