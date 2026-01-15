import { useCallback, useMemo } from "react";

import { useSearchParams } from "@/navigation/urlState";
import {
  DEFAULT_WORKBENCH_SEARCH,
  mergeWorkbenchSearchParams,
  readWorkbenchSearchParams,
  type WorkbenchConsoleState,
  type WorkbenchPane,
} from "./workbenchSearchParams";

interface WorkbenchUrlState {
  readonly fileId?: string;
  readonly pane: WorkbenchPane;
  readonly console: WorkbenchConsoleState;
  readonly consoleExplicit: boolean;
  readonly setFileId: (fileId: string | undefined) => void;
  readonly setPane: (pane: WorkbenchPane) => void;
  readonly setConsole: (console: WorkbenchConsoleState) => void;
}

export function useWorkbenchUrlState(): WorkbenchUrlState {
  const [params, setSearchParams] = useSearchParams();
  const snapshot = useMemo(() => readWorkbenchSearchParams(params), [params]);

  const setFileId = useCallback(
    (fileId: string | undefined) => {
      if (snapshot.fileId === fileId || (!fileId && !snapshot.present.fileId)) {
        return;
      }
      setSearchParams((current) => mergeWorkbenchSearchParams(current, { fileId: fileId ?? undefined }), {
        replace: true,
      });
    },
    [setSearchParams, snapshot.fileId, snapshot.present.fileId],
  );

  const setPane = useCallback(
    (pane: WorkbenchPane) => {
      if (snapshot.pane === pane) {
        return;
      }
      setSearchParams((current) => mergeWorkbenchSearchParams(current, { pane }), { replace: true });
    },
    [setSearchParams, snapshot.pane],
  );

  const setConsole = useCallback(
    (console: WorkbenchConsoleState) => {
      if (snapshot.console === console) {
        return;
      }
      setSearchParams((current) => mergeWorkbenchSearchParams(current, { console }), { replace: true });
    },
    [setSearchParams, snapshot.console],
  );

  return {
    fileId: snapshot.fileId ?? DEFAULT_WORKBENCH_SEARCH.fileId,
    pane: snapshot.pane,
    console: snapshot.console,
    consoleExplicit: snapshot.present.console,
    setFileId,
    setPane,
    setConsole,
  };
}
