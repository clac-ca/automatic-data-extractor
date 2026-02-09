import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import {
  DEFAULT_WORKBENCH_SEARCH,
  applyWorkbenchSearchPatch,
  readWorkbenchSearchParams,
  type WorkbenchConsoleState,
  type WorkbenchPane,
  type WorkbenchSearchPatch,
} from "./workbenchSearchParams";

interface WorkbenchUrlState {
  readonly fileId?: string;
  readonly pane: WorkbenchPane;
  readonly console: WorkbenchConsoleState;
  readonly consoleExplicit: boolean;
  readonly setFileId: (fileId: string | undefined) => void;
  readonly setPane: (pane: WorkbenchPane) => void;
  readonly setConsole: (console: WorkbenchConsoleState) => void;
  readonly patchState: (patch: WorkbenchSearchPatch) => void;
}

export function useWorkbenchUrlState(): WorkbenchUrlState {
  const [params, setSearchParams] = useSearchParams();
  const snapshot = useMemo(() => readWorkbenchSearchParams(params), [params]);

  const patchState = useCallback(
    (patch: WorkbenchSearchPatch) => {
      setSearchParams(
        (current) => applyWorkbenchSearchPatch(current, patch),
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setFileId = useCallback(
    (fileId: string | undefined) => {
      if (snapshot.fileId === fileId || (!fileId && !snapshot.present.fileId)) {
        return;
      }
      patchState({ fileId: fileId ?? undefined });
    },
    [patchState, snapshot.fileId, snapshot.present.fileId],
  );

  const setPane = useCallback(
    (pane: WorkbenchPane) => {
      if (snapshot.pane === pane) {
        return;
      }
      patchState({ pane });
    },
    [patchState, snapshot.pane],
  );

  const setConsole = useCallback(
    (console: WorkbenchConsoleState) => {
      if (snapshot.console === console) {
        return;
      }
      patchState({ console });
    },
    [patchState, snapshot.console],
  );

  return {
    fileId: snapshot.fileId ?? DEFAULT_WORKBENCH_SEARCH.fileId,
    pane: snapshot.pane,
    console: snapshot.console,
    consoleExplicit: snapshot.present.console,
    setFileId,
    setPane,
    setConsole,
    patchState,
  };
}
