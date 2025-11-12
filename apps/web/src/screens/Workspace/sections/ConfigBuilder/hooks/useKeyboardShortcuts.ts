import { useEffect } from "react";

interface KeyboardShortcutOptions {
  readonly onToggleExplorer: () => void;
  readonly onToggleConsole: () => void;
  readonly onSave: () => void;
  readonly onQuickOpen: () => void;
  readonly onSplit: () => void;
  readonly onZen: () => void;
}

function isModifierPressed(event: KeyboardEvent) {
  return event.metaKey || event.ctrlKey;
}

export function useKeyboardShortcuts({
  onToggleExplorer,
  onToggleConsole,
  onSave,
  onQuickOpen,
  onSplit,
  onZen,
}: KeyboardShortcutOptions) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!isModifierPressed(event)) {
        if (event.key === "Escape") {
          onToggleConsole();
        }
        return;
      }

      const key = event.key.toLowerCase();
      if (key === "b") {
        event.preventDefault();
        onToggleExplorer();
        return;
      }
      if (key === "j") {
        event.preventDefault();
        onToggleConsole();
        return;
      }
      if (key === "p" || key === "k") {
        event.preventDefault();
        onQuickOpen();
        return;
      }
      if (key === "s") {
        event.preventDefault();
        onSave();
        return;
      }
      if (event.key === "\\") {
        event.preventDefault();
        onSplit();
        return;
      }
      if (event.shiftKey && key === "enter") {
        event.preventDefault();
        onZen();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onToggleExplorer, onToggleConsole, onSave, onQuickOpen, onSplit, onZen]);
}
