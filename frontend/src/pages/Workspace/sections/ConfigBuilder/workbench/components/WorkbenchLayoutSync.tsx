import { useEffect } from "react";

import { useSidebar } from "@/components/ui/sidebar";

import type { WorkbenchPane } from "../state/workbenchSearchParams";

export function WorkbenchLayoutSync({
  outputCollapsed,
  consoleFraction,
  isMaximized,
  pane,
}: {
  readonly outputCollapsed: boolean;
  readonly consoleFraction: number | null;
  readonly isMaximized: boolean;
  readonly pane: WorkbenchPane;
}) {
  const { state, openMobile } = useSidebar();

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [state, openMobile, outputCollapsed, consoleFraction, isMaximized, pane]);

  return null;
}
