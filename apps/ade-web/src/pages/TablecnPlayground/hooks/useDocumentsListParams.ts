import { useMemo } from "react";

import { useSearchParams } from "@app/navigation/urlState";
import { DEFAULT_PAGE_SIZE, parseNumberParam } from "../utils";
import type { DocumentsListParams } from "../types";

export function useDocumentsListParams(): DocumentsListParams {
  const [searchParams] = useSearchParams();

  const page = useMemo(
    () => parseNumberParam(searchParams.get("page"), 1),
    [searchParams],
  );
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
    page,
    perPage,
    sort,
    filters,
    joinOperator,
    q,
  };
}
