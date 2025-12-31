import clsx from "clsx";
import type { MouseEvent } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { TabsTrigger } from "@components/ui/tabs";

import type { WorkbenchFileTab } from "../types";
import { PinGlyph, TabSavingSpinner } from "./EditorIcons";

interface EditorTabProps {
  readonly tab: WorkbenchFileTab;
  readonly isActive: boolean;
  readonly isDirty: boolean;
  readonly draggingId: string | null;
  readonly onContextMenu: (event: MouseEvent<HTMLButtonElement>) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly setTabNode: (tabId: string, node: HTMLDivElement | null) => void;
}

export function EditorTab({
  tab,
  isActive,
  isDirty,
  draggingId,
  onContextMenu,
  onCloseTab,
  setTabNode,
}: EditorTabProps) {
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
      ref={(node) => {
        setNodeRef(node);
        setTabNode(tab.id, node);
      }}
      style={style}
      className={clsx("group relative mr-1 flex min-w-0 items-stretch", showingDrag && "opacity-60")}
      data-editor-tab="true"
      {...attributes}
      {...listeners}
    >
      <TabsTrigger
        value={tab.id}
        data-tab-id={tab.id}
        title={tab.id}
        onContextMenu={onContextMenu}
        onMouseDown={(event) => {
          if (event.button === 1) {
            event.preventDefault();
            onCloseTab(tab.id);
          }
        }}
        className={clsx(
          "relative flex min-w-[3rem] max-w-[16rem] items-center gap-2 overflow-hidden rounded-t-lg border px-2 py-1.5 pr-8 text-sm font-medium transition-[background-color,border-color,color] duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          isActive
            ? "border-border border-b-card bg-card text-foreground shadow-[0_1px_0_rgb(var(--sys-color-shadow)/0.08)]"
            : "border-transparent border-b-border text-muted-foreground hover:border-border hover:bg-card/70 hover:text-foreground",
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
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
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
          "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-xs transition focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 focus-visible:ring-offset-background",
          isActive
            ? "text-muted-foreground hover:bg-muted hover:text-foreground"
            : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-muted hover:text-foreground",
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
