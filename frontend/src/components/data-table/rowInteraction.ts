import type * as React from "react";

const ROW_INTERACTIVE_SELECTOR = [
  "[data-row-interactive]",
  "[data-ignore-row-click]",
  "[data-radix-popper-content-wrapper]",
  "[data-slot='popover-content']",
  "[data-slot='dropdown-menu-content']",
  "[data-slot='command']",
  "[cmdk-root]",
  "[cmdk-item]",
  "[cmdk-input]",
  "button",
  "a[href]",
  "input",
  "select",
  "textarea",
  "[role='button']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='checkbox']",
  "[role='switch']",
  "[role='combobox']",
  "[role='listbox']",
  "[role='option']",
  "[contenteditable='true']",
].join(",");

const CONTEXT_MENU_BLOCK_SELECTOR = [
  "[data-row-interactive]",
  "[data-ignore-row-click]",
  "[data-radix-popper-content-wrapper]",
  "[data-slot='popover-content']",
  "[data-slot='dropdown-menu-content']",
  "[data-slot='command']",
  "[cmdk-root]",
  "[cmdk-item]",
  "[cmdk-input]",
  "button",
  "a[href]",
  "input",
  "select",
  "textarea",
  "[role='button']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='combobox']",
  "[role='listbox']",
  "[role='option']",
  "[role='textbox']",
  "[contenteditable='true']",
].join(",");

export type RowPointerIntent = {
  pointerStartedOnInteractive: boolean;
};

export function isInteractiveElement(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  if (target.closest("[data-allow-row-activate]")) return false;
  return Boolean(target.closest(ROW_INTERACTIVE_SELECTOR));
}

function isContextMenuBlockedElement(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  if (target.closest("[data-allow-row-context-menu],[data-allow-row-activate]")) return false;
  return Boolean(target.closest(CONTEXT_MENU_BLOCK_SELECTOR));
}

export function getRowPointerIntent(
  event: React.PointerEvent<HTMLElement>,
): RowPointerIntent {
  return {
    pointerStartedOnInteractive: isInteractiveElement(event.target),
  };
}

export function shouldActivateRowFromClick(
  event: React.MouseEvent<HTMLElement>,
  pointerIntent: RowPointerIntent | null,
): boolean {
  if (event.defaultPrevented) return false;
  if (event.button !== 0) return false;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (pointerIntent?.pointerStartedOnInteractive) return false;
  return !isInteractiveElement(event.target);
}

export function shouldOpenRowContextMenu(
  event: React.MouseEvent<HTMLElement>,
): boolean {
  if (event.defaultPrevented) return false;
  return !isContextMenuBlockedElement(event.target);
}

export function shouldActivateRowFromKeyboard(
  event: React.KeyboardEvent<HTMLElement>,
): boolean {
  if (event.key !== "Enter" && event.key !== " ") return false;
  return !isInteractiveElement(event.target);
}

export function shouldOpenRowContextMenuFromKeyboard(
  event: React.KeyboardEvent<HTMLElement>,
): boolean {
  if (event.key !== "ContextMenu" && !(event.shiftKey && event.key === "F10")) {
    return false;
  }
  return !isContextMenuBlockedElement(event.target);
}
