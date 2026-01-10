import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import clsx from "clsx";

import { ContextMenu } from "@/components/ui/context-menu";
import { TabsList } from "@/components/ui/tabs";

import type { WorkbenchFileTab } from "../types";
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon } from "./EditorIcons";
import { EditorTab } from "./EditorTab";
import { buildTabCatalogItems, buildTabContextMenuItems } from "./EditorTabMenus";

const SCROLL_STEP = 220;
const AUTO_SCROLL_THRESHOLD = 64;
const AUTO_SCROLL_SPEED = 14;

interface EditorTabStripProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly menuAppearance: "light" | "dark";
  readonly canSaveFiles?: boolean;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number) => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
  readonly onTabDragStateChange?: (isDragging: boolean) => void;
}

export function EditorTabStrip({
  tabs,
  activeTabId,
  menuAppearance,
  canSaveFiles = false,
  onSelectTab,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseAllTabs,
  onMoveTab,
  onPinTab,
  onUnpinTab,
  onSaveTab,
  onSaveAllTabs,
  onTabDragStateChange,
}: EditorTabStripProps) {
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(null);
  const [tabCatalogMenu, setTabCatalogMenu] = useState<{ x: number; y: number } | null>(null);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);
  const [scrollShadow, setScrollShadow] = useState({ left: false, right: false });
  const [autoScrollDirection, setAutoScrollDirection] = useState<0 | -1 | 1>(0);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const overflowButtonRef = useRef<HTMLButtonElement | null>(null);
  const tabRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const pinnedTabs = useMemo(() => tabs.filter((tab) => tab.pinned), [tabs]);
  const regularTabs = useMemo(() => tabs.filter((tab) => !tab.pinned), [tabs]);
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
  const barTone = "border-border bg-card";
  const overflowButtonTone =
    "text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card";

  const setTabNode = useCallback((tabId: string, node: HTMLDivElement | null) => {
    const map = tabRefs.current;
    if (node) {
      map.set(tabId, node);
    } else {
      map.delete(tabId);
    }
  }, []);

  useEffect(() => {
    if (contextMenu && !tabs.some((tab) => tab.id === contextMenu.tabId)) {
      setContextMenu(null);
    }
    if (!tabs.length) {
      setTabCatalogMenu(null);
    }
  }, [contextMenu, tabs]);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      setDraggingTabId(String(event.active.id));
      onTabDragStateChange?.(true);
    },
    [onTabDragStateChange],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const activeId = event.active.id;
      const overId = event.over?.id;
      if (overId && activeId !== overId) {
        const activeIndex = tabs.findIndex((tab) => tab.id === activeId);
        const overIndex = tabs.findIndex((tab) => tab.id === overId);
        if (activeIndex !== -1 && overIndex !== -1) {
          const insertIndex = activeIndex < overIndex ? overIndex + 1 : overIndex;
          onMoveTab(String(activeId), insertIndex);
        }
      }
      setDraggingTabId(null);
      onTabDragStateChange?.(false);
    },
    [onMoveTab, onTabDragStateChange, tabs],
  );

  const handleDragCancel = useCallback(() => {
    setDraggingTabId(null);
    onTabDragStateChange?.(false);
  }, [onTabDragStateChange]);

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
    return () => window.cancelAnimationFrame(frame);
  }, [autoScrollDirection, draggingTabId]);

  useEffect(() => {
    const target = tabRefs.current.get(activeTabId);
    target?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [activeTabId, tabs.length]);

  const tabContextItems = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const currentTab = tabs.find((tab) => tab.id === contextMenu.tabId);
    if (!currentTab) {
      return [];
    }
    return buildTabContextMenuItems({
      currentTab,
      tabs,
      canSaveFiles,
      hasDirtyTabs,
      onCloseTab,
      onCloseOtherTabs,
      onCloseTabsToRight,
      onCloseAllTabs,
      onPinTab,
      onUnpinTab,
      onSaveTab,
      onSaveAllTabs,
    });
  }, [
    canSaveFiles,
    contextMenu,
    hasDirtyTabs,
    onCloseAllTabs,
    onCloseOtherTabs,
    onCloseTab,
    onCloseTabsToRight,
    onPinTab,
    onSaveAllTabs,
    onSaveTab,
    onUnpinTab,
    tabs,
  ]);

  const tabCatalogItems = useMemo(
    () =>
      buildTabCatalogItems({
        pinnedTabs,
        regularTabs,
        activeTabId,
        onSelectTab,
      }),
    [pinnedTabs, regularTabs, activeTabId, onSelectTab],
  );

  const scrollTabs = useCallback((delta: number) => {
    scrollContainerRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  }, []);

  const openTabListMenu = useCallback(() => {
    const anchor = overflowButtonRef.current?.getBoundingClientRect();
    if (!anchor) {
      return;
    }
    setTabCatalogMenu({ x: anchor.left, y: anchor.bottom + 6 });
  }, []);

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
          <div className={clsx("flex items-center gap-1 px-1", barTone, "border-b")}>
            <ScrollButton
              appearance={menuAppearance}
              direction="left"
              disabled={!scrollShadow.left}
              onClick={() => scrollTabs(-SCROLL_STEP)}
            />
            <div className="relative flex min-w-0 flex-1 items-stretch">
              {scrollShadow.left ? <ScrollGradient position="left" appearance={menuAppearance} /> : null}
              {scrollShadow.right ? <ScrollGradient position="right" appearance={menuAppearance} /> : null}
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
                    const isActive = tab.id === activeTabId;
                    return (
                      <EditorTab
                        key={tab.id}
                        tab={tab}
                        isActive={isActive}
                        isDirty={isDirty}
                        draggingId={draggingTabId}
                        setTabNode={setTabNode}
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
              appearance={menuAppearance}
              direction="right"
              disabled={!scrollShadow.right}
              onClick={() => scrollTabs(SCROLL_STEP)}
            />
            <button
              ref={overflowButtonRef}
              type="button"
              className={clsx(
                "mx-1 flex h-8 w-8 items-center justify-center rounded-md transition focus-visible:outline-none focus-visible:ring-2",
                overflowButtonTone,
              )}
              aria-label="Open editors list"
              onClick={openTabListMenu}
            >
              <ChevronDownIcon className="h-4 w-4" />
            </button>
          </div>
        </SortableContext>
      </DndContext>
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
    </>
  );
}

interface ScrollButtonProps {
  readonly appearance: "light" | "dark";
  readonly direction: "left" | "right";
  readonly disabled: boolean;
  readonly onClick: () => void;
}

function ScrollButton({ appearance, direction, disabled, onClick }: ScrollButtonProps) {
  const activeTone =
    "hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card";
  return (
    <button
      type="button"
      className={clsx(
        "flex h-8 w-8 items-center justify-center rounded-md transition focus-visible:outline-none",
        appearance === "dark" ? "text-muted-foreground" : "text-muted-foreground",
        disabled ? "cursor-default opacity-30" : activeTone,
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "left" ? "Scroll tabs left" : "Scroll tabs right"}
    >
      {direction === "left" ? <ChevronLeftIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
    </button>
  );
}

interface ScrollGradientProps {
  readonly position: "left" | "right";
  readonly appearance: "light" | "dark";
}

function ScrollGradient({ position, appearance: _appearance }: ScrollGradientProps) {
  const gradientClass =
    position === "left"
      ? "left-0 bg-gradient-to-r from-card via-card/80 to-transparent"
      : "right-0 bg-gradient-to-l from-card via-card/80 to-transparent";
  return (
    <div className={clsx("pointer-events-none absolute top-0 bottom-0 w-8", gradientClass)} />
  );
}
