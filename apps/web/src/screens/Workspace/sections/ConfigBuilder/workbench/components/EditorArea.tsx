import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";
import clsx from "clsx";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { CodeEditor } from "@ui/CodeEditor";
import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchFileTab } from "../types";

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly editorTheme: string;
  readonly menuAppearance: "light" | "dark";
  readonly minHeight?: number;
}

export function EditorArea({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseAllTabs,
  onMoveTab,
  onContentChange,
  editorTheme,
  menuAppearance,
  minHeight,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(null);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);

  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0], [tabs, activeTabId]);
  const contentTabs = useMemo(() => tabs.slice().sort((a, b) => a.id.localeCompare(b.id)), [tabs]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
  );

  useEffect(() => {
    if (!hasTabs) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      if (event.key.toLowerCase() === "w") {
        if (!activeTabId) {
          return;
        }
        event.preventDefault();
        onCloseTab(activeTabId);
        return;
      }

      if (event.key === "Tab") {
        if (tabs.length < 2) {
          return;
        }
        event.preventDefault();
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const delta = event.shiftKey ? -1 : 1;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasTabs, tabs, activeTabId, onCloseTab, onSelectTab]);

  useEffect(() => {
    if (!contextMenu) {
      return;
    }
    if (!tabs.some((tab) => tab.id === contextMenu.tabId)) {
      setContextMenu(null);
    }
  }, [contextMenu, tabs]);

  const handleDragStart = (event: DragStartEvent) => {
    setDraggingTabId(String(event.active.id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const activeId = event.active.id;
    const overId = event.over?.id;
    if (!overId) {
      setDraggingTabId(null);
      return;
    }
    if (activeId !== overId) {
      const activeIndex = tabs.findIndex((tab) => tab.id === activeId);
      const overIndex = tabs.findIndex((tab) => tab.id === overId);
      if (activeIndex !== -1 && overIndex !== -1) {
        const insertIndex = activeIndex < overIndex ? overIndex + 1 : overIndex;
        onMoveTab(String(activeId), insertIndex);
      }
    }
    setDraggingTabId(null);
  };

  const handleDragCancel = () => {
    setDraggingTabId(null);
  };

  const tabContextItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const { tabId } = contextMenu;
    const tabIndex = tabs.findIndex((tab) => tab.id === tabId);
    const hasTabsToRight = tabIndex >= 0 && tabIndex < tabs.length - 1;
    const hasMultipleTabs = tabs.length > 1;
    const shortcuts = {
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
    };
    return [
      {
        id: "close",
        label: "Close",
        icon: <MenuIconClose />,
        shortcut: shortcuts.close,
        onSelect: () => onCloseTab(tabId),
      },
      {
        id: "close-others",
        label: "Close Others",
        icon: <MenuIconCloseOthers />,
        disabled: !hasMultipleTabs,
        shortcut: shortcuts.closeOthers,
        onSelect: () => onCloseOtherTabs(tabId),
      },
      {
        id: "close-right",
        label: "Close Tabs to the Right",
        icon: <MenuIconCloseRight />,
        disabled: !hasTabsToRight,
        shortcut: shortcuts.closeRight,
        onSelect: () => onCloseTabsToRight(tabId),
      },
      {
        id: "close-all",
        label: "Close All",
        icon: <MenuIconCloseAll />,
        dividerAbove: true,
        disabled: tabs.length === 0,
        shortcut: shortcuts.closeAll,
        onSelect: () => onCloseAllTabs(),
      },
    ];
  }, [contextMenu, tabs, onCloseTab, onCloseOtherTabs, onCloseTabsToRight, onCloseAllTabs]);

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col" style={minHeight ? { minHeight } : undefined}>
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
            <TabsList className="flex min-h-[2.75rem] items-end gap-0 overflow-x-auto border-b border-slate-200 bg-slate-900/5 px-2">
              {tabs.map((tab) => {
                const isDirty = tab.status === "ready" && tab.content !== tab.initialContent;
                const isActive = tab.id === activeTab.id;
                return (
                  <SortableTab
                    key={tab.id}
                    tab={tab}
                    isActive={isActive}
                    isDirty={isDirty}
                    draggingId={draggingTabId}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      setContextMenu({ tabId: tab.id, x: event.clientX, y: event.clientY });
                    }}
                    onCloseTab={onCloseTab}
                  />
                );
              })}
            </TabsList>
          </SortableContext>
        </DndContext>
        {contentTabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 flex-1">
            {tab.status === "loading" ? (
              <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
                Loading {tab.name}…
              </div>
            ) : tab.status === "error" ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
                <p>{tab.error ?? "Unable to load the file."}</p>
                <button
                  type="button"
                  className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-500"
                  onClick={() => onSelectTab(tab.id)}
                >
                  Retry loading
                </button>
              </div>
            ) : (
              <div className={clsx("flex min-h-0 flex-1", draggingTabId && "pointer-events-none select-none")}>
                <CodeEditor
                  value={tab.content}
                  language={tab.language ?? "plaintext"}
                  theme={editorTheme}
                  onChange={(value) => onContentChange(tab.id, value ?? "")}
                />
              </div>
            )}
          </TabsContent>
        ))}
      </TabsRoot>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && { x: contextMenu.x, y: contextMenu.y }}
        onClose={() => setContextMenu(null)}
        items={tabContextItems}
        appearance={menuAppearance}
      />
    </div>
  );
}
interface SortableTabProps {
  readonly tab: WorkbenchFileTab;
  readonly isActive: boolean;
  readonly isDirty: boolean;
  readonly draggingId: string | null;
  readonly onContextMenu: (event: ReactMouseEvent<HTMLDivElement>) => void;
  readonly onCloseTab: (tabId: string) => void;
}

function SortableTab({ tab, isActive, isDirty, draggingId, onContextMenu, onCloseTab }: SortableTabProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: tab.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const showingDrag = isDragging || draggingId === tab.id;
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group relative mr-1 flex min-w-0 items-stretch",
        showingDrag && "opacity-60",
      )}
      data-editor-tab="true"
      onContextMenu={onContextMenu}
      {...attributes}
      {...listeners}
    >
      <TabsTrigger
        value={tab.id}
        title={tab.id}
        className={clsx(
          "relative flex min-w-[9rem] max-w-[16rem] items-center gap-2 overflow-hidden rounded-t-lg border px-3 py-1.5 pr-8 text-sm font-medium transition-[background-color,border-color,color] duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
          isActive
            ? "border-slate-200 border-b-white bg-white text-slate-900 shadow-[0_1px_0_rgba(15,23,42,0.08)]"
            : "border-transparent border-b-slate-200 text-slate-500 hover:border-slate-200 hover:bg-white/70 hover:text-slate-900",
        )}
      >
        <span className="block min-w-0 flex-1 truncate text-left">{tab.name}</span>
        {tab.status === "loading" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-slate-400"
            aria-label="Loading"
          >
            ●
          </span>
        ) : null}
        {tab.status === "error" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Load failed"
          >
            !
          </span>
        ) : null}
        {isDirty ? <span className="flex-none text-xs leading-none text-brand-600">●</span> : null}
      </TabsTrigger>
      <button
        type="button"
        className={clsx(
          "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-xs transition focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 focus-visible:ring-offset-white",
          isActive
            ? "text-slate-500 hover:bg-slate-200 hover:text-slate-900"
            : "text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-slate-200 hover:text-slate-700",
        )}
        onClick={(event) => {
          event.stopPropagation();
          onCloseTab(tab.id);
        }}
        aria-label={`Close ${tab.name}`}
      >
        ×
      </button>
    </div>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4h3a1 1 0 0 1 1 1v7.5M12.5 12h-3a1 1 0 0 1-1-1V3.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M5 6l6 6m0-6-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
