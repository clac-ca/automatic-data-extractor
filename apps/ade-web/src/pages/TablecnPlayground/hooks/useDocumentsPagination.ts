import { useMemo } from "react";

import { useSearchParams } from "@app/navigation/urlState";
import { DEFAULT_PAGE_SIZE, parseNumberParam } from "../utils";

export function useDocumentsPagination() {
  const [searchParams] = useSearchParams();

  const page = useMemo(
    () => parseNumberParam(searchParams.get("page"), 1),
    [searchParams],
  );
  const perPage = useMemo(
    () => parseNumberParam(searchParams.get("perPage"), DEFAULT_PAGE_SIZE),
    [searchParams],
  );

  return { page, perPage };
}
