import type { ContextMenuItem } from "@components/ui/context-menu";

import type { WorkbenchFileTab } from "../types";
import {
  MenuIconClose,
  MenuIconCloseAll,
  MenuIconCloseOthers,
  MenuIconCloseRight,
  MenuIconFile,
  MenuIconPin,
  MenuIconSave,
  MenuIconSaveAll,
  MenuIconUnpin,
} from "./EditorIcons";

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

interface BuildTabContextMenuItemsArgs {
  readonly currentTab: WorkbenchFileTab;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly canSaveFiles: boolean;
  readonly hasDirtyTabs: boolean;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
}

export function buildTabContextMenuItems({
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
}: BuildTabContextMenuItemsArgs): ContextMenuItem[] {
  const tabIndex = tabs.findIndex((tab) => tab.id === currentTab.id);
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
      icon: <MenuIconSave className={MENU_ICON_CLASS} />,
      disabled: !canSaveCurrent,
      shortcut: shortcuts.save,
      onSelect: () => onSaveTab?.(currentTab.id),
    },
    {
      id: "save-all",
      label: "Save All",
      icon: <MenuIconSaveAll className={MENU_ICON_CLASS} />,
      disabled: !canSaveAny,
      shortcut: shortcuts.saveAll,
      onSelect: () => onSaveAllTabs?.(),
    },
    {
      id: "pin",
      label: currentTab.pinned ? "Unpin" : "Pin",
      icon: currentTab.pinned ? <MenuIconUnpin className={MENU_ICON_CLASS} /> : <MenuIconPin className={MENU_ICON_CLASS} />,
      dividerAbove: true,
      onSelect: () => (currentTab.pinned ? onUnpinTab(currentTab.id) : onPinTab(currentTab.id)),
    },
    {
      id: "close",
      label: "Close",
      icon: <MenuIconClose className={MENU_ICON_CLASS} />,
      dividerAbove: true,
      shortcut: shortcuts.close,
      onSelect: () => onCloseTab(currentTab.id),
    },
    {
      id: "close-others",
      label: "Close Others",
      icon: <MenuIconCloseOthers className={MENU_ICON_CLASS} />,
      disabled: !hasMultipleTabs,
      shortcut: shortcuts.closeOthers,
      onSelect: () => onCloseOtherTabs(currentTab.id),
    },
    {
      id: "close-right",
      label: "Close Tabs to the Right",
      icon: <MenuIconCloseRight className={MENU_ICON_CLASS} />,
      disabled: !hasTabsToRight,
      shortcut: shortcuts.closeRight,
      onSelect: () => onCloseTabsToRight(currentTab.id),
    },
    {
      id: "close-all",
      label: "Close All",
      icon: <MenuIconCloseAll className={MENU_ICON_CLASS} />,
      dividerAbove: true,
      disabled: tabs.length === 0,
      shortcut: shortcuts.closeAll,
      onSelect: () => onCloseAllTabs(),
    },
  ];
}

interface BuildTabCatalogItemsArgs {
  readonly pinnedTabs: readonly WorkbenchFileTab[];
  readonly regularTabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
}

export function buildTabCatalogItems({
  pinnedTabs,
  regularTabs,
  activeTabId,
  onSelectTab,
}: BuildTabCatalogItemsArgs): ContextMenuItem[] {
  if (pinnedTabs.length === 0 && regularTabs.length === 0) {
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
    const isDirty = tab.status === "ready" && tab.content !== tab.initialContent;
    const badges: string[] = [];
    if (tab.id === activeTabId) {
      badges.push("Active");
    }
    if (tab.saving) {
      badges.push("Saving…");
    } else if (isDirty) {
      badges.push("Unsaved");
    }
    items.push({
      id: `switch-${tab.id}`,
      label: `${tab.saving ? "↻ " : isDirty ? "● " : ""}${tab.name}`,
      icon: tab.pinned ? <MenuIconPin className={MENU_ICON_CLASS} /> : <MenuIconFile className={MENU_ICON_CLASS} />,
      shortcut: badges.length > 0 ? badges.join(" · ") : undefined,
      dividerAbove,
      onSelect: () => onSelectTab(tab.id),
    });
  };

  pinnedTabs.forEach((tab) => appendItem(tab, false));
  regularTabs.forEach((tab, index) => appendItem(tab, index === 0 && pinnedTabs.length > 0));
  return items;
}
