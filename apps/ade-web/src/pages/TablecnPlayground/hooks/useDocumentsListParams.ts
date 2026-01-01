import { useEffect, useMemo } from "react";

import { useSearchParams } from "@app/navigation/urlState";
import { DEFAULT_PAGE_SIZE, parseNumberParam } from "../utils";
import type { DocumentsListParams } from "../types";

export function useDocumentsListParams(): DocumentsListParams {
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (!searchParams.has("page")) return;
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.delete("page");
      return params;
    }, { replace: true });
  }, [searchParams, setSearchParams]);
  const perPage = useMemo(
    () => parseNumberParam(searchParams.get("perPage"), DEFAULT_PAGE_SIZE),
    [searchParams],
  );

  const sort = useMemo(() => searchParams.get("sort"), [searchParams]);
  const filters = useMemo(() => searchParams.get("filters"), [searchParams]);
  const joinOperator = useMemo(() => {
    const value = searchParams.get("joinOperator");
    return value === "and" || value === "or" ? value : null;
  }, [searchParams]);
  const q = useMemo(() => {
    const value = searchParams.get("q")?.trim();
    return value ? value : null;
  }, [searchParams]);

  return {
    perPage,
    sort,
    filters,
    joinOperator,
    q,
  };
}
