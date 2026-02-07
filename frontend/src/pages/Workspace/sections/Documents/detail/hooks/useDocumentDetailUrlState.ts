import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import {
  getDocumentDetailState,
  type DocumentActivityFilter,
  type DocumentDetailTab,
  type DocumentPreviewSource,
} from "@/pages/Workspace/sections/Documents/shared/navigation";

export function useDocumentDetailUrlState() {
  const [searchParams, setSearchParams] = useSearchParams();

  const state = useMemo(
    () => getDocumentDetailState(searchParams),
    [searchParams],
  );

  const setTab = useCallback(
    (nextTab: DocumentDetailTab) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", nextTab);

      if (nextTab === "preview") {
        next.delete("activityFilter");
      } else {
        next.delete("source");
        next.delete("sheet");
      }

      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setActivityFilter = useCallback(
    (nextFilter: DocumentActivityFilter) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", "activity");
      next.delete("source");
      next.delete("sheet");

      if (nextFilter === "all") {
        next.delete("activityFilter");
      } else {
        next.set("activityFilter", nextFilter);
      }

      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setPreviewSource = useCallback(
    (nextSource: DocumentPreviewSource) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", "preview");
      next.delete("activityFilter");
      next.set("source", nextSource);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setPreviewSheet = useCallback(
    (nextSheet: string | null) => {
      const next = new URLSearchParams(searchParams);

      if (!nextSheet) {
        next.delete("sheet");
      } else {
        next.set("sheet", nextSheet);
      }

      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  return {
    state,
    setTab,
    setActivityFilter,
    setPreviewSource,
    setPreviewSheet,
  };
}
