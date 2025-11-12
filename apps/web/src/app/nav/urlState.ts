import { useCallback, useMemo } from "react";

import { useLocation, useNavigate } from "./history";

export function getParam(search: string, key: string) {
  return new URLSearchParams(search).get(key) ?? undefined;
}

export function setParams(url: URL, patch: Record<string, string | undefined>) {
  const next = new URL(url.toString());
  const query = new URLSearchParams(next.search);

  for (const [paramKey, value] of Object.entries(patch)) {
    if (value == null || value === "") {
      query.delete(paramKey);
    } else {
      query.set(paramKey, String(value));
    }
  }

  next.search = query.toString() ? `?${query}` : "";
  return `${next.pathname}${next.search}${next.hash}`;
}

type SetSearchParamsInit = URLSearchParams | ((prev: URLSearchParams) => URLSearchParams);
type SetSearchParamsOptions = { replace?: boolean };

export function useSearchParams(): [URLSearchParams, (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void] {
  const location = useLocation();
  const navigate = useNavigate();

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const setSearchParams = useCallback(
    (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => {
      const next = typeof init === "function" ? init(new URLSearchParams(params)) : new URLSearchParams(init);
      const search = next.toString();
      const target = `${location.pathname}${search ? `?${search}` : ""}${location.hash}`;
      navigate(target, { replace: options?.replace });
    },
    [location.hash, location.pathname, navigate, params],
  );

  return [params, setSearchParams];
}
