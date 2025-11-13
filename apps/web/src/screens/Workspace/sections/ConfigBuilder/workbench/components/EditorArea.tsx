import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

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

type WorkbenchTabZone = "pinned" | "regular";

const SCROLL_STEP = 220;
const AUTO_SCROLL_THRESHOLD = 64;
const AUTO_SCROLL_SPEED = 14;

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number, options?: { zone?: WorkbenchTabZone }) => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
  readonly onSelectRecentTab: (direction: "forward" | "backward") => void;
  readonly editorTheme: string;
  readonly menuAppearance: "light" | "dark";
  readonly canSaveFiles?: boolean;
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
  onPinTab,
  onUnpinTab,
  onContentChange,
  onSaveTab,
  onSaveAllTabs,
  onSelectRecentTab,
  editorTheme,
  menuAppearance,
  canSaveFiles = false,
  minHeight,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(null);
  const [tabCatalogMenu, setTabCatalogMenu] = useState<{ x: number; y: number } | null>(null);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);
  const [scrollShadow, setScrollShadow] = useState({ left: false, right: false });
  const [autoScrollDirection, setAutoScrollDirection] = useState<0 | -1 | 1>(0);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const overflowButtonRef = useRef<HTMLButtonElement | null>(null);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [tabs, activeTabId],
  );

  const pinnedTabs = useMemo(() => tabs.filter((tab) => tab.pinned), [tabs]);
  const regularTabs = useMemo(() => tabs.filter((tab) => !tab.pinned), [tabs]);
  const contentTabs = useMemo(() => tabs.slice().sort((a, b) => a.id.localeCompare(b.id)), [tabs]);
  const dirtyTabs = useMemo(
    () => tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );
  const hasDirtyTabs = dirtyTabs.length > 0;

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
        onSelectRecentTab(event.shiftKey ? "backward" : "forward");
        return;
      }

      const cycleVisual = (delta: number) => {
        if (tabs.length < 2) {
          return;
        }
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      };

      if (event.key === "PageUp") {
        event.preventDefault();
        cycleVisual(-1);
        return;
      }

      if (event.key === "PageDown") {
        event.preventDefault();
        cycleVisual(1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasTabs, tabs, activeTabId, onCloseTab, onSelectTab, onSelectRecentTab]);

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
        const overTab = tabs[overIndex];
        const zone: WorkbenchTabZone = overTab?.pinned ? "pinned" : "regular";
        onMoveTab(String(activeId), insertIndex, { zone });
      }
    }
    setDraggingTabId(null);
  };

  const handleDragCancel = () => {
    setDraggingTabId(null);
  };

  const updateScrollIndicators = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    const { scrollLeft, scrollWidth, clientWidth } = container;
    setScrollShadow({
      left: scrollLeft > 2,
      right: scrollLeft + clientWidth < scrollWidth - 2,
    });
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    updateScrollIndicators();
    const handleScroll = () => updateScrollIndicators();
    container.addEventListener("scroll", handleScroll);
    window.addEventListener("resize", updateScrollIndicators);
    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateScrollIndicators) : null;
    observer?.observe(container);
    return () => {
      container.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", updateScrollIndicators);
      observer?.disconnect();
    };
  }, [tabs.length, updateScrollIndicators]);

  useEffect(() => {
    if (!draggingTabId) {
      setAutoScrollDirection(0);
      return;
    }
    const handlePointerMove = (event: PointerEvent) => {
      const container = scrollContainerRef.current;
      if (!container) {
        setAutoScrollDirection(0);
        return;
      }
      const bounds = container.getBoundingClientRect();
      if (event.clientX < bounds.left + AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(-1);
      } else if (event.clientX > bounds.right - AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(1);
      } else {
        setAutoScrollDirection(0);
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      setAutoScrollDirection(0);
    };
  }, [draggingTabId]);

  useEffect(() => {
    if (!draggingTabId || autoScrollDirection === 0) {
      return;
    }
    let frame: number;
    const step = () => {
      const container = scrollContainerRef.current;
      if (!container) {
        return;
      }
      container.scrollBy({ left: autoScrollDirection * AUTO_SCROLL_SPEED });
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [autoScrollDirection, draggingTabId]);

  useEffect(() => {
    if (!activeTabId) {
      return;
    }
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }
    const selector = `[data-tab-id="${escapeAttributeValue(activeTabId)}"]`;
    const target = container.querySelector<HTMLElement>(selector);
    target?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [activeTabId, tabs.length]);

  const tabContextItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const currentTab = tabs.find((tab) => tab.id === contextMenu.tabId);
    if (!currentTab) {
      return [];
    }
    const tabIndex = tabs.findIndex((tab) => tab.id === contextMenu.tabId);
    const hasTabsToRight = tabIndex >= 0 && tabIndex < tabs.length - 1;
    const hasMultipleTabs = tabs.length > 1;
    const isDirty = currentTab.status === "ready" && currentTab.content !== currentTab.initialContent;
    const canSaveCurrent = Boolean(onSaveTab) && canSaveFiles && isDirty && !currentTab.saving;
    const canSaveAny = Boolean(onSaveAllTabs) && canSaveFiles && hasDirtyTabs;
    const shortcuts = {
      save: "Ctrl+S",
      saveAll: "Ctrl+Shift+S",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
    };
    return [
      {
        id: "save",
        label: currentTab.saving ? "Saving…" : "Save",
        icon: <MenuIconSave />,
        disabled: !canSaveCurrent,
        shortcut: shortcuts.save,
        onSelect: () => onSaveTab?.(currentTab.id),
      },
      {
        id: "save-all",
        label: "Save All",
        icon: <MenuIconSaveAll />,
        disabled: !canSaveAny,
        shortcut: shortcuts.saveAll,
        onSelect: () => onSaveAllTabs?.(),
      },
      {
        id: "pin",
        label: currentTab.pinned ? "Unpin" : "Pin",
        icon: currentTab.pinned ? <MenuIconUnpin /> : <MenuIconPin />,
        dividerAbove: true,
        onSelect: () => (currentTab.pinned ? onUnpinTab(currentTab.id) : onPinTab(currentTab.id)),
      },
      {
        id: "close",
        label: "Close",
        icon: <MenuIconClose />,
        dividerAbove: true,
        shortcut: shortcuts.close,
        onSelect: () => onCloseTab(currentTab.id),
      },
      {
        id: "close-others",
        label: "Close Others",
        icon: <MenuIconCloseOthers />,
        disabled: !hasMultipleTabs,
        shortcut: shortcuts.closeOthers,
        onSelect: () => onCloseOtherTabs(currentTab.id),
      },
      {
        id: "close-right",
        label: "Close Tabs to the Right",
        icon: <MenuIconCloseRight />,
        disabled: !hasTabsToRight,
        shortcut: shortcuts.closeRight,
        onSelect: () => onCloseTabsToRight(currentTab.id),
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
  }, [
    contextMenu,
    tabs,
    hasDirtyTabs,
    canSaveFiles,
    onPinTab,
    onUnpinTab,
    onCloseTab,
    onCloseOtherTabs,
    onCloseTabsToRight,
    onCloseAllTabs,
    onSaveTab,
    onSaveAllTabs,
  ]);

  const tabCatalogItems: ContextMenuItem[] = useMemo(() => {
    if (!hasTabs) {
      return [
        {
          id: "empty",
          label: "No open editors",
          onSelect: () => undefined,
          disabled: true,
        },
      ];
    }
    const items: ContextMenuItem[] = [];
    const appendItem = (tab: WorkbenchFileTab, dividerAbove: boolean) => {
      items.push({
        id: `switch-${tab.id}`,
        label: tab.name,
        icon: tab.pinned ? <MenuIconPin /> : <MenuIconFile />,
        shortcut: tab.id === activeTabId ? "Active" : undefined,
        dividerAbove,
        onSelect: () => onSelectTab(tab.id),
      });
    };
    pinnedTabs.forEach((tab) => appendItem(tab, false));
    regularTabs.forEach((tab, index) => appendItem(tab, index === 0 && pinnedTabs.length > 0));
    return items;
  }, [hasTabs, pinnedTabs, regularTabs, activeTabId, onSelectTab]);

  const scrollTabs = (delta: number) => {
    scrollContainerRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  };

  const openTabListMenu = () => {
    if (typeof window === "undefined") {
      return;
    }
    const anchor = overflowButtonRef.current?.getBoundingClientRect();
    if (!anchor) {
      return;
    }
    setTabCatalogMenu({ x: anchor.left, y: anchor.bottom + 6 });
  };

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={minHeight ? { minHeight } : undefined}>
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
            <div className="flex items-center gap-1 border-b border-slate-200 bg-slate-900/5 px-1">
              <ScrollButton
                direction="left"
                disabled={!scrollShadow.left}
                onClick={() => scrollTabs(-SCROLL_STEP)}
              />
              <div className="relative flex min-w-0 flex-1 items-stretch">
                {scrollShadow.left ? <ScrollGradient position="left" /> : null}
                {scrollShadow.right ? <ScrollGradient position="right" /> : null}
                <div
                  ref={scrollContainerRef}
                  className="flex min-w-0 flex-1 overflow-x-auto pb-1"
                  onWheel={(event) => {
                    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
                      event.preventDefault();
                      scrollContainerRef.current?.scrollBy({ left: event.deltaY });
                    }
                  }}
                >
                  <TabsList className="flex min-h-[2.75rem] flex-1 items-end gap-0 px-1">
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
                </div>
              </div>
              <ScrollButton
                direction="right"
                disabled={!scrollShadow.right}
                onClick={() => scrollTabs(SCROLL_STEP)}
              />
              <button
                ref={overflowButtonRef}
                type="button"
                className="mx-1 flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-white hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label="Open editors list"
                onClick={openTabListMenu}
              >
                <ChevronDownIcon />
              </button>
            </div>
          </SortableContext>
        </DndContext>

        {contentTabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 min-w-0 flex-1">
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
              <div
                className={clsx(
                  "flex min-h-0 min-w-0 flex-1",
                  draggingTabId && "pointer-events-none select-none",
                )}
              >
                <CodeEditor
                  value={tab.content}
                  language={tab.language ?? "plaintext"}
                  path={tab.id}
                  theme={editorTheme}
                  onChange={(value) => onContentChange(tab.id, value ?? "")}
                  onSaveShortcut={() => {
                    if (!canSaveFiles) {
                      return;
                    }
                    onSaveTab?.(tab.id);
                  }}
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
      <ContextMenu
        open={Boolean(tabCatalogMenu)}
        position={tabCatalogMenu}
        onClose={() => setTabCatalogMenu(null)}
        items={tabCatalogItems}
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
  const isPinned = Boolean(tab.pinned);

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
      onMouseDown={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          onCloseTab(tab.id);
        }
      }}
      {...attributes}
      {...listeners}
    >
      <TabsTrigger
        value={tab.id}
        data-tab-id={tab.id}
        title={tab.id}
        className={clsx(
          "relative flex min-w-[3rem] max-w-[16rem] items-center gap-2 overflow-hidden rounded-t-lg border px-2 py-1.5 pr-8 text-sm font-medium transition-[background-color,border-color,color] duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
          isActive
            ? "border-slate-200 border-b-white bg-white text-slate-900 shadow-[0_1px_0_rgba(15,23,42,0.08)]"
            : "border-transparent border-b-slate-200 text-slate-500 hover:border-slate-200 hover:bg-white/70 hover:text-slate-900",
          isPinned ? "min-w-[4rem] max-w-[8rem] justify-center" : "min-w-[9rem] justify-start px-3",
        )}
      >
        {isPinned ? (
          <span className="flex-none text-[12px]" aria-label="Pinned">
            <PinGlyph filled={isActive} />
          </span>
        ) : null}
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
        {tab.saving ? (
          <span className="flex-none" aria-label="Saving" title="Saving changes…">
            <TabSavingSpinner />
          </span>
        ) : null}
        {tab.saveError ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Save failed"
            title={tab.saveError}
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

interface ScrollButtonProps {
  readonly direction: "left" | "right";
  readonly disabled: boolean;
  readonly onClick: () => void;
}

function ScrollButton({ direction, disabled, onClick }: ScrollButtonProps) {
  return (
    <button
      type="button"
      className={clsx(
        "flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        disabled
          ? "cursor-default opacity-30"
          : "hover:bg-white hover:text-slate-900 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900/5",
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "left" ? "Scroll tabs left" : "Scroll tabs right"}
    >
      {direction === "left" ? <ChevronLeftIcon /> : <ChevronRightIcon />}
    </button>
  );
}

interface ScrollGradientProps {
  readonly position: "left" | "right";
}

function ScrollGradient({ position }: ScrollGradientProps) {
  return (
    <div
      className={clsx(
        "pointer-events-none absolute top-0 bottom-0 w-8",
        position === "left"
          ? "left-0 bg-gradient-to-r from-slate-100 via-slate-100/70 to-transparent"
          : "right-0 bg-gradient-to-l from-slate-100 via-slate-100/70 to-transparent",
      )}
    />
  );
}

function PinGlyph({ filled }: { readonly filled: boolean }) {
  return filled ? (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="currentColor"
        className="text-slate-500"
      />
    </svg>
  ) : (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        className="text-slate-400"
      />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function TabSavingSpinner() {
  return (
    <svg className="h-3 w-3 animate-spin text-brand-500" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      <path
        d="M14 8a6 6 0 0 0-6-6"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MenuIconSave() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M4 2.5h7.5L13.5 5v8.5H4z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconSaveAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5h6l3 3v5.5h-9z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 3.5v3.5h3.5v-3.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path
        d="M6.5 6.5h6l1.5 1.5v4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
}

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

function MenuIconPin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5.5 2.5h5l.5 4h2v1.5h-4V13l-1-.5V8h-3V6.5h3z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconUnpin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5l9 9M5.5 2.5h5l.5 4h2v1.5H10M8 8v4.5L7 12.5V8H4V6.5h1"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5 2.5h4l2.5 2.5V13.5H5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function escapeAttributeValue(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
