import { useEffect, useState } from "react";

interface ShortcutHintOptions {
  readonly macLabel?: string;
  readonly windowsLabel?: string;
}

const DEFAULT_MAC_LABEL = "⌘K";
const DEFAULT_WINDOWS_LABEL = "Ctrl+K";

export function useShortcutHint({ macLabel = DEFAULT_MAC_LABEL, windowsLabel = DEFAULT_WINDOWS_LABEL }: ShortcutHintOptions = {}) {
  const [hint, setHint] = useState(macLabel);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const platform = window.navigator.platform ?? "";
    const isApplePlatform = /Mac|iPhone|iPad|Macintosh/.test(platform);
    setHint(isApplePlatform ? macLabel : windowsLabel);
  }, [macLabel, windowsLabel]);

  return hint;
}
