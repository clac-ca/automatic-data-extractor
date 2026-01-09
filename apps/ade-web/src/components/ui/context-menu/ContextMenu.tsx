import { createPortal } from "react-dom";
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

import clsx from "clsx";

export interface ContextMenuItem {
  readonly id: string;
  readonly label: string;
  readonly onSelect: () => void;
  readonly shortcut?: string;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly danger?: boolean;
  readonly dividerAbove?: boolean;
  readonly onHover?: () => void;
}

export interface ContextMenuProps {
  readonly open: boolean;
  readonly position: { readonly x: number; readonly y: number } | null;
  readonly onClose: () => void;
  readonly items: readonly ContextMenuItem[];
  readonly appearance?: "light" | "dark";
  readonly onPointerLeave?: () => void;
}

const MENU_WIDTH = 232;
const MENU_ITEM_HEIGHT = 30;
const MENU_PADDING = 6;

export function ContextMenu({
  open,
  position,
  onClose,
  items,
  appearance = "dark",
  onPointerLeave,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);
  const firstEnabledIndex = useMemo(
    () => items.findIndex((item) => !item.disabled),
    [items],
  );
  const [activeIndex, setActiveIndex] = useState(() =>
    firstEnabledIndex >= 0 ? firstEnabledIndex : 0,
  );

  useEffect(() => {
    if (!open || !position || typeof window === "undefined") {
      setCoords(null);
      return;
    }
    const estimatedHeight = items.length * MENU_ITEM_HEIGHT + MENU_PADDING * 2;
    const maxX = Math.max(
      MENU_PADDING,
      (window.innerWidth || 0) - MENU_WIDTH - MENU_PADDING,
    );
    const maxY = Math.max(
      MENU_PADDING,
      (window.innerHeight || 0) - estimatedHeight - MENU_PADDING,
    );
    const nextX = Math.min(Math.max(position.x, MENU_PADDING), maxX);
    const nextY = Math.min(Math.max(position.y, MENU_PADDING), maxY);
    setCoords({ x: nextX, y: nextY });
  }, [open, position, items.length]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setActiveIndex(firstEnabledIndex >= 0 ? firstEnabledIndex : 0);
  }, [open, firstEnabledIndex]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const target = itemRefs.current[activeIndex];
    target?.focus();
  }, [open, activeIndex]);

  useEffect(() => {
    if (!open || typeof window === "undefined") {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    const handleContextMenu = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (menuRef.current.contains(event.target as Node)) {
        event.preventDefault();
        return;
      }
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        setActiveIndex((current) => {
          if (items.length === 0) {
            return current;
          }
          let next = current;
          for (let i = 0; i < items.length; i += 1) {
            next = (next + direction + items.length) % items.length;
            if (!items[next]?.disabled) {
              return next;
            }
          }
          return current;
        });
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const item = items[activeIndex];
        if (item && !item.disabled) {
          item.onSelect();
          onClose();
        }
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("contextmenu", handleContextMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose, items, activeIndex]);

  if (!open || !position || typeof window === "undefined" || !coords) {
    return null;
  }

  const palette =
    appearance === "dark"
      ? {
          bg: "bg-popover text-foreground",
          border: "border-border/70",
          shadow: "shadow-md",
          item: "hover:bg-muted focus-visible:bg-muted",
          disabled: "text-muted-foreground",
          danger: "text-destructive hover:bg-destructive/20 focus-visible:bg-destructive/20",
          shortcut: "text-muted-foreground",
          separator: "border-border/60",
        }
      : {
          bg: "bg-popover text-foreground",
          border: "border-border/80",
          shadow: "shadow-md",
          item: "hover:bg-muted focus-visible:bg-muted",
          disabled: "text-muted-foreground",
          danger: "text-destructive hover:bg-destructive/10 focus-visible:bg-destructive/10",
          shortcut: "text-muted-foreground",
          separator: "border-border/70",
        };

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className={clsx(
        "z-[60] min-w-[200px] rounded-sm border",
        palette.bg,
        palette.border,
        palette.shadow,
      )}
      style={{ top: coords.y, left: coords.x, position: "fixed" }}
      onPointerLeave={onPointerLeave}
    >
      <ul className="py-1" role="none">
        {items.map((item, index) => {
          const disabled = Boolean(item.disabled);
          const danger = Boolean(item.danger);
          return (
            <Fragment key={item.id}>
              {item.dividerAbove ? (
                <li role="separator" className={clsx("mx-2 my-1 border-t", palette.separator)} />
              ) : null}
              <li role="none">
                <button
                  ref={(node) => {
                    itemRefs.current[index] = node;
                  }}
                  type="button"
                  role="menuitem"
                  className={clsx(
                    "flex w-full items-center justify-between gap-6 px-3 py-1.5 text-[13px] leading-5 outline-none transition",
                    palette.item,
                    disabled && palette.disabled,
                    danger && !disabled && palette.danger,
                    disabled && "cursor-default",
                  )}
                  onClick={(event: ReactMouseEvent<HTMLButtonElement>) => {
                    event.stopPropagation();
                    if (disabled) {
                      return;
                    }
                    item.onSelect();
                    onClose();
                  }}
                  onMouseEnter={() => {
                    if (!disabled) {
                      setActiveIndex(index);
                      item.onHover?.();
                    }
                  }}
                  disabled={disabled}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    {item.icon ? (
                      <span className="text-base opacity-80">{item.icon}</span>
                    ) : (
                      <span className="inline-block h-4 w-4" />
                    )}
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.shortcut ? (
                    <span className={clsx("text-[11px] uppercase tracking-wide", palette.shortcut)}>
                      {item.shortcut}
                    </span>
                  ) : null}
                </button>
              </li>
            </Fragment>
          );
        })}
      </ul>
    </div>,
    window.document.body,
  );
}
