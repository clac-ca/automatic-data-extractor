import { useCallback, useEffect } from "react";

function canUseSessionStorage() {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

function escapeSelectorValue(value: string) {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/g, "\\$&");
}

export function useSettingsFocusRestore(storageKey: string) {
  const rememberRow = useCallback(
    (rowId: string) => {
      if (!storageKey) {
        return;
      }
      if (!canUseSessionStorage()) {
        return;
      }
      window.sessionStorage.setItem(storageKey, rowId);
    },
    [storageKey],
  );

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    if (!canUseSessionStorage()) {
      return;
    }

    const pendingRowId = window.sessionStorage.getItem(storageKey);
    if (!pendingRowId) {
      return;
    }

    const escapedKey = escapeSelectorValue(storageKey);
    const escapedRowId = escapeSelectorValue(pendingRowId);

    const raf = window.requestAnimationFrame(() => {
      const selector = `[data-settings-focus-key="${escapedKey}"][data-settings-row-id="${escapedRowId}"]`;
      const node = document.querySelector<HTMLElement>(selector);
      if (node) {
        node.focus({ preventScroll: false });
        node.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      window.sessionStorage.removeItem(storageKey);
    });

    return () => window.cancelAnimationFrame(raf);
  }, [storageKey]);

  return {
    rememberRow,
    focusKey: storageKey,
  };
}
